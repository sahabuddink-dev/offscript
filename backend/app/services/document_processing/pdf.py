from pathlib import Path
from typing import Any

from app.services.document_processing.base import (
    ExtractedItem,
    ProcessingError,
    text_item,
)
from app.services.document_processing.ocr import recognize_page
from app.services.document_processing.vision import (
    describe_image,
    should_describe_image,
    vision_enabled,
)


def extract_pdf(file_path: Path) -> list[ExtractedItem]:
    try:
        import pymupdf
    except ImportError as error:
        raise ProcessingError("PDF processing requires PyMuPDF.") from error

    try:
        document = pymupdf.open(file_path)
    except Exception as error:
        raise ProcessingError("The PDF is corrupted or could not be opened.") from error

    items: list[ExtractedItem] = []
    described_images = 0
    try:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            page_text_found = False
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                block_text = "\n".join(
                    span.get("text", "")
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                )
                item = text_item(
                    block_text,
                    page_number=page_number,
                    source={
                        "parser": "pymupdf",
                        "bounding_box": block.get("bbox"),
                        "coordinate_space": "pdf_points",
                        "layout": "text_block",
                    },
                )
                if item:
                    items.append(item)
                    page_text_found = True

            try:
                tables = page.find_tables().tables
            except (AttributeError, RuntimeError):
                tables = []
            for table_index, table in enumerate(tables, start=1):
                rows = table.extract()
                if not rows:
                    continue
                items.append(
                    ExtractedItem(
                        content_type="table",
                        content={
                            "headers": rows[0],
                            "rows": rows[1:],
                            "row_count": len(rows),
                            "column_count": max(map(len, rows), default=0),
                        },
                        page_number=page_number,
                        source={
                            "parser": "pymupdf",
                            "table_index": table_index,
                            "bounding_box": getattr(table, "bbox", None),
                        },
                    )
                )

            page_images = page.get_images(full=True)
            if not page_text_found and page_images:
                pixmap = page.get_pixmap(dpi=150, alpha=False)
                for recognized in recognize_page(pixmap.tobytes("png")):
                    items.append(
                        ExtractedItem(
                            content_type="ocr_text",
                            content={"text": recognized["text"]},
                            page_number=page_number,
                            source={
                                "parser": "paddleocr",
                                "confidence": recognized["confidence"],
                                "bounding_box": recognized["bounding_box"],
                                "coordinate_space": "rendered_image_pixels",
                                "render_dpi": 150,
                            },
                        )
                    )

            for image_index, image_info in enumerate(page_images, start=1):
                xref = image_info[0]
                rects = page.get_image_rects(xref)
                width, height = image_info[2], image_info[3]
                image_source: dict[str, Any] = {
                    "parser": "pymupdf",
                    "reference": f"pdf-image-{xref}",
                    "image_index": image_index,
                    "bounding_boxes": [list(rect) for rect in rects],
                    "coordinate_space": "pdf_points",
                }
                content: dict[str, Any] = {"reference": image_source["reference"]}
                if (
                    vision_enabled()
                    and should_describe_image(width, height, described_images)
                ):
                    described_images += 1
                    embedded = document.extract_image(xref)
                    description = describe_image(
                        embedded.get("image", b""),
                        f"image/{embedded.get('ext', 'png')}",
                    )
                    if description:
                        content["description"] = description
                items.append(
                    ExtractedItem(
                        content_type="image_reference",
                        content=content,
                        page_number=page_number,
                        source=image_source,
                    )
                )
    except ProcessingError:
        raise
    except Exception as error:
        raise ProcessingError("The PDF could not be fully processed.") from error
    finally:
        document.close()
    return items
