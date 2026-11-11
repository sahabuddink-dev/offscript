from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.services.document_processing.base import ExtractedItem, ProcessingError
from app.services.document_processing.vision import (
    describe_image,
    should_describe_image,
    vision_enabled,
)


def _cell_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def extract_xlsx(file_path: Path) -> list[ExtractedItem]:
    try:
        from openpyxl import load_workbook
        from openpyxl.utils import get_column_letter
        from openpyxl.utils.cell import range_boundaries
    except ImportError as error:
        raise ProcessingError("XLSX processing requires OpenPyXL.") from error
    try:
        workbook = load_workbook(file_path, read_only=False, data_only=False)
    except Exception as error:
        raise ProcessingError("The XLSX file is corrupted or could not be opened.") from error

    items: list[ExtractedItem] = []
    described_images = 0
    try:
        for worksheet in workbook.worksheets:
            table_ranges = [table.ref for table in worksheet.tables.values()]
            items.append(
                ExtractedItem(
                    content_type="worksheet",
                    content={
                        "name": worksheet.title,
                        "max_row": worksheet.max_row,
                        "max_column": worksheet.max_column,
                        "tables": table_ranges,
                    },
                    sheet_name=worksheet.title,
                    source={"parser": "openpyxl"},
                )
            )
            for table_index, table in enumerate(worksheet.tables.values(), start=1):
                min_column, min_row, max_column, max_row = range_boundaries(table.ref)
                rows = [
                    [
                        _cell_value(worksheet.cell(row=row, column=column).value)
                        for column in range(min_column, max_column + 1)
                    ]
                    for row in range(min_row, max_row + 1)
                ]
                if rows:
                    items.append(
                        ExtractedItem(
                            content_type="table",
                            content={
                                "name": table.displayName,
                                "headers": rows[0],
                                "rows": rows[1:],
                                "row_count": len(rows),
                                "column_count": max(map(len, rows), default=0),
                            },
                            sheet_name=worksheet.title,
                            cell_reference=table.ref,
                            source={
                                "parser": "openpyxl",
                                "table_index": table_index,
                            },
                        )
                    )

            for row in worksheet.iter_rows():
                cells = [
                    {
                        "reference": cell.coordinate,
                        "column": cell.column,
                        "value": _cell_value(cell.value),
                    }
                    for cell in row
                    if cell.value is not None
                ]
                if cells:
                    cell_references = [cell["reference"] for cell in cells]
                    items.append(
                        ExtractedItem(
                            content_type="row",
                            content={
                                "row_number": row[0].row,
                                "cells": cells,
                            },
                            sheet_name=worksheet.title,
                            cell_reference=f"{cell_references[0]}:{cell_references[-1]}",
                            source={"parser": "openpyxl"},
                        )
                    )

            if not table_ranges:
                populated_cells = [
                    cell
                    for row in worksheet.iter_rows()
                    for cell in row
                    if cell.value is not None
                ]
                if populated_cells:
                    min_row = min(cell.row for cell in populated_cells)
                    max_row = max(cell.row for cell in populated_cells)
                    min_column = min(cell.column for cell in populated_cells)
                    max_column = max(cell.column for cell in populated_cells)
                    if max_row > min_row and max_column > min_column:
                        table_rows = [
                            [
                                _cell_value(worksheet.cell(row=row, column=column).value)
                                for column in range(min_column, max_column + 1)
                            ]
                            for row in range(min_row, max_row + 1)
                        ]
                        if all(
                            sum(value is not None for value in row) >= 2
                            for row in table_rows
                        ):
                            items.append(
                                ExtractedItem(
                                    content_type="table",
                                    content={
                                        "headers": table_rows[0],
                                        "rows": table_rows[1:],
                                        "row_count": len(table_rows),
                                        "column_count": max(map(len, table_rows), default=0),
                                    },
                                    sheet_name=worksheet.title,
                                    cell_reference=(
                                        f"{get_column_letter(min_column)}{min_row}:"
                                        f"{get_column_letter(max_column)}{max_row}"
                                    ),
                                    source={
                                        "parser": "openpyxl",
                                        "table_detection": "inferred_used_range",
                                    },
                                )
                            )

            for chart_index, chart in enumerate(worksheet._charts, start=1):
                anchor = chart.anchor
                cell_reference = None
                if hasattr(anchor, "_from"):
                    cell_reference = worksheet.cell(
                        row=anchor._from.row + 1,
                        column=anchor._from.col + 1,
                    ).coordinate
                items.append(
                    ExtractedItem(
                        content_type="chart_reference",
                        content={"reference": f"{worksheet.title}-chart-{chart_index}"},
                        sheet_name=worksheet.title,
                        cell_reference=cell_reference,
                        source={"parser": "openpyxl", "chart_index": chart_index},
                    )
                )
            for image_index, image in enumerate(worksheet._images, start=1):
                anchor = image.anchor
                cell_reference = None
                if hasattr(anchor, "_from"):
                    cell_reference = worksheet.cell(
                        row=anchor._from.row + 1,
                        column=anchor._from.col + 1,
                    ).coordinate
                content: dict[str, Any] = {
                    "reference": f"{worksheet.title}-image-{image_index}"
                }
                if (
                    vision_enabled()
                    and should_describe_image(
                        image.width,
                        image.height,
                        described_images,
                    )
                ):
                    described_images += 1
                    image_bytes = image._data()
                    mime_type = (
                        "image/jpeg"
                        if image.format == "jpeg"
                        else f"image/{image.format}"
                    )
                    description = describe_image(image_bytes, mime_type)
                    if description:
                        content["description"] = description
                items.append(
                    ExtractedItem(
                        content_type="image_reference",
                        content=content,
                        sheet_name=worksheet.title,
                        cell_reference=cell_reference,
                        source={
                            "parser": "openpyxl",
                            "image_index": image_index,
                            "dimensions": {
                                "width": image.width,
                                "height": image.height,
                            },
                        },
                    )
                )
    finally:
        workbook.close()
    return items
