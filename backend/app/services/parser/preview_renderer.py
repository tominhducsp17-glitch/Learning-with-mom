from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any


SECTION_NAMES = {
    "single_choice": "PHẦN I - Trắc nghiệm A/B/C/D",
    "true_false": "PHẦN II - Đúng/Sai",
    "short_answer": "PHẦN III - Trả lời ngắn",
}


def render_exam_preview(parsed_exam: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_document(parsed_exam, output), encoding="utf-8")
    return output


def _render_document(parsed_exam: dict[str, Any], output_path: Path) -> str:
    title = html.escape(parsed_exam.get("title") or "Parsed Exam")
    counts = {
        section["type"]: len(section.get("questions", []))
        for section in parsed_exam.get("sections", [])
    }
    warnings = parsed_exam.get("warnings", [])
    warning_html = "".join(_render_warning(warning) for warning in warnings)
    sections_html = "".join(_render_section(section, output_path) for section in parsed_exam.get("sections", []))
    asset_count = len(parsed_exam.get("assets", []))

    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: #1f2937;
      background: #f8fafc;
      line-height: 1.55;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid #d1d5db;
      padding: 20px 28px;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 22px;
      letter-spacing: 0;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 13px;
    }}
    .pill {{
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      padding: 2px 9px;
      background: #f8fafc;
    }}
    main {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 22px;
    }}
    .warning {{
      border-left: 4px solid #f97316;
      background: #fff7ed;
      padding: 10px 12px;
      margin-bottom: 10px;
      font-size: 14px;
    }}
    section {{
      background: #ffffff;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      margin: 18px 0;
      padding: 18px;
    }}
    h2 {{
      font-size: 18px;
      margin: 0 0 14px;
      letter-spacing: 0;
    }}
    article {{
      border-top: 1px solid #e5e7eb;
      padding: 14px 0;
    }}
    article:first-of-type {{
      border-top: 0;
    }}
    .question-title {{
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .blocks {{
      white-space: pre-wrap;
    }}
    .inline-asset {{
      display: inline-block;
      vertical-align: middle;
      margin: 0 2px;
    }}
    .question-illustration {{
      display: block;
      width: auto;
      max-width: 100%;
      height: auto;
      margin: 12px 0 16px;
      vertical-align: initial;
    }}
    .option, .statement {{
      margin: 6px 0 0 18px;
    }}
    .answer {{
      margin-top: 8px;
      font-size: 13px;
      color: #065f46;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <div class="meta">
      <span class="pill">PHẦN I: {counts.get("single_choice", 0)} câu</span>
      <span class="pill">PHẦN II: {counts.get("true_false", 0)} câu</span>
      <span class="pill">PHẦN III: {counts.get("short_answer", 0)} câu</span>
      <span class="pill">Assets: {asset_count}</span>
      <span class="pill">Warnings: {len(warnings)}</span>
    </div>
  </header>
  <main>
    {warning_html}
    {sections_html}
  </main>
</body>
</html>
"""


def _render_warning(warning: dict[str, Any]) -> str:
    code = html.escape(str(warning.get("code", "WARNING")))
    message = html.escape(str(warning.get("message", "")))
    return f'<div class="warning"><strong>{code}</strong>: {message}</div>'


def _render_section(section: dict[str, Any], output_path: Path) -> str:
    section_type = section.get("type", "")
    title = html.escape(SECTION_NAMES.get(section_type, section.get("title", section_type)))
    questions = "".join(_render_question(section_type, question, output_path) for question in section.get("questions", []))
    return f"<section><h2>{title}</h2>{questions}</section>"


def _render_question(section_type: str, question: dict[str, Any], output_path: Path) -> str:
    number = html.escape(str(question.get("number", "")))
    prompt = _render_blocks(question.get("prompt_blocks", []), output_path)
    answer = html.escape(str(question.get("correct_answer", "")))
    body = f'<div class="question-title">Câu {number}</div><div class="blocks">{prompt}</div>'

    if section_type == "single_choice":
        for label, blocks in question.get("options", {}).items():
            body += f'<div class="option"><strong>{html.escape(label)}.</strong> {_render_blocks(blocks, output_path)}</div>'
    elif section_type == "true_false":
        for label, blocks in question.get("statements", {}).items():
            item_answer = html.escape(str((question.get("correct_answer") or {}).get(label, "")))
            body += (
                f'<div class="statement"><strong>{html.escape(label)}.</strong> '
                f'{_render_blocks(blocks, output_path)} <span class="answer">[{item_answer}]</span></div>'
            )
        answer = ""

    if answer:
        body += f'<div class="answer">Đáp án: {answer}</div>'
    return f"<article>{body}</article>"


def _render_blocks(blocks: list[dict[str, Any]], output_path: Path) -> str:
    rendered: list[str] = []
    for block in blocks:
        if block.get("type") == "text":
            rendered.append(html.escape(str(block.get("text", ""))))
        elif block.get("type") == "image":
            src = _image_src(str(block.get("render_path") or ""), output_path)
            alt = html.escape(str(block.get("asset_id", "inline asset")))
            style = _image_style(block)
            css_class = "question-illustration" if block.get("display_mode") == "block" else "inline-asset"
            rendered.append(f'<img class="{css_class}" src="{src}" alt="{alt}" title="{alt}"{style}>')
    return "".join(rendered)


def _image_style(block: dict[str, Any]) -> str:
    width = block.get("display_width_px")
    height = block.get("display_height_px")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        return ""
    if block.get("display_mode") == "block":
        return f' style="width:{width:.2f}px;max-width:100%;height:auto"'
    return f' style="width:{width:.2f}px;height:{height:.2f}px"'


def _image_src(render_path: str, output_path: Path) -> str:
    if not render_path:
        return ""
    target = Path(render_path)
    if not target.is_absolute():
        target = Path.cwd() / target
    relative = os.path.relpath(target.resolve(), output_path.parent.resolve())
    return html.escape(Path(relative).as_posix())
