from pathlib import Path
from typing import Any

from app.services.document_processing.base import ExtractedItem, ProcessingError, text_item
from app.services.document_processing.vision import (
    describe_image,
    should_describe_image,
    vision_enabled,
)


def extract_pptx(file_path: Path) -> list[ExtractedItem]:
    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
    except ImportError as error:
        raise ProcessingError("PPTX processing requires python-pptx.") from error
    try:
        presentation = Presentation(file_path)
    except Exception as error:
        raise ProcessingError("The PPTX file is corrupted or could not be opened.") from error

    items: list[ExtractedItem] = []
    described_images = 0

    for slide_number, slide in enumerate(presentation.slides, start=1):
        title_shape = slide.shapes.title
        if title_shape is not None:
            title = text_item(
                title_shape.text,
                content_type="slide_title",
                slide_number=slide_number,
                source={"parser": "python-pptx", "shape_id": title_shape.shape_id},
            )
            if title:
                items.append(title)

        for shape_index, shape in enumerate(slide.shapes, start=1):
            if shape is title_shape:
                continue
            if shape.has_text_frame:
                item = text_item(
                    "\n".join(paragraph.text for paragraph in shape.text_frame.paragraphs),
                    slide_number=slide_number,
                    source={"parser": "python-pptx", "shape_id": shape.shape_id},
                )
                if item:
                    items.append(item)
            if shape.has_table:
                rows = [
                    [cell.text.strip() for cell in row.cells]
                    for row in shape.table.rows
                ]
                if rows:
                    items.append(
                        ExtractedItem(
                            content_type="table",
                            content={
                                "headers": rows[0],
                                "rows": rows[1:],
                                "row_count": len(rows),
                                "column_count": max(map(len, rows), default=0),
                            },
                            slide_number=slide_number,
                            source={"parser": "python-pptx", "shape_id": shape.shape_id},
                        )
                    )
            if shape.has_chart:
                chart = shape.chart
                items.append(
                    ExtractedItem(
                        content_type="chart_reference",
                        content={
                            "reference": f"slide-{slide_number}-chart-{shape_index}",
                            "chart_type": str(chart.chart_type),
                            "series": [series.name for series in chart.series],
                        },
                        slide_number=slide_number,
                        source={
                            "parser": "python-pptx",
                            "shape_id": shape.shape_id,
                        },
                    )
                )
            elif (
                shape.shape_type == MSO_SHAPE_TYPE.DIAGRAM
                and not shape.has_table
            ):
                items.append(
                    ExtractedItem(
                        content_type="diagram_reference",
                        content={"reference": f"slide-{slide_number}-diagram-{shape_index}"},
                        slide_number=slide_number,
                        source={
                            "parser": "python-pptx",
                            "shape_id": shape.shape_id,
                        },
                    )
                )
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                image = shape.image
                width, height = image.size
                content: dict[str, Any] = {
                    "reference": f"slide-{slide_number}-image-{shape_index}"
                }
                if (
                    vision_enabled()
                    and should_describe_image(width, height, described_images)
                ):
                    described_images += 1
                    description = describe_image(image.blob, image.content_type)
                    if description:
                        content["description"] = description
                items.append(
                    ExtractedItem(
                        content_type="image_reference",
                        content=content,
                        slide_number=slide_number,
                        source={
                            "parser": "python-pptx",
                            "shape_id": shape.shape_id,
                            "dimensions": {"width": width, "height": height},
                        },
                    )
                )
    return items
