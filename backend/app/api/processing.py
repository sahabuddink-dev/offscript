import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Document, DocumentContent, DocumentProcessing
from app.schemas.processing import (
    ExtractedContentListRead,
    ExtractedContentRead,
    ProcessingStartRead,
    ProcessingStatusRead,
)
from app.services.document_processing.pipeline import process_document


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/{document_id}/process",
    response_model=ProcessingStartRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_document_processing(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ProcessingStartRead:
    document = db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .with_for_update()
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    job = db.get(DocumentProcessing, document_id)
    if job is not None and job.status in {"queued", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document processing is already in progress.",
        )

    now = datetime.now(timezone.utc)
    if job is None:
        job = DocumentProcessing(
            document_id=document_id,
            status="queued",
            started_at=None,
            completed_at=None,
        )
        db.add(job)
    else:
        job.status = "queued"
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        job.updated_at = now

    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.exception("Could not queue document processing for %s", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start document processing.",
        ) from error

    background_tasks.add_task(process_document, document_id)
    return ProcessingStartRead(
        document_id=document_id,
        status="queued",
        message="Document processing has been queued.",
    )


@router.get(
    "/{document_id}/processing",
    response_model=ProcessingStatusRead,
)
def get_processing_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProcessingStatusRead:
    if db.get(Document, document_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    job = db.get(DocumentProcessing, document_id)
    if job is None:
        return ProcessingStatusRead(document_id=document_id, status="not_started")
    return ProcessingStatusRead(
        document_id=document_id,
        status=job.status,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/{document_id}/content",
    response_model=ExtractedContentListRead,
)
def get_extracted_content(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ExtractedContentListRead:
    if db.get(Document, document_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    job = db.get(DocumentProcessing, document_id)
    items = db.scalars(
        select(DocumentContent)
        .where(DocumentContent.document_id == document_id)
        .order_by(DocumentContent.content_order)
    ).all()
    return ExtractedContentListRead(
        document_id=document_id,
        status=job.status if job else "not_started",
        items=[
            ExtractedContentRead.model_validate(item, from_attributes=True)
            for item in items
        ],
    )
