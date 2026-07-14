"""Tool-call definitions and dispatch.

`get_tools()` returns OpenAI-format tool definitions you can pass straight to
any chat-completions endpoint (Groq, Ollama, vLLM, ...). `dispatch()` executes
a tool call the model made and returns a JSON-safe result dict - errors are
returned rather than raised, so the model can read them and self-correct.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from .renderers import render_document, render_presentation, render_spreadsheet
from .schemas import DocumentSpec, PresentationSpec, SpreadsheetSpec

_REGISTRY: dict[str, tuple[type[BaseModel], Any, str]] = {
    "create_document": (
        DocumentSpec,
        render_document,
        "Create a Word document (.docx) from ordered content blocks: headings, "
        "paragraphs, bullet/numbered lists, tables, and page breaks.",
    ),
    "create_spreadsheet": (
        SpreadsheetSpec,
        render_spreadsheet,
        "Create an Excel workbook (.xlsx) with one or more worksheets. Supports "
        "bold header rows, column widths, frozen headers, and formulas "
        "(string cells starting with '=').",
    ),
    "create_presentation": (
        PresentationSpec,
        render_presentation,
        "Create a PowerPoint deck (.pptx) from slides: a title slide, section "
        "dividers, and bulleted content slides with optional speaker notes.",
    ),
}


def get_tools() -> list[dict[str, Any]]:
    """OpenAI-format tool definitions for the three document skills."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": spec.model_json_schema(),
            },
        }
        for name, (spec, _, description) in _REGISTRY.items()
    ]


def dispatch(name: str, arguments: str | dict[str, Any], out_dir: str | Path) -> dict[str, Any]:
    """Execute one tool call and return {"ok": True, "file": path} or an error."""
    entry = _REGISTRY.get(name)
    if entry is None:
        return {"ok": False, "error": f"unknown tool {name!r}"}
    spec_cls, render, _ = entry

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"arguments are not valid JSON: {e}"}

    try:
        spec = spec_cls.model_validate(arguments)
    except ValidationError as e:
        return {"ok": False, "error": f"invalid arguments: {e}"}

    try:
        path = render(spec, Path(out_dir))
    except Exception as e:  # surface renderer failures to the model
        return {"ok": False, "error": f"failed to render: {e}"}
    return {"ok": True, "file": str(path)}
