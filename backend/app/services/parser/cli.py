from __future__ import annotations

import argparse
import json
from pathlib import Path

from .docx_parser import parse_docx_exam
from .preview_renderer import render_exam_preview


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Azota-style math exam DOCX to JSON.")
    parser.add_argument("docx_path", type=Path)
    parser.add_argument("--assets-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--preview-output", type=Path, default=None)
    parser.add_argument("--convert-images", action="store_true")
    args = parser.parse_args()

    parsed = parse_docx_exam(
        args.docx_path,
        assets_dir=args.assets_dir,
        convert_images=args.convert_images,
    )
    payload = json.dumps(parsed, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    if args.preview_output:
        render_exam_preview(parsed, args.preview_output)


if __name__ == "__main__":
    main()
