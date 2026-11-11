from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ProcessingStatusRead(BaseModel):
    document_id: UUID
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None


class ProcessingStartRead(BaseModel):
    document_id: UUID
    status: str
    message: str


class ExtractedContentRead(BaseModel):
    id: UUID
    content_type: str
    content: dict[str, Any]
    page_number: int | None
    slide_number: int | None
    sheet_name: str | None
    cell_reference: str | None
    content_order: int
    source: dict[str, Any]


class ExtractedContentListRead(BaseModel):
    document_id: UUID
    status: str
    items: list[ExtractedContentRead]
