from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ..schemas import Sheet, SpreadsheetSpec

_CHART_CLASSES = {"bar": BarChart, "line": LineChart, "pie": PieChart}
_CHART_ROWS = 15  # vertical space to leave per chart when stacking


def render_spreadsheet(spec: SpreadsheetSpec, out_dir: Path) -> Path:
    from . import output_path

    wb = Workbook()
    wb.remove(wb.active)

    for sheet in spec.sheets:
        ws = wb.create_sheet(title=sheet.name)
        first_data_row = 1
        if sheet.columns:
            for i, col in enumerate(sheet.columns, start=1):
                cell = ws.cell(row=1, column=i, value=col.header)
                cell.font = Font(bold=True)
                if col.width:
                    ws.column_dimensions[get_column_letter(i)].width = col.width
            if sheet.freeze_header:
                ws.freeze_panes = "A2"
            first_data_row = 2

        for r, row in enumerate(sheet.rows, start=first_data_row):
            for c, value in enumerate(row, start=1):
                ws.cell(row=r, column=c, value=value)

        _add_charts(ws, sheet, first_data_row)

    path = output_path(out_dir, spec.filename, ".xlsx")
    wb.save(str(path))
    return path


def _add_charts(ws: Worksheet, sheet: Sheet, first_data_row: int) -> None:
    if not sheet.charts or not sheet.rows:
        return
    last_row = first_data_row + len(sheet.rows) - 1
    data_cols = max(len(row) for row in sheet.rows)
    anchor_col = get_column_letter(data_cols + 2)

    for i, chart_spec in enumerate(sheet.charts):
        chart = _CHART_CLASSES[chart_spec.kind]()
        chart.title = chart_spec.title
        has_header = bool(sheet.columns)
        for col in chart_spec.value_columns:
            data = Reference(
                ws,
                min_col=col,
                min_row=1 if has_header else first_data_row,
                max_row=last_row,
            )
            chart.add_data(data, titles_from_data=has_header)
        categories = Reference(
            ws, min_col=chart_spec.label_column, min_row=first_data_row, max_row=last_row
        )
        chart.set_categories(categories)
        ws.add_chart(chart, f"{anchor_col}{2 + i * _CHART_ROWS}")
