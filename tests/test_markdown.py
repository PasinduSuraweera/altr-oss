from altr.markdown import markdown_to_blocks, split_inline
from altr.schemas import BulletList, Heading, NumberedList, Paragraph, Table

SAMPLE = """\
# Title

Intro paragraph over
two lines.

## Details

- first
- second

1. step one
2. step two

| Name | Value |
|------|-------|
| a    | 1     |
| b    | 2     |
"""


def test_markdown_to_blocks():
    blocks = markdown_to_blocks(SAMPLE)
    kinds = [type(b) for b in blocks]
    assert kinds == [Heading, Paragraph, Heading, BulletList, NumberedList, Table]

    heading = blocks[0]
    assert heading.level == 1 and heading.text == "Title"
    assert blocks[1].text == "Intro paragraph over two lines."
    assert blocks[2].level == 2
    assert blocks[3].items == ["first", "second"]
    assert blocks[4].items == ["step one", "step two"]
    table = blocks[5]
    assert table.headers == ["Name", "Value"]
    assert table.rows == [["a", "1"], ["b", "2"]]


def test_split_inline():
    runs = split_inline("plain **bold** and *ital* and `code` end")
    assert runs == [
        ("", "plain "),
        ("bold", "bold"),
        ("", " and "),
        ("italic", "ital"),
        ("", " and "),
        ("code", "code"),
        ("", " end"),
    ]


def test_split_inline_plain_text_unchanged():
    assert split_inline("no styling here") == [("", "no styling here")]
