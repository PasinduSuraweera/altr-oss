"""PDF export via LibreOffice's headless converter."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def soffice_available() -> bool:
    return _soffice() is not None


def _soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def to_pdf(path: str | Path, out_dir: str | Path | None = None) -> Path:
    """Convert a docx/xlsx/pptx file to PDF. Requires LibreOffice on PATH."""
    soffice = _soffice()
    if soffice is None:
        raise RuntimeError(
            "PDF export requires LibreOffice: install it so 'soffice' is on PATH"
        )
    path = Path(path)
    out_dir = Path(out_dir) if out_dir else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(path)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    pdf_path = out_dir / (path.stem + ".pdf")
    if result.returncode != 0 or not pdf_path.is_file():
        detail = result.stderr.strip() or result.stdout.strip() or "no output produced"
        raise RuntimeError(f"PDF conversion failed for {path.name}: {detail}")
    return pdf_path
