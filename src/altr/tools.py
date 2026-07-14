"""Tool-call definitions and dispatch.

`get_tools()` returns OpenAI-format tool definitions you can pass straight to
any chat-completions endpoint (Groq, Ollama, vLLM, ...). `dispatch()` executes
a tool call the model made and returns a JSON-safe result dict - errors are
returned rather than raised, so the model can read them and self-correct.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, NamedTuple

from pydantic import BaseModel, ValidationError

from . import editors
from .renderers import render_document, render_presentation, render_spreadsheet
from .schemas import (
    DocumentSpec,
    EditDocumentSpec,
    EditPresentationSpec,
    EditSpreadsheetSpec,
    PresentationSpec,
    ReadFileSpec,
    SpreadsheetSpec,
)


class _Tool(NamedTuple):
    spec_cls: type[BaseModel]
    description: str
    # (spec, out_dir, templates) -> JSON-safe outcome dict
    handler: Callable[[BaseModel, Path, dict[str, Path]], dict[str, Any]]


def _create(render, template_key: str | None):
    def handler(spec, out_dir: Path, templates: dict[str, Path]) -> dict[str, Any]:
        if template_key:
            path = render(spec, out_dir, template=templates.get(template_key))
        else:
            path = render(spec, out_dir)
        return {"ok": True, "file": str(path)}

    return handler


def _read(spec, out_dir: Path, templates) -> dict[str, Any]:
    path = editors.resolve_existing(spec.path, out_dir)
    return {"ok": True, "content": editors.read_office(path)}


def _edit(edit_fn):
    def handler(spec, out_dir: Path, templates) -> dict[str, Any]:
        path = editors.resolve_existing(spec.path, out_dir)
        return edit_fn(spec, path)

    return handler


_REGISTRY: dict[str, _Tool] = {
    "create_document": _Tool(
        DocumentSpec,
        "Create a Word document (.docx) from ordered content blocks: headings, "
        "paragraphs, bullet/numbered lists, tables, images, markdown, and page "
        "breaks.",
        _create(render_document, "docx"),
    ),
    "create_spreadsheet": _Tool(
        SpreadsheetSpec,
        "Create an Excel workbook (.xlsx) with one or more worksheets. Supports "
        "bold header rows, column widths, frozen headers, formulas (string cells "
        "starting with '='), and bar/line/pie charts of the sheet's data.",
        _create(render_spreadsheet, None),
    ),
    "create_presentation": _Tool(
        PresentationSpec,
        "Create a PowerPoint deck (.pptx) from slides: a title slide, section "
        "dividers, bulleted content slides, chart slides, and image slides, "
        "with optional speaker notes.",
        _create(render_presentation, "pptx"),
    ),
    "read_office_file": _Tool(
        ReadFileSpec,
        "Inspect an existing .docx/.xlsx/.pptx: returns its paragraphs, sheet "
        "data, or slides with the indexes the edit tools use. Always read a "
        "file before editing it.",
        _read,
    ),
    "edit_document": _Tool(
        EditDocumentSpec,
        "Edit an existing Word document in place: append content blocks, "
        "find/replace text, rewrite or delete a paragraph by index (from "
        "read_office_file).",
        _edit(editors.edit_document),
    ),
    "edit_spreadsheet": _Tool(
        EditSpreadsheetSpec,
        "Edit an existing Excel workbook in place: set cells by A1 reference "
        "(formulas allowed), append rows, or add a new worksheet. Note: "
        "existing charts cannot be preserved and will be dropped.",
        _edit(editors.edit_spreadsheet),
    ),
    "edit_presentation": _Tool(
        EditPresentationSpec,
        "Edit an existing PowerPoint deck in place: append slides, retitle a "
        "slide by index (from read_office_file), or find/replace text across "
        "slides.",
        _edit(editors.edit_presentation),
    ),
}


def _schema(spec_cls: type[BaseModel]) -> dict[str, Any]:
    return _strip_titles(spec_cls.model_json_schema())


def _strip_titles(node):
    """Drop pydantic's auto-generated 'title' annotations - they carry no
    meaning for the model and cost hundreds of prompt tokens per request.
    Property entries NAMED 'title' (dict values) are untouched."""
    if isinstance(node, dict):
        return {
            k: _strip_titles(v)
            for k, v in node.items()
            if not (k == "title" and isinstance(v, str))
        }
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


def get_tools(names: list[str] | None = None) -> list[dict[str, Any]]:
    """OpenAI-format tool definitions for the document skills.

    Pass `names` to send a subset - schemas are prompt tokens, and slim
    payloads matter on tight per-minute token budgets.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.description,
                "parameters": _schema(tool.spec_cls),
            },
        }
        for name, tool in _REGISTRY.items()
        if names is None or name in names
    ]


def get_tool_specs() -> list[tuple[str, str, dict[str, Any]]]:
    """(name, description, JSON schema) triples - handy for MCP servers."""
    return [
        (name, tool.description, _schema(tool.spec_cls))
        for name, tool in _REGISTRY.items()
    ]


def dispatch(
    name: str,
    arguments: str | dict[str, Any],
    out_dir: str | Path,
    templates: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Execute one tool call and return {"ok": True, ...} or an error dict.

    `templates` optionally maps 'docx'/'pptx' to a template file the renderer
    starts from, for brand styling.
    """
    tool = _REGISTRY.get(name)
    if tool is None:
        return {"ok": False, "error": f"unknown tool {name!r}"}

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"arguments are not valid JSON: {e}"}

    try:
        spec = tool.spec_cls.model_validate(arguments)
    except ValidationError as e:
        return {"ok": False, "error": f"invalid arguments: {e}"}

    try:
        return tool.handler(spec, Path(out_dir), templates or {})
    except Exception as e:  # surface renderer/editor failures to the model
        return {"ok": False, "error": f"failed: {e}"}
