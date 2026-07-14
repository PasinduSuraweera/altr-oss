"""Renderers turn validated specs into real files on disk."""

from __future__ import annotations

from pathlib import Path

from .docx import render_document
from .pptx import render_presentation
from .xlsx import render_spreadsheet

__all__ = ["render_document", "render_spreadsheet", "render_presentation", "output_path"]


def output_path(out_dir: Path, filename: str, ext: str) -> Path:
    """Resolve a model-supplied filename to a safe path inside out_dir.

    Only the base name is kept, so a hostile or confused model cannot write
    outside the output directory.
    """
    name = Path(filename.strip()).name or f"output{ext}"
    if not name.lower().endswith(ext):
        name += ext
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / name
