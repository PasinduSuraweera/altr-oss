from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from ..schemas import PresentationSpec, Slide

# Layout indexes in the standard template. Custom templates must keep the
# stock layout order (0 title, 1 title+content, 2 section header, 5 title only).
_TITLE_LAYOUT = 0
_BULLETS_LAYOUT = 1
_SECTION_LAYOUT = 2
_TITLE_ONLY_LAYOUT = 5

_CHART_TYPES = {
    "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "pie": XL_CHART_TYPE.PIE,
}

# Body area below the title on a 10 x 7.5 inch slide.
_BODY = (Inches(0.8), Inches(1.8), Inches(8.4), Inches(5.0))


def render_presentation(
    spec: PresentationSpec, out_dir: Path, template: Path | None = None
) -> Path:
    from . import output_path

    prs = Presentation(str(template)) if template else Presentation()

    for slide_spec in spec.slides:
        slide = prs.slides.add_slide(prs.slide_layouts[_layout_index(slide_spec)])
        slide.shapes.title.text = slide_spec.title

        if slide_spec.layout in ("title", "section") and slide_spec.subtitle:
            slide.placeholders[1].text = slide_spec.subtitle

        if slide_spec.layout == "bullets" and slide_spec.bullets:
            body = slide.placeholders[1].text_frame
            for i, bullet in enumerate(slide_spec.bullets):
                para = body.paragraphs[0] if i == 0 else body.add_paragraph()
                para.text = bullet.text
                para.level = bullet.level

        if slide_spec.layout == "chart":
            _add_chart(slide, slide_spec)

        if slide_spec.layout == "image":
            _add_image(slide, slide_spec)

        if slide_spec.notes:
            slide.notes_slide.notes_text_frame.text = slide_spec.notes

    path = output_path(out_dir, spec.filename, ".pptx")
    prs.save(str(path))
    return path


def _layout_index(slide_spec: Slide) -> int:
    if slide_spec.layout == "title":
        return _TITLE_LAYOUT
    if slide_spec.layout == "section":
        return _SECTION_LAYOUT
    if slide_spec.layout in ("chart", "image"):
        return _TITLE_ONLY_LAYOUT
    return _BULLETS_LAYOUT


def _add_chart(slide, slide_spec: Slide) -> None:
    chart = slide_spec.chart
    data = CategoryChartData()
    data.categories = chart.categories
    for series in chart.series:
        # Pad or trim so every series aligns with the category axis.
        values = list(series.values[: len(chart.categories)])
        values += [0.0] * (len(chart.categories) - len(values))
        data.add_series(series.name, values)
    slide.shapes.add_chart(_CHART_TYPES[chart.kind], *_BODY, data)


def _add_image(slide, slide_spec: Slide) -> None:
    image_path = Path(slide_spec.image.path)
    if not image_path.is_file():
        raise FileNotFoundError(f"image not found: {slide_spec.image.path}")
    left, top, width, _ = _BODY
    slide.shapes.add_picture(str(image_path), left, top, width=width)
