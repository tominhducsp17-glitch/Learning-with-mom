from __future__ import annotations

import base64
import html
import json
import posixpath
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .asset_converter import convert_vector_asset


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "v": "urn:schemas-microsoft-com:vml",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

DISPLAYABLE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg"}
ILLUSTRATION_EXTENSIONS = DISPLAYABLE_EXTENSIONS
VECTOR_EXTENSIONS = {".wmf", ".emf"}


@dataclass
class BodyItem:
    kind: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class AssetContext:
    zip_file: zipfile.ZipFile
    rels: dict[str, str]
    output_dir: Path
    libreoffice_renders: list[dict[str, Any]] = field(default_factory=list)
    counter: int = 0
    assets: list[dict[str, Any]] = field(default_factory=list)
    assets_by_relationship: dict[str, dict[str, Any]] = field(default_factory=dict)
    unconverted_vector_count: int = 0
    convert_images: bool = False

    def add_image(
        self,
        relationship_id: str | None,
        extent_emu: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        asset = self._asset_for_relationship(relationship_id)
        block = {
            "type": "image",
            "asset_id": asset["asset_id"],
            "render_path": asset["render_path"],
            "original_path": asset["original_path"],
            "extension": asset["extension"],
            "status": asset["status"],
        }
        if extent_emu:
            block["extent_emu"] = extent_emu
            block["display_width_px"] = extent_emu["cx"] / 9525
            block["display_height_px"] = extent_emu["cy"] / 9525
        return block

    def _asset_for_relationship(self, relationship_id: str | None) -> dict[str, Any]:
        if relationship_id and relationship_id in self.assets_by_relationship:
            return self.assets_by_relationship[relationship_id]
        self.counter += 1
        asset_id = f"img_{self.counter:04d}"
        rel_target = self.rels.get(relationship_id or "", "")
        docx_path = _relationship_target_to_docx_path(rel_target)
        ext = Path(docx_path).suffix.lower() if docx_path else ".bin"
        original_name = f"{asset_id}{ext}"
        original_path = self.output_dir / original_name
        status = "missing"
        render_path: Path | None = None
        warning: str | None = None

        if docx_path and docx_path in self.zip_file.namelist():
            original_path.write_bytes(self.zip_file.read(docx_path))
            if ext in DISPLAYABLE_EXTENSIONS:
                status = "ready"
                render_path = original_path
            elif ext in VECTOR_EXTENSIONS:
                libreoffice_render = self._libreoffice_render_for_asset(asset_id) if self.convert_images else None
                conversion = None
                if libreoffice_render:
                    render_path = self.output_dir / f"{asset_id}{libreoffice_render['extension']}"
                    render_path.write_bytes(libreoffice_render["bytes"])
                    status = "converted"
                else:
                    conversion = convert_vector_asset(original_path, asset_id) if self.convert_images else None
                if status != "converted" and conversion and conversion.status == "converted" and conversion.render_path:
                    status = "converted"
                    render_path = conversion.render_path
                else:
                    if status != "converted":
                        status = "placeholder"
                        self.unconverted_vector_count += 1
                        render_path = self.output_dir / f"{asset_id}.placeholder.svg"
                        _write_placeholder_svg(render_path, asset_id, ext)
                        reason = conversion.message if conversion else "Image conversion was not requested."
                        warning = (
                            f"{asset_id} references {ext.upper()} media. Original file was copied, "
                            f"but no browser-friendly image was produced. {reason}"
                        )
            else:
                status = "placeholder"
                render_path = self.output_dir / f"{asset_id}.placeholder.svg"
                _write_placeholder_svg(render_path, asset_id, ext)
                warning = f"{asset_id} has unsupported media extension {ext}."
        else:
            render_path = self.output_dir / f"{asset_id}.missing.svg"
            _write_placeholder_svg(render_path, asset_id, "missing")
            warning = f"{asset_id} relationship {relationship_id!r} did not resolve to media."

        asset = {
            "asset_id": asset_id,
            "relationship_id": relationship_id,
            "docx_path": docx_path,
            "original_path": _relpath(original_path),
            "render_path": _relpath(render_path),
            "extension": ext,
            "status": status,
        }
        if warning:
            asset["warning"] = warning
        self.assets.append(asset)
        if relationship_id:
            self.assets_by_relationship[relationship_id] = asset
        return asset

    def _libreoffice_render_for_asset(self, asset_id: str) -> dict[str, Any] | None:
        match = re.match(r"img_(\d+)$", asset_id)
        if not match:
            return None
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(self.libreoffice_renders):
            return None
        return self.libreoffice_renders[index]


def parse_docx_exam(
    docx_path: str | Path,
    assets_dir: str | Path | None = None,
    convert_images: bool = False,
) -> dict[str, Any]:
    source_path = Path(docx_path)
    if assets_dir is None:
        assets_dir = Path("storage") / "extracted-assets" / source_path.stem
    output_dir = Path(assets_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source_path) as docx_zip:
        rels = _read_relationships(docx_zip)
        libreoffice_renders = _render_docx_images_with_libreoffice(source_path) if convert_images else []
        context = AssetContext(
            docx_zip,
            rels,
            output_dir,
            libreoffice_renders=libreoffice_renders,
            convert_images=convert_images,
        )
        document = ET.fromstring(docx_zip.read("word/document.xml"))
        body = document.find("w:body", NS)
        if body is None:
            raise ValueError("word/document.xml does not contain w:body")

        body_items = _read_body_items(body, context)

    title = _extract_title(body_items)
    answer_keys = _parse_answer_tables([item.rows for item in body_items if item.kind == "table"])
    sections = _parse_sections(body_items, answer_keys)
    _attach_markup(sections)
    assets_by_id = _asset_map(context.assets, sections)
    warnings = _validate_exam(sections, answer_keys)

    if context.unconverted_vector_count:
        warnings.insert(
            0,
            {
                "code": "UNCONVERTED_VECTOR_IMAGE",
                "severity": "warning",
                "message": (
                    f"{context.unconverted_vector_count} WMF/EMF inline assets were copied "
                    "and represented by SVG placeholders. Configure a converter before "
                    "claiming full visual fidelity."
                ),
                "count": context.unconverted_vector_count,
            },
        )

    return {
        "schema_version": "0.1",
        "source_file": str(source_path),
        "title": title,
        "sections": sections,
        "answer_keys": answer_keys,
        "assets": context.assets,
        "assets_by_id": assets_by_id,
        "warnings": warnings,
    }


def write_parsed_exam(
    docx_path: str | Path,
    output_path: str | Path,
    assets_dir: str | Path | None = None,
    convert_images: bool = False,
) -> dict[str, Any]:
    parsed = parse_docx_exam(docx_path, assets_dir=assets_dir, convert_images=convert_images)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return parsed


def _render_docx_images_with_libreoffice(docx_path: Path) -> list[dict[str, Any]]:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return []

    with tempfile.TemporaryDirectory(prefix="mathexam-lo-") as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "source.docx"
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        shutil.copy2(docx_path, input_path)
        try:
            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "html",
                    "--outdir",
                    str(output_dir),
                    str(input_path),
                ],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []

        html_files = sorted(output_dir.glob("*.html"))
        if not html_files:
            return []
        html_text = html_files[0].read_text(encoding="utf-8", errors="ignore")
        image_sources = re.findall(r"<img[^>]+src=['\"]([^'\"]+)['\"]", html_text, flags=re.I)
        unique_sources: list[str] = []
        seen: set[str] = set()
        for source in image_sources:
            source = html.unescape(source)
            if source in seen:
                continue
            seen.add(source)
            unique_sources.append(source)

        rendered: list[dict[str, Any]] = []
        for source in unique_sources:
            image_path = (output_dir / source).resolve()
            try:
                image_path.relative_to(output_dir.resolve())
            except ValueError:
                continue
            if not image_path.exists() or not image_path.is_file():
                continue
            suffix = image_path.suffix.lower()
            if suffix not in DISPLAYABLE_EXTENSIONS:
                continue
            image_bytes, render_suffix = _normalize_libreoffice_render(image_path)
            rendered.append(
                {
                    "extension": render_suffix,
                    "bytes": image_bytes,
                    "source": source,
                    "tool": "libreoffice",
                }
            )
        return rendered


def _normalize_libreoffice_render(image_path: Path) -> tuple[bytes, str]:
    """Convert LibreOffice-rendered image to high-DPI PNG.

    Upscales 3× using ImageMagick Point (nearest-neighbor) filter so math
    formula edges stay sharp.  The JSON metadata still records the original
    Word display size; the browser down-scales the larger image → crisp
    rendering on Retina / high-DPI screens.
    """
    magick = shutil.which("convert") or shutil.which("magick")
    if not magick:
        return image_path.read_bytes(), image_path.suffix.lower()

    png_path = image_path.with_suffix(".png")
    try:
        subprocess.run(
            [magick, str(image_path), "-filter", "Point", "-resize", "300%", str(png_path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass

    if png_path.exists() and png_path.stat().st_size > 0:
        return png_path.read_bytes(), ".png"
    return image_path.read_bytes(), image_path.suffix.lower()


def _read_relationships(docx_zip: zipfile.ZipFile) -> dict[str, str]:
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in docx_zip.namelist():
        return {}
    root = ET.fromstring(docx_zip.read(rels_path))
    rels: dict[str, str] = {}
    for rel in root.findall("rel:Relationship", NS):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            rels[rel_id] = target
    return rels


def _read_body_items(body: ET.Element, context: AssetContext) -> list[BodyItem]:
    items: list[BodyItem] = []
    for child in body:
        tag = _local_name(child.tag)
        if tag == "p":
            blocks = _mark_standalone_illustrations(_paragraph_blocks(child, context))
            if _blocks_text(blocks).strip() or _has_rich_content(blocks):
                items.append(BodyItem(kind="paragraph", blocks=blocks))
        elif tag == "tbl":
            items.append(BodyItem(kind="table", rows=_table_text_rows(child)))
    return items


def _paragraph_blocks(paragraph: ET.Element, context: AssetContext) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for child in paragraph:
        _append_inline_blocks(child, blocks, context)
    return _merge_text_blocks(blocks)


def _mark_standalone_illustrations(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark browser-friendly images that occupy their own Word paragraph."""
    if _blocks_text(blocks).strip():
        return blocks

    image_blocks = [block for block in blocks if block.get("type") == "image"]
    if not image_blocks or not all(
        str(block.get("extension", "")).lower() in ILLUSTRATION_EXTENSIONS
        for block in image_blocks
    ):
        return blocks

    for block in image_blocks:
        block["display_mode"] = "block"
    return image_blocks


def _append_inline_blocks(
    element: ET.Element,
    blocks: list[dict[str, Any]],
    context: AssetContext,
) -> None:
    tag = _local_name(element.tag)
    if tag == "t":
        _append_text(blocks, element.text or "")
        return
    if tag == "tab":
        _append_text(blocks, "\t")
        return
    if tag in {"br", "cr"}:
        _append_text(blocks, "\n")
        return
    if tag == "oMath":
        latex = _omml_to_latex(element)
        if latex:
            blocks.append({"type": "math", "latex": latex})
        return
    if tag in {"drawing", "pict", "object", "shape"}:
        references = _image_references(element)
        if not references:
            for child in element:
                _append_inline_blocks(child, blocks, context)
            return
        for reference in references:
            blocks.append(context.add_image(reference["relationship_id"], reference.get("extent_emu")))
        return

    for child in element:
        _append_inline_blocks(child, blocks, context)


def _omml_to_latex(element: ET.Element) -> str:
    latex = _omml_children_to_latex(element).strip()
    function_pattern = r"(?<![A-Za-z\\])(arcsin|arccos|arctan|sin|cos|tan|cot|sec|csc|log|ln|exp)(?=[A-Za-z0-9(])"
    return re.sub(function_pattern, lambda match: rf"\{match.group(1)} ", latex)


def _omml_children_to_latex(element: ET.Element, *, skip: set[str] | None = None) -> str:
    skipped = skip or set()
    return "".join(
        _omml_node_to_latex(child)
        for child in element
        if _local_name(child.tag) not in skipped
    )


def _omml_node_to_latex(element: ET.Element) -> str:
    tag = _local_name(element.tag)
    if tag.endswith("Pr") or tag in {"ctrlPr", "argPr"}:
        return ""
    if tag == "t":
        return _math_text_to_latex(element.text or "")
    if tag == "r":
        text = "".join(_math_text_to_latex(node.text or "") for node in element.findall("m:t", NS))
        script = element.find("m:rPr/m:scr", NS)
        if script is not None and _attribute_value(script, "val") == "double-struck":
            raw = "".join(node.text or "" for node in element.findall("m:t", NS))
            if raw:
                return rf"\mathbb{{{raw}}}"
        return text
    if tag == "f":
        numerator = _omml_container_to_latex(element.find("m:num", NS))
        denominator = _omml_container_to_latex(element.find("m:den", NS))
        return rf"\frac{{{numerator}}}{{{denominator}}}"
    if tag == "d":
        props = element.find("m:dPr", NS)
        begin = _delimiter_property(props, "begChr", "(")
        end = _delimiter_property(props, "endChr", ")")
        contents = [_omml_node_to_latex(child) for child in element.findall("m:e", NS)]
        if begin == "|" and not end:
            return rf"\mid {''.join(contents)}"
        separator = _delimiter_property(props, "sepChr", "|")
        inner = separator.join(contents)
        return f"{_left_delimiter(begin)}{inner}{_right_delimiter(end)}"
    if tag == "func":
        name = _omml_container_to_latex(element.find("m:fName", NS))
        argument = _omml_container_to_latex(element.find("m:e", NS))
        plain_name = re.sub(r"\\([A-Za-z]+)\s*", r"\1", name)
        if plain_name in {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "max", "min"}:
            name = rf"\{plain_name} "
        return f"{name}{argument}"
    if tag in {"sSup", "sSub", "sSubSup"}:
        base = _omml_container_to_latex(element.find("m:e", NS))
        sub = _omml_container_to_latex(element.find("m:sub", NS))
        sup = _omml_container_to_latex(element.find("m:sup", NS))
        grouped_base = base if base.rstrip().endswith((")", "]", r"\right)")) else f"{{{base}}}"
        if tag == "sSup":
            return rf"{grouped_base}^{{{sup}}}"
        if tag == "sSub":
            return rf"{grouped_base}_{{{sub}}}"
        return rf"{grouped_base}_{{{sub}}}^{{{sup}}}"
    if tag == "rad":
        degree = _omml_container_to_latex(element.find("m:deg", NS))
        body = _omml_container_to_latex(element.find("m:e", NS))
        return rf"\sqrt[{degree}]{{{body}}}" if degree else rf"\sqrt{{{body}}}"
    if tag in {"limLow", "limUpp"}:
        base = _omml_container_to_latex(element.find("m:e", NS))
        limit = _omml_container_to_latex(element.find("m:lim", NS))
        marker = "_" if tag == "limLow" else "^"
        return rf"{{{base}}}{marker}{{{limit}}}"
    return _omml_children_to_latex(element)


def _omml_container_to_latex(element: ET.Element | None) -> str:
    return _omml_children_to_latex(element) if element is not None else ""


def _attribute_value(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    for key, value in element.attrib.items():
        if _local_name(key) == name:
            return value
    return None


def _delimiter_property(props: ET.Element | None, name: str, default: str) -> str:
    if props is None:
        return default
    node = props.find(f"m:{name}", NS)
    value = _attribute_value(node, "val")
    return default if node is None or value is None else value


def _left_delimiter(value: str) -> str:
    if not value:
        return ""
    escaped = r"\{" if value == "{" else r"\lvert" if value == "|" else value
    return rf"\left{escaped}"


def _right_delimiter(value: str) -> str:
    if not value:
        return ""
    escaped = r"\}" if value == "}" else r"\rvert" if value == "|" else value
    return rf"\right{escaped}"


def _math_text_to_latex(text: str) -> str:
    replacements = {
        "{": r"\{",
        "}": r"\}",
        "π": r"\pi ",
        "∞": r"\infty ",
        "∈": r"\in ",
        "∉": r"\notin ",
        "≠": r"\ne ",
        "≤": r"\le ",
        "≥": r"\ge ",
        "⇔": r"\Leftrightarrow ",
        "⇒": r"\Rightarrow ",
        "→": r"\to ",
        "∣": r"\mid ",
        "ℝ": r"\mathbb{R}",
        "ℤ": r"\mathbb{Z}",
        "×": r"\times ",
    }
    output = "".join(replacements.get(char, r"\setminus " if char == "\\" else char) for char in text)
    function_pattern = r"(?<![A-Za-z\\])(arcsin|arccos|arctan|sin|cos|tan|cot|sec|csc|log|ln|exp)(?=[A-Za-z0-9(])"
    return re.sub(function_pattern, lambda match: rf"\{match.group(1)} ", output)


def _image_references(element: ET.Element) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    drawing_containers = element.findall(".//wp:inline", NS) + element.findall(".//wp:anchor", NS)
    for container in drawing_containers:
        extent_emu = _wp_extent_emu(container)
        for rel_id in _blip_relationship_ids(container):
            references.append({"relationship_id": rel_id, "extent_emu": extent_emu})

    shape_candidates = []
    if _local_name(element.tag) == "shape":
        shape_candidates.append(element)
    shape_candidates.extend(element.findall(".//v:shape", NS))
    for shape in shape_candidates:
        extent_emu = _vml_extent_emu(shape)
        for image_data in shape.findall(".//v:imagedata", NS):
            rel_id = image_data.attrib.get(f"{{{NS['r']}}}id")
            if rel_id:
                references.append({"relationship_id": rel_id, "extent_emu": extent_emu})

    if references:
        return references

    return [
        {"relationship_id": rel_id, "extent_emu": None}
        for rel_id in _image_relationship_ids(element)
    ]


def _image_relationship_ids(element: ET.Element) -> list[str]:
    relationship_ids: list[str] = []
    relationship_ids.extend(_blip_relationship_ids(element))
    for image_data in element.findall(".//v:imagedata", NS):
        rel_id = image_data.attrib.get(f"{{{NS['r']}}}id")
        if rel_id:
            relationship_ids.append(rel_id)
    return relationship_ids


def _blip_relationship_ids(element: ET.Element) -> list[str]:
    relationship_ids: list[str] = []
    for blip in element.findall(".//a:blip", NS):
        rel_id = blip.attrib.get(f"{{{NS['r']}}}embed") or blip.attrib.get(f"{{{NS['r']}}}link")
        if rel_id:
            relationship_ids.append(rel_id)
    return relationship_ids


def _wp_extent_emu(element: ET.Element) -> dict[str, int] | None:
    extent = element.find("wp:extent", NS)
    if extent is None:
        extent = element.find(".//wp:extent", NS)
    if extent is None:
        return None
    try:
        return {"cx": int(extent.attrib["cx"]), "cy": int(extent.attrib["cy"])}
    except (KeyError, ValueError):
        return None


def _vml_extent_emu(element: ET.Element) -> dict[str, int] | None:
    style = element.attrib.get("style", "")
    width = _css_length_to_px(_style_value(style, "width"))
    height = _css_length_to_px(_style_value(style, "height"))
    if width is None or height is None:
        return None
    return {"cx": round(width * 9525), "cy": round(height * 9525)}


def _style_value(style: str, name: str) -> str | None:
    for declaration in style.split(";"):
        if ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        if key.strip().lower() == name:
            return value.strip()
    return None


def _css_length_to_px(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"^\s*([0-9.]+)\s*(pt|px|in|cm|mm)?\s*$", value, re.I)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    if unit == "pt":
        return amount * 96 / 72
    if unit == "in":
        return amount * 96
    if unit == "cm":
        return amount * 96 / 2.54
    if unit == "mm":
        return amount * 96 / 25.4
    return amount


def _table_text_rows(table: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.findall("w:tr", NS):
        cells: list[str] = []
        for tc in tr.findall("w:tc", NS):
            paragraph_texts = []
            for paragraph in tc.findall("w:p", NS):
                text = "".join(t.text or "" for t in paragraph.findall(".//w:t", NS))
                if text.strip():
                    paragraph_texts.append(_clean_space(text))
            cells.append("\n".join(paragraph_texts).strip())
        rows.append(cells)
    return rows


def _extract_title(items: list[BodyItem]) -> str:
    for item in items:
        if item.kind != "paragraph":
            continue
        text = _clean_space(_blocks_text(item.blocks))
        if text and not _is_section_heading(text):
            return text
    return ""


def _parse_sections(
    items: list[BodyItem],
    answer_keys: dict[str, Any],
) -> list[dict[str, Any]]:
    sections_by_type = {
        "single_choice": {"type": "single_choice", "title": "", "questions": []},
        "true_false": {"type": "true_false", "title": "", "questions": []},
        "short_answer": {"type": "short_answer", "title": "", "questions": []},
    }
    current_type: str | None = None
    current_question: dict[str, Any] | None = None
    current_subitem: str | None = None

    for item in items:
        if item.kind != "paragraph":
            continue
        blocks = item.blocks
        text = _clean_space(_blocks_text(blocks))
        if not text and not _has_rich_content(blocks):
            continue

        section_type = _section_type_from_heading(text)
        if section_type:
            current_type = section_type
            sections_by_type[current_type]["title"] = text
            current_question = None
            current_subitem = None
            continue

        if current_type is None:
            continue

        question_number = _question_number(text)
        if question_number is not None:
            current_question = _new_question(current_type, question_number, _remove_question_prefix(blocks))
            sections_by_type[current_type]["questions"].append(current_question)
            current_subitem = None
            continue

        if current_question is None:
            continue

        if current_type == "single_choice":
            option_blocks = _split_labeled_blocks(blocks, labels=("A", "B", "C", "D"))
            if option_blocks:
                for label, label_blocks in option_blocks.items():
                    current_question["options"][label].extend(label_blocks)
            else:
                current_question["prompt_blocks"].extend(blocks)
        elif current_type == "true_false":
            subitem_blocks = _split_labeled_blocks(blocks, labels=("a", "b", "c", "d"))
            if subitem_blocks:
                for label, label_blocks in subitem_blocks.items():
                    current_question["statements"][label].extend(label_blocks)
                    current_subitem = label
            elif current_subitem:
                current_question["statements"][current_subitem].extend(blocks)
            else:
                current_question["prompt_blocks"].extend(blocks)
        elif current_type == "short_answer":
            current_question["prompt_blocks"].extend(blocks)

    for question in sections_by_type["single_choice"]["questions"]:
        key = str(question["number"])
        question["correct_answer"] = answer_keys.get("single_choice", {}).get(key)
    for question in sections_by_type["true_false"]["questions"]:
        key = str(question["number"])
        question["correct_answer"] = answer_keys.get("true_false", {}).get(key)
    for question in sections_by_type["short_answer"]["questions"]:
        key = str(question["number"])
        question["correct_answer"] = answer_keys.get("short_answer", {}).get(key)

    return [
        sections_by_type["single_choice"],
        sections_by_type["true_false"],
        sections_by_type["short_answer"],
    ]


def _new_question(section_type: str, number: int, prompt_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    question: dict[str, Any] = {
        "number": number,
        "prompt_blocks": prompt_blocks,
    }
    if section_type == "single_choice":
        question["options"] = {"A": [], "B": [], "C": [], "D": []}
        question["correct_answer"] = None
    elif section_type == "true_false":
        question["statements"] = {"a": [], "b": [], "c": [], "d": []}
        question["correct_answer"] = None
    else:
        question["correct_answer"] = None
    return question


def _parse_answer_tables(tables: list[list[list[str]]]) -> dict[str, Any]:
    answer_keys: dict[str, Any] = {
        "single_choice": {},
        "true_false": {},
        "short_answer": {},
    }
    for table in tables:
        if not table:
            continue
        normalized_first_cell = _fold(_cell(table, 0, 0))
        if len(table) >= 2 and normalized_first_cell == "cau":
            numbers = [_clean_space(cell) for cell in table[0][1:]]
            choices = [_clean_space(cell) for cell in table[1][1:]]
            parsed = {num: choice for num, choice in zip(numbers, choices) if num}
            if len(parsed) == 12:
                answer_keys["single_choice"] = parsed
            elif len(parsed) == 6:
                answer_keys["short_answer"] = parsed
        elif _looks_like_true_false_table(table):
            answer_keys["true_false"] = _parse_true_false_answer_table(table)
    return answer_keys


def _parse_true_false_answer_table(table: list[list[str]]) -> dict[str, dict[str, str]]:
    answers: dict[str, dict[str, str]] = {}
    question_numbers = [_clean_space(cell) for cell in table[0]]
    for col_index, question_number in enumerate(question_numbers):
        if not question_number:
            continue
        answers[question_number] = {}
        for row in table[1:]:
            cell = _cell_from_row(row, col_index)
            match = re.match(r"\s*([abcd])\s*[).]?\s*([ĐDđdS])", cell)
            if match:
                answers[question_number][match.group(1).lower()] = _normalize_true_false(match.group(2))
    return answers


def _looks_like_true_false_table(table: list[list[str]]) -> bool:
    if len(table) < 5 or len(table[0]) < 4:
        return False
    first_row_numbers = all(_clean_space(cell).isdigit() for cell in table[0])
    has_subitems = any(re.match(r"\s*[abcd]\s*[).]", cell, re.I) for row in table[1:] for cell in row)
    return first_row_numbers and has_subitems


def _validate_exam(sections: list[dict[str, Any]], answer_keys: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    expected_counts = {"single_choice": 12, "true_false": 4, "short_answer": 6}
    for section in sections:
        section_type = section["type"]
        questions = section["questions"]
        expected = expected_counts[section_type]
        if len(questions) != expected:
            warnings.append(
                {
                    "code": "COUNT_MISMATCH",
                    "severity": "error",
                    "section": section_type,
                    "message": f"Expected {expected} questions, parsed {len(questions)}.",
                }
            )
        for question in questions:
            if question.get("correct_answer") in (None, {}, ""):
                warnings.append(
                    {
                        "code": "MISSING_ANSWER",
                        "severity": "error",
                        "section": section_type,
                        "question_number": question["number"],
                        "message": "Question has no answer from the parsed answer tables.",
                    }
                )
            if section_type == "single_choice":
                missing = [
                    label
                    for label, blocks in question["options"].items()
                    if not _blocks_text(blocks).strip() and not _has_rich_content(blocks)
                ]
                if missing:
                    warnings.append(
                        {
                            "code": "OPTION_COUNT_MISMATCH",
                            "severity": "error",
                            "section": section_type,
                            "question_number": question["number"],
                            "missing": missing,
                            "message": "Single-choice question is missing one or more A/B/C/D options.",
                        }
                    )
            if section_type == "true_false":
                missing = [
                    label
                    for label, blocks in question["statements"].items()
                    if not _blocks_text(blocks).strip() and not _has_rich_content(blocks)
                ]
                if missing:
                    warnings.append(
                        {
                            "code": "SUBITEM_COUNT_MISMATCH",
                            "severity": "error",
                            "section": section_type,
                            "question_number": question["number"],
                            "missing": missing,
                            "message": "True/false question is missing one or more a/b/c/d statements.",
                        }
                    )

    for key, expected in expected_counts.items():
        actual = len(answer_keys.get(key, {}))
        if actual != expected:
            warnings.append(
                {
                    "code": "ANSWER_TABLE_COUNT_MISMATCH",
                    "severity": "error",
                    "section": key,
                    "message": f"Expected {expected} answer keys, parsed {actual}.",
                }
            )
    return warnings


def _attach_markup(sections: list[dict[str, Any]]) -> None:
    for section in sections:
        for question in section["questions"]:
            question["prompt_markup"] = _blocks_to_markup(question.get("prompt_blocks", []))
            if "options" in question:
                question["options_markup"] = {
                    label: _blocks_to_markup(blocks)
                    for label, blocks in question["options"].items()
                }
            if "statements" in question:
                question["statements_markup"] = {
                    label: _blocks_to_markup(blocks)
                    for label, blocks in question["statements"].items()
                }


def _blocks_to_markup(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.get("type") == "image":
            asset_id = block.get("asset_id", "")
            if asset_id:
                parts.append(f"[img:${asset_id}$]")
        elif block.get("type") == "math":
            encoded = base64.urlsafe_b64encode(str(block.get("latex", "")).encode("utf-8")).decode("ascii").rstrip("=")
            if encoded:
                parts.append(f"[math64:${encoded}$]")
        elif block.get("type") == "text":
            parts.append(_escape_markup_text(block.get("text", "")))
    return "".join(parts)


def _escape_markup_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("[", "\\[")


def _asset_map(assets: list[dict[str, Any]], sections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped = {asset["asset_id"]: dict(asset) for asset in assets if asset.get("asset_id")}
    for block in _iter_image_blocks(sections):
        asset_id = block.get("asset_id")
        if not asset_id:
            continue
        asset = mapped.setdefault(asset_id, {"asset_id": asset_id})
        occurrence = {
            key: block[key]
            for key in ("extent_emu", "display_width_px", "display_height_px", "display_mode")
            if key in block
        }
        if occurrence:
            asset.setdefault("occurrences", []).append(occurrence)
            asset.setdefault("extent_emu", block.get("extent_emu"))
            asset.setdefault("display_width_px", block.get("display_width_px"))
            asset.setdefault("display_height_px", block.get("display_height_px"))
    return mapped


def _iter_image_blocks(sections: list[dict[str, Any]]):
    for section in sections:
        for question in section.get("questions", []):
            for block in question.get("prompt_blocks", []):
                if block.get("type") == "image":
                    yield block
            for nested_key in ("options", "statements"):
                for blocks in question.get(nested_key, {}).values():
                    for block in blocks:
                        if block.get("type") == "image":
                            yield block


def _split_labeled_blocks(
    blocks: list[dict[str, Any]],
    labels: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    label_set = {label.lower(): label for label in labels}
    label_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?<![\w])({label_pattern})\s*[\.)]", re.I)
    current_label: str | None = None
    split: dict[str, list[dict[str, Any]]] = {}
    seen_label = False

    for block in blocks:
        if block["type"] != "text":
            if current_label:
                split.setdefault(current_label, []).append(block)
            continue

        text = block["text"]
        cursor = 0
        for match in pattern.finditer(text):
            before = text[cursor : match.start()]
            if before and current_label:
                split.setdefault(current_label, []).append({"type": "text", "text": before})
            current_label = label_set[match.group(1).lower()]
            split.setdefault(current_label, [])
            seen_label = True
            cursor = match.end()
        remainder = text[cursor:]
        if remainder and current_label:
            split.setdefault(current_label, []).append({"type": "text", "text": remainder})

    if not seen_label:
        return {}
    return {label: _trim_blocks(split.get(label, [])) for label in labels if label in split}


def _remove_question_prefix(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    removed = False
    pattern = re.compile(r"^\s*Câu\s*\d+\s*[:.]\s*", re.I)
    for block in blocks:
        if removed or block["type"] != "text":
            output.append(block)
            continue
        text = block["text"]
        new_text = pattern.sub("", text, count=1)
        if new_text != text:
            removed = True
            if new_text:
                output.append({"type": "text", "text": new_text})
        else:
            output.append(block)
    return _trim_blocks(output)


def _question_number(text: str) -> int | None:
    match = re.match(r"\s*Câu\s*(\d+)\s*[:.]", text, re.I)
    if not match:
        return None
    return int(match.group(1))


def _section_type_from_heading(text: str) -> str | None:
    folded = _fold(text)
    if re.search(r"\bphan\s+iii\b", folded):
        return "short_answer"
    if re.search(r"\bphan\s+ii\b", folded):
        return "true_false"
    if re.search(r"\bphan\s+i\b", folded):
        return "single_choice"
    return None


def _is_section_heading(text: str) -> bool:
    return _section_type_from_heading(text) is not None


def _append_text(blocks: list[dict[str, Any]], text: str) -> None:
    if not text:
        return
    if blocks and blocks[-1]["type"] == "text":
        blocks[-1]["text"] += text
    else:
        blocks.append({"type": "text", "text": text})


def _merge_text_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for block in blocks:
        if block["type"] == "text":
            _append_text(merged, block["text"])
        else:
            merged.append(block)
    return merged


def _trim_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trimmed = list(blocks)
    while trimmed and trimmed[0]["type"] == "text" and not trimmed[0]["text"].strip():
        trimmed.pop(0)
    while trimmed and trimmed[-1]["type"] == "text" and not trimmed[-1]["text"].strip():
        trimmed.pop()
    if trimmed and trimmed[0]["type"] == "text":
        trimmed[0] = {**trimmed[0], "text": trimmed[0]["text"].lstrip()}
    if trimmed and trimmed[-1]["type"] == "text":
        trimmed[-1] = {**trimmed[-1], "text": trimmed[-1]["text"].rstrip()}
    return trimmed


def _blocks_text(blocks: list[dict[str, Any]]) -> str:
    return "".join(block["text"] for block in blocks if block["type"] == "text")


def _has_rich_content(blocks: list[dict[str, Any]]) -> bool:
    return any(block["type"] in {"image", "math"} for block in blocks)


def _clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return _clean_space(without_marks).lower()


def _normalize_true_false(value: str) -> str:
    normalized = value.strip().upper()
    if normalized.startswith("Đ") or normalized.startswith("D"):
        return "Đ"
    return "S"


def _relationship_target_to_docx_path(target: str) -> str:
    if not target:
        return ""
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("word", target))


def _write_placeholder_svg(path: Path, asset_id: str, extension: str) -> None:
    label = html.escape(f"{asset_id} {extension.upper()} placeholder")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="180" height="42" viewBox="0 0 180 42">'
        '<rect x="0.5" y="0.5" width="179" height="41" rx="4" fill="#fff7ed" stroke="#f97316"/>'
        f'<text x="90" y="25" text-anchor="middle" font-size="12" font-family="Arial" fill="#9a3412">{label}</text>'
        "</svg>"
    )
    path.write_text(svg, encoding="utf-8")


def _relpath(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _cell(table: list[list[str]], row: int, col: int) -> str:
    if row >= len(table) or col >= len(table[row]):
        return ""
    return table[row][col]


def _cell_from_row(row: list[str], col: int) -> str:
    if col >= len(row):
        return ""
    return row[col]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
