from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Inches

from ..markdown import markdown_to_blocks, split_inline
from ..schemas import (
    BulletList,
    DocumentSpec,
    Heading,
    Image,
    Markdown,
    NumberedList,
    PageBreak,
    Paragraph,
    Table,
)


def render_document(
    spec: DocumentSpec, out_dir: Path, template: Path | None = None
) -> Path:
    from . import output_path

    doc = Document(str(template)) if template else Document()
    if spec.title:
        doc.add_heading(spec.title, 0)

    for block in spec.blocks:
        _add_block(doc, block)

    path = output_path(out_dir, spec.filename, ".docx")
    doc.save(str(path))
    return path


def _add_block(doc: Document, block) -> None:
    if isinstance(block, Heading):
        doc.add_heading(block.text, block.level)
    elif isinstance(block, Paragraph):
        _add_styled_paragraph(doc, block.text)
    elif isinstance(block, BulletList):
        for item in block.items:
            _add_styled_paragraph(doc, item, style="List Bullet")
    elif isinstance(block, NumberedList):
        for item in block.items:
            _add_styled_paragraph(doc, item, style="List Number")
    elif isinstance(block, Table):
        table = doc.add_table(rows=1, cols=len(block.headers))
        table.style = "Table Grid"
        for i, header in enumerate(block.headers):
            run = table.rows[0].cells[i].paragraphs[0].add_run(header)
            run.bold = True
        for row in block.rows:
            cells = table.add_row().cells
            for i, value in enumerate(row[: len(block.headers)]):
                cells[i].text = value
    elif isinstance(block, Image):
        image_path = Path(block.path)
        if not image_path.is_file():
            raise FileNotFoundError(f"image not found: {block.path}")
        width = Inches(block.width_inches) if block.width_inches else None
        doc.add_picture(str(image_path), width=width)
        if block.caption:
            doc.add_paragraph(block.caption, style="Caption")
    elif isinstance(block, Markdown):
        for sub_block in markdown_to_blocks(block.text):
            _add_block(doc, sub_block)
    elif isinstance(block, PageBreak):
        doc.add_page_break()


def _add_styled_paragraph(doc: Document, text: str, style: str | None = None) -> None:
    """Add a paragraph, turning inline **bold**/*italic*/`code` into runs."""
    para = doc.add_paragraph(style=style)
    for kind, part in split_inline(text):
        run = para.add_run(part)
        if kind == "bold":
            run.bold = True
        elif kind == "italic":
            run.italic = True
        elif kind == "code":
            run.font.name = "Courier New"
