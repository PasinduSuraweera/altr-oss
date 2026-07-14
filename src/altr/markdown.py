"""A small markdown-to-blocks converter.

Supports the subset that maps cleanly onto document blocks: #-headings,
bullet (-/*) and numbered (1.) lists, pipe tables, and paragraphs. Inline
formatting (**bold**, *italic*, `code`) is left in the text; the docx
renderer turns it into styled runs.
"""

from __future__ import annotations

import re

from .schemas import BulletList, Heading, NumberedList, Paragraph, Table

_HEADING = re.compile(r"^(#{1,9})\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")
_NUMBERED = re.compile(r"^\d+[.)]\s+(.*)$")
_TABLE_DIVIDER = re.compile(r"^\|?[\s:|-]+\|?$")

MarkdownBlock = Heading | Paragraph | BulletList | NumberedList | Table


def markdown_to_blocks(text: str) -> list[MarkdownBlock]:
    """Convert markdown text into document blocks."""
    blocks: list[MarkdownBlock] = []
    paragraph: list[str] = []
    bullets: list[str] = []
    numbered: list[str] = []
    table: list[list[str]] = []

    def flush() -> None:
        nonlocal paragraph, bullets, numbered, table
        if paragraph:
            blocks.append(Paragraph(text=" ".join(paragraph)))
            paragraph = []
        if bullets:
            blocks.append(BulletList(items=bullets))
            bullets = []
        if numbered:
            blocks.append(NumberedList(items=numbered))
            numbered = []
        if table:
            blocks.append(Table(headers=table[0], rows=table[1:]))
            table = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue

        if m := _HEADING.match(line):
            flush()
            blocks.append(Heading(level=len(m.group(1)), text=m.group(2).strip()))
            continue

        if line.startswith("|") and "|" in line[1:]:
            if _TABLE_DIVIDER.match(line):
                continue  # the |---|---| row under the header
            if paragraph or bullets or numbered:
                flush()
            cells = [c.strip() for c in line.strip("|").split("|")]
            table.append(cells)
            continue

        if m := _BULLET.match(line):
            if paragraph or numbered or table:
                flush()
            bullets.append(m.group(1).strip())
            continue

        if m := _NUMBERED.match(line):
            if paragraph or bullets or table:
                flush()
            numbered.append(m.group(1).strip())
            continue

        if bullets or numbered or table:
            flush()
        paragraph.append(line)

    flush()
    return blocks


_INLINE = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`)")


def split_inline(text: str) -> list[tuple[str, str]]:
    """Split text into (style, text) runs; style is '', 'bold', 'italic', or 'code'."""
    runs: list[tuple[str, str]] = []
    for part in _INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            runs.append(("bold", part[2:-2]))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            runs.append(("code", part[1:-1]))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            runs.append(("italic", part[1:-1]))
        else:
            runs.append(("", part))
    return runs
