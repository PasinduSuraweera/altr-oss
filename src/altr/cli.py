"""Command-line entry points.

    altr make "Create a pitch deck about solar drones"
    altr render presentation examples/pitch.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import DEFAULT_MODEL, GROQ_BASE_URL, OfficeAgent
from .pdf import to_pdf
from .renderers import render_document, render_presentation, render_spreadsheet
from .schemas import DocumentSpec, PresentationSpec, SpreadsheetSpec

_RENDERERS = {
    "document": (DocumentSpec, render_document),
    "spreadsheet": (SpreadsheetSpec, render_spreadsheet),
    "presentation": (PresentationSpec, render_presentation),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="altr",
        description="Office document skills (docx/xlsx/pptx) for open-weight models.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    make = sub.add_parser("make", help="ask a model to create documents from a prompt")
    make.add_argument("prompt", help="what to create, in plain language")
    make.add_argument("--model", default=DEFAULT_MODEL)
    make.add_argument("--base-url", default=GROQ_BASE_URL, help="any OpenAI-compatible endpoint")
    make.add_argument("--api-key", default=None, help="defaults to $GROQ_API_KEY / $OPENAI_API_KEY")
    make.add_argument("--out", default="output", help="output directory (default: ./output)")
    make.add_argument("--max-rounds", type=int, default=8)
    make.add_argument("--temperature", type=float, default=0.3)
    make.add_argument("--docx-template", default=None, help="template .docx for brand styling")
    make.add_argument("--pptx-template", default=None, help="template .pptx for brand styling")
    make.add_argument("--pdf", action="store_true", help="also export each file to PDF (needs LibreOffice)")

    render = sub.add_parser("render", help="render a JSON spec to a file, no model involved")
    render.add_argument("type", choices=sorted(_RENDERERS))
    render.add_argument("spec", help="path to a JSON spec file")
    render.add_argument("--out", default="output", help="output directory (default: ./output)")
    render.add_argument("--template", default=None, help="template .docx/.pptx for brand styling")
    render.add_argument("--pdf", action="store_true", help="also export to PDF (needs LibreOffice)")

    args = parser.parse_args(argv)

    if args.command == "render":
        return _render(args)
    return _make(args)


def _render(args: argparse.Namespace) -> int:
    spec_cls, render_fn = _RENDERERS[args.type]
    spec = spec_cls.model_validate(json.loads(Path(args.spec).read_text()))
    if args.type == "spreadsheet":
        if args.template:
            print("altr: --template is not supported for spreadsheets", file=sys.stderr)
            return 2
        path = render_fn(spec, Path(args.out))
    else:
        template = Path(args.template) if args.template else None
        path = render_fn(spec, Path(args.out), template=template)
    print(f"created {path}")
    if args.pdf:
        print(f"created {to_pdf(path)}")
    return 0


def _make(args: argparse.Namespace) -> int:
    try:
        agent = OfficeAgent(
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            out_dir=args.out,
            max_rounds=args.max_rounds,
            temperature=args.temperature,
            docx_template=args.docx_template,
            pptx_template=args.pptx_template,
        )
    except ValueError as e:
        print(f"altr: {e}", file=sys.stderr)
        return 2

    result = agent.run(args.prompt)
    for path in result.files:
        print(f"created {path}")
        if args.pdf:
            print(f"created {to_pdf(path)}")
    if result.reply:
        print(result.reply)
    if not result.files:
        print("altr: the model created no files", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
