from pathlib import Path

from app.services.document_processing.base import ExtractedItem, ProcessingError, text_item


def extract_txt(file_path: Path) -> list[ExtractedItem]:
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        raise ProcessingError("The text document could not be read as UTF-8.") from error

    items: list[ExtractedItem] = []
    for paragraph_index, paragraph in enumerate(text.splitlines(), start=1):
        item = text_item(
            paragraph,
            source={"parser": "utf-8", "line_number": paragraph_index},
        )
        if item:
            items.append(item)
    return items
