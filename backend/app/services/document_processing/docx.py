from pathlib import Path
from typing import Any

from app.services.document_processing.base import ExtractedItem, ProcessingError, text_item
from app.services.document_processing.vision import (
    describe_image,
    should_describe_image,
    vision_enabled,
)


def extract_docx(file_path: Path) -> list[ExtractedItem]:
    try:
        from docx import Document as WordDocument
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as error:
        raise ProcessingError("DOCX processing requires python-docx.") from error
    try:
        document = WordDocument(file_path)
    except Exception as error:
        raise ProcessingError("The DOCX file is corrupted or could not be opened.") from error

    items: list[ExtractedItem] = []
    paragraph_index = 0
    table_index = 0
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            paragraph_index += 1
            style = block.style.name if block.style else "Normal"
            content_type = (
                "heading"
                if style.lower().startswith(("heading", "title"))
                else "paragraph"
            )
            item = text_item(
                block.text,
                content_type=content_type,
                source={
                    "parser": "python-docx",
                    "paragraph_index": paragraph_index,
                    "style": style,
                },
            )
            if item:
                items.append(item)
            continue

        table_index += 1
        if not isinstance(block, Table):
            continue
        rows = [[cell.text.strip() for cell in row.cells] for row in block.rows]
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
                    source={"parser": "python-docx", "table_index": table_index},
                )
            )

    described_images = 0
    for image_index, shape in enumerate(document.inline_shapes, start=1):
        inline = shape._inline
        blip = inline.graphic.graphicData.pic.blipFill.blip
        relationship_id = blip.embed
        image_part = document.part.related_parts[relationship_id]
        width, height = image_part.image.px_width, image_part.image.px_height
        content: dict[str, Any] = {"reference": f"docx-image-{image_index}"}
        if (
            vision_enabled()
            and should_describe_image(width, height, described_images)
        ):
            described_images += 1
            description = describe_image(image_part.blob, image_part.content_type)
            if description:
                content["description"] = description
        items.append(
            ExtractedItem(
                content_type="image_reference",
                content=content,
                source={
                    "parser": "python-docx",
                    "relationship_id": relationship_id,
                    "dimensions": {"width": width, "height": height},
                },
            )
        )
    return items
