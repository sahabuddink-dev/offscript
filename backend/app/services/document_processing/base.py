from dataclasses import dataclass, field
from typing import Any


class ProcessingError(Exception):
    pass


@dataclass
class ExtractedItem:
    content_type: str
    content: dict[str, Any]
    source: dict[str, Any] = field(default_factory=dict)
    page_number: int | None = None
    slide_number: int | None = None
    sheet_name: str | None = None
    cell_reference: str | None = None
    content_order: int = 0


def text_item(
    text: str,
    *,
    content_type: str = "paragraph",
    page_number: int | None = None,
    slide_number: int | None = None,
    sheet_name: str | None = None,
    cell_reference: str | None = None,
    source: dict[str, Any] | None = None,
) -> ExtractedItem | None:
    normalized_text = " ".join(text.split())
    if not normalized_text:
        return None
    return ExtractedItem(
        content_type=content_type,
        content={"text": normalized_text},
        source=source or {},
        page_number=page_number,
        slide_number=slide_number,
        sheet_name=sheet_name,
        cell_reference=cell_reference,
    )
