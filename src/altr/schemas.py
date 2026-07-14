"""Pydantic specs for the three document types.

These models serve double duty: they validate what the model sends, and their
JSON schemas become the tool-call parameter schemas the model sees. Keep the
field descriptions model-facing - they are effectively prompt text.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

ChartType = Literal["bar", "line", "pie"]

# --- Word documents (.docx) -------------------------------------------------


class Heading(BaseModel):
    type: Literal["heading"] = "heading"
    level: int = Field(1, ge=1, le=9, description="1 is the largest heading.")
    text: str


class Paragraph(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str = Field(
        description="Supports inline markdown: **bold**, *italic*, `code`."
    )


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


class Image(BaseModel):
    type: Literal["image"] = "image"
    path: str = Field(
        description="Path to an existing local image file (.png/.jpg). Only "
        "reference files the user explicitly told you about."
    )
    width_inches: float | None = Field(None, gt=0, le=10)
    caption: str | None = None


class Markdown(BaseModel):
    type: Literal["markdown"] = "markdown"
    text: str = Field(
        description="Markdown converted to document content. Supports #-headings, "
        "-/1. lists, | pipe tables |, paragraphs, and inline **bold**/*italic*/`code`."
    )


class PageBreak(BaseModel):
    type: Literal["page_break"] = "page_break"


Block = Annotated[
    Union[Heading, Paragraph, BulletList, NumberedList, Table, Image, Markdown, PageBreak],
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


class SheetChart(BaseModel):
    """A chart embedded in a worksheet, built from the sheet's own data."""

    kind: ChartType = "bar"
    title: str
    label_column: int = Field(
        1, ge=1, description="1-based index of the column holding category labels."
    )
    value_columns: list[int] = Field(
        default_factory=list,
        description="1-based indexes of numeric columns to plot as series. "
        "Leave empty to plot every numeric column.",
    )


class Sheet(BaseModel):
    name: str = Field(max_length=31, description="Worksheet tab name.")
    columns: list[Column] = Field(
        default_factory=list, description="Header row; rendered bold."
    )
    rows: list[list[Cell]] = Field(
        min_length=1,
        description="Data rows. String cells starting with '=' are Excel formulas, "
        "e.g. '=SUM(B2:B10)'.",
    )
    freeze_header: bool = Field(True, description="Keep the header row visible on scroll.")
    charts: list[SheetChart] = Field(
        default_factory=list,
        description="Charts plotting this sheet's data, placed beside it.",
    )


class SpreadsheetSpec(BaseModel):
    """An Excel workbook with one or more worksheets."""

    filename: str = Field(description="Output file name, e.g. 'budget.xlsx'.")
    sheets: list[Sheet] = Field(min_length=1)


# --- Presentations (.pptx) --------------------------------------------------


class BulletPoint(BaseModel):
    text: str
    level: int = Field(0, ge=0, le=4, description="Indent level; 0 is top level.")


class ChartSeries(BaseModel):
    name: str
    values: list[float] = Field(min_length=1)


class SlideChart(BaseModel):
    """A chart drawn on a slide from inline data."""

    kind: ChartType = "bar"
    categories: list[str] = Field(min_length=1)
    series: list[ChartSeries] = Field(
        min_length=1,
        description="Each series must have exactly one value per category.",
    )


class SlideImage(BaseModel):
    path: str = Field(
        description="Path to an existing local image file (.png/.jpg). Only "
        "reference files the user explicitly told you about."
    )


class Slide(BaseModel):
    layout: Literal["title", "bullets", "section", "chart", "image"] = Field(
        "bullets",
        description="'title' for the opening slide, 'section' for a divider, "
        "'bullets' for a regular content slide, 'chart' for a chart slide, "
        "'image' for a full-width image slide.",
    )
    title: str
    subtitle: str | None = Field(None, description="Only used by title/section layouts.")
    bullets: list[str | BulletPoint] = Field(
        default_factory=list,
        description="Body content for the 'bullets' layout: plain strings, or "
        "{text, level} objects for indented bullets.",
    )
    chart: SlideChart | None = Field(None, description="Required for the 'chart' layout.")
    image: SlideImage | None = Field(None, description="Required for the 'image' layout.")
    notes: str | None = Field(None, description="Speaker notes for this slide.")

    @model_validator(mode="after")
    def _check_layout_content(self) -> "Slide":
        self.bullets = [
            b if isinstance(b, BulletPoint) else BulletPoint(text=b)
            for b in self.bullets
        ]
        if self.layout == "chart" and self.chart is None:
            raise ValueError("a 'chart' slide needs the 'chart' field")
        if self.layout == "image" and self.image is None:
            raise ValueError("an 'image' slide needs the 'image' field")
        return self


class PresentationSpec(BaseModel):
    """A PowerPoint deck built from a list of slides."""

    filename: str = Field(description="Output file name, e.g. 'pitch.pptx'.")
    slides: list[Slide] = Field(min_length=1)


# --- Reading and editing existing files --------------------------------------

_PATH_DESC = (
    "Path to an existing file the user told you about, e.g. 'output/report.docx'."
)


class ReadFileSpec(BaseModel):
    """Inspect an existing .docx/.xlsx/.pptx before editing it."""

    path: str = Field(description=_PATH_DESC)


class AppendBlocks(BaseModel):
    """Add new content blocks at the end of the document."""

    op: Literal["append_blocks"] = "append_blocks"
    blocks: list[Block] = Field(min_length=1)


class ReplaceText(BaseModel):
    """Replace every occurrence of a phrase throughout the document."""

    op: Literal["replace_text"] = "replace_text"
    find: str = Field(min_length=1)
    replace: str


class SetParagraph(BaseModel):
    """Rewrite one paragraph, keeping its style."""

    op: Literal["set_paragraph"] = "set_paragraph"
    index: int = Field(ge=0, description="Paragraph index from read_office_file.")
    text: str


class DeleteParagraph(BaseModel):
    op: Literal["delete_paragraph"] = "delete_paragraph"
    index: int = Field(ge=0, description="Paragraph index from read_office_file.")


DocEdit = Annotated[
    Union[AppendBlocks, ReplaceText, SetParagraph, DeleteParagraph],
    Field(discriminator="op"),
]


class EditDocumentSpec(BaseModel):
    """Edits applied in order to an existing Word document."""

    path: str = Field(description=_PATH_DESC)
    edits: list[DocEdit] = Field(min_length=1)


class SetCells(BaseModel):
    """Write values into individual cells by A1-style reference."""

    op: Literal["set_cells"] = "set_cells"
    sheet: str = Field(description="Worksheet name from read_office_file.")
    cells: dict[str, Cell] = Field(
        min_length=1,
        description="A1-style refs to values, e.g. {\"B2\": 120, \"C7\": \"=SUM(C2:C6)\"}.",
    )


class AppendRows(BaseModel):
    """Add data rows after the last used row of a worksheet."""

    op: Literal["append_rows"] = "append_rows"
    sheet: str = Field(description="Worksheet name from read_office_file.")
    rows: list[list[Cell]] = Field(min_length=1)


class AddSheet(BaseModel):
    """Add a whole new worksheet to the workbook."""

    op: Literal["add_sheet"] = "add_sheet"
    sheet: Sheet


SheetEdit = Annotated[
    Union[SetCells, AppendRows, AddSheet], Field(discriminator="op")
]


class EditSpreadsheetSpec(BaseModel):
    """Edits applied in order to an existing Excel workbook."""

    path: str = Field(description=_PATH_DESC)
    edits: list[SheetEdit] = Field(min_length=1)


class AppendSlides(BaseModel):
    """Add new slides at the end of the deck."""

    op: Literal["append_slides"] = "append_slides"
    slides: list[Slide] = Field(min_length=1)


class SetSlideTitle(BaseModel):
    op: Literal["set_slide_title"] = "set_slide_title"
    index: int = Field(ge=0, description="Slide index from read_office_file.")
    title: str


class ReplaceSlideText(BaseModel):
    """Replace every occurrence of a phrase across all slides."""

    op: Literal["replace_text"] = "replace_text"
    find: str = Field(min_length=1)
    replace: str


SlideEdit = Annotated[
    Union[AppendSlides, SetSlideTitle, ReplaceSlideText], Field(discriminator="op")
]


class EditPresentationSpec(BaseModel):
    """Edits applied in order to an existing PowerPoint deck."""

    path: str = Field(description=_PATH_DESC)
    edits: list[SlideEdit] = Field(min_length=1)
