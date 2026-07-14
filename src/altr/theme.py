"""The default visual theme shared by all three renderers.

One restrained, brand-neutral scheme: near-black ink, a deep blue accent, and
a colorblind-safe categorical palette for chart series (fixed slot order - the
ordering is the CVD-safety mechanism, so never reshuffle or cycle it).
"""

from __future__ import annotations

# Chart series colors, assigned to series in this exact order.
SERIES = [
    "2A78D6",  # blue
    "1BAF7A",  # aqua
    "EDA100",  # yellow
    "008300",  # green
    "4A3AA7",  # violet
    "E34948",  # red
    "E87BA4",  # magenta
    "EB6834",  # orange
]

ACCENT = "2A78D6"  # structural accent: rules, bars, links
ACCENT_DEEP = "184F95"  # headings, slide titles
ACCENT_DARK = "0D366B"  # dark backdrop (title slides)
ACCENT_TINT = "9EC5F4"  # light accent on dark backdrops

INK = "1F1F1F"  # body text
INK_SECONDARY = "52514E"  # subtitles, captions
INK_MUTED = "898781"  # axis labels, footers
GRIDLINE = "E1E0D9"  # hairline grid / table borders
ROW_BAND = "F4F4F1"  # zebra fill for table/sheet rows
HEADER_FILL = "184F95"  # table and sheet header row fill (white text on top)
