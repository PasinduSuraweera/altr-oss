"""Command-line entry points.

    altr make "Create a pitch deck about solar drones"
    altr render presentation examples/pitch.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openai import APIError, APIStatusError

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
    make.add_argument(
        "--tools", choices=["auto", "all", "create"], default="auto",
        help="which tool schemas to send the model: 'auto' adds the edit "
        "tools only for edit-shaped prompts (saves tokens on tight tiers); "
        "'all' always sends everything - use this on paid tiers",
    )
    make.add_argument(
        "--max-completion-tokens", type=int, default=None,
        help="cap the model's output tokens; also shrinks the request budget "
        "some providers count against per-minute limits (try 2500 on Groq's "
        "free tier for long documents)",
    )
    make.add_argument("--docx-template", default=None, help="template .docx for brand styling")
    make.add_argument("--pptx-template", default=None, help="template .pptx for brand styling")
    make.add_argument("--pdf", action="store_true", help="also export each file to PDF (needs LibreOffice)")

    mcp = sub.add_parser("mcp", help="serve the document tools over MCP (stdio)")
    mcp.add_argument("--out", default="output", help="output directory (default: ./output)")
    mcp.add_argument("--docx-template", default=None, help="template .docx for brand styling")
    mcp.add_argument("--pptx-template", default=None, help="template .pptx for brand styling")

    render = sub.add_parser("render", help="render a JSON spec to a file, no model involved")
    render.add_argument("type", choices=sorted(_RENDERERS))
    render.add_argument("spec", help="path to a JSON spec file")
    render.add_argument("--out", default="output", help="output directory (default: ./output)")
    render.add_argument("--template", default=None, help="template .docx/.pptx for brand styling")
    render.add_argument("--pdf", action="store_true", help="also export to PDF (needs LibreOffice)")

    args = parser.parse_args(argv)

    if args.command == "render":
        return _render(args)
    if args.command == "mcp":
        return _mcp(args)
    return _make(args)


def _mcp(args: argparse.Namespace) -> int:
    try:
        from .mcp_server import serve
    except ImportError as e:
        print(f"altr: {e}", file=sys.stderr)
        return 2
    templates = {}
    if args.docx_template:
        templates["docx"] = Path(args.docx_template)
    if args.pptx_template:
        templates["pptx"] = Path(args.pptx_template)
    serve(args.out, templates)
    return 0


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
            max_completion_tokens=args.max_completion_tokens,
            tools=args.tools,
            docx_template=args.docx_template,
            pptx_template=args.pptx_template,
        )
    except ValueError as e:
        print(f"altr: {e}", file=sys.stderr)
        return 2

    try:
        result = agent.run(args.prompt)
    except APIError as e:
        print(f"altr: the API rejected the request: {_api_error_message(e)}", file=sys.stderr)
        if _is_too_large(e):
            print(
                "altr: the request exceeds your tier's per-minute token limit and "
                "waiting will not help. Try --max-completion-tokens 2500, a shorter "
                "prompt, or a higher tier.",
                file=sys.stderr,
            )
        return 1
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


def _api_error_message(error: APIError) -> str:
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        inner = body.get("error", body)
        if isinstance(inner, dict) and inner.get("message"):
            return str(inner["message"])
    return str(error)


def _is_too_large(error: APIError) -> bool:
    """A 413 'request too large for TPM' can never succeed by waiting."""
    return isinstance(error, APIStatusError) and error.response.status_code == 413


if __name__ == "__main__":
    sys.exit(main())
