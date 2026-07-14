"""Pydantic specs for the three document types.

These models serve double duty: they validate what the model sends, and their
JSON schemas become the tool-call parameter schemas the model sees. Keep the
field descriptions model-facing - they are effectively prompt text.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

# --- Word documents (.docx) -------------------------------------------------


class Heading(BaseModel):
    type: Literal["heading"] = "heading"
    level: int = Field(1, ge=1, le=9, description="1 is the largest heading.")
    text: str


class Paragraph(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str


class BulletList(BaseModel):
    type: Literal["bullet_list"] = "bullet_list"
    items: list[str] = Field(min_length=1)


class NumberedList(BaseModel):
    type: Literal["numbered_list"] = "numbered_list"
    items: list[str] = Field(min_length=1)


class Table(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str] = Field(min_length=1)
    rows: list[list[str]] = Field(
        default_factory=list,
        description="Each row must have the same number of cells as headers.",
    )


class PageBreak(BaseModel):
    type: Literal["page_break"] = "page_break"


Block = Annotated[
    Union[Heading, Paragraph, BulletList, NumberedList, Table, PageBreak],
    Field(discriminator="type"),
]


class DocumentSpec(BaseModel):
    """A Word document composed of ordered content blocks."""

    filename: str = Field(description="Output file name, e.g. 'report.docx'.")
    title: str | None = Field(None, description="Optional document title heading.")
    blocks: list[Block] = Field(min_length=1, description="Document content, in order.")


# --- Spreadsheets (.xlsx) ---------------------------------------------------

Cell = Union[str, int, float, bool, None]


class Column(BaseModel):
    header: str
    width: float | None = Field(None, gt=0, description="Column width in characters.")


class Sheet(BaseModel):
    name: str = Field(max_length=31, description="Worksheet tab name.")
    columns: list[Column] = Field(
        default_factory=list, description="Header row; rendered bold."
    )
    rows: list[list[Cell]] = Field(
        default_factory=list,
        description="Data rows. String cells starting with '=' are Excel formulas, "
        "e.g. '=SUM(B2:B10)'.",
    )
    freeze_header: bool = Field(True, description="Keep the header row visible on scroll.")


class SpreadsheetSpec(BaseModel):
    """An Excel workbook with one or more worksheets."""

    filename: str = Field(description="Output file name, e.g. 'budget.xlsx'.")
    sheets: list[Sheet] = Field(min_length=1)


# --- Presentations (.pptx) --------------------------------------------------


class BulletPoint(BaseModel):
    text: str
    level: int = Field(0, ge=0, le=4, description="Indent level; 0 is top level.")


class Slide(BaseModel):
    layout: Literal["title", "bullets", "section"] = Field(
        "bullets",
        description="'title' for the opening slide, 'section' for a divider, "
        "'bullets' for a regular content slide.",
    )
    title: str
    subtitle: str | None = Field(None, description="Only used by title/section layouts.")
    bullets: list[BulletPoint] = Field(
        default_factory=list, description="Body content for the 'bullets' layout."
    )
    notes: str | None = Field(None, description="Speaker notes for this slide.")


class PresentationSpec(BaseModel):
    """A PowerPoint deck built from a list of slides."""

    filename: str = Field(description="Output file name, e.g. 'pitch.pptx'.")
    slides: list[Slide] = Field(min_length=1)
