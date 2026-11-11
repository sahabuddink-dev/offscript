import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import SessionLocal
from app.models import Document, DocumentContent, DocumentProcessing
from app.services.document_processing.base import ExtractedItem, ProcessingError
from app.services.document_processing.docx import extract_docx
from app.services.document_processing.pdf import extract_pdf
from app.services.document_processing.pptx import extract_pptx
from app.services.document_processing.txt import extract_txt
from app.services.document_processing.xlsx import extract_xlsx


logger = logging.getLogger(__name__)
STORAGE_DIR = Path(__file__).resolve().parents[4] / "storage" / "documents"
PROCESSORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "xlsx": extract_xlsx,
    "pptx": extract_pptx,
    "txt": extract_txt,
}


def _original_file_path(document: Document) -> Path:
    storage_root = STORAGE_DIR.resolve()
    expected_path = (storage_root / document.stored_filename).resolve()
    recorded_path = Path(document.file_path).resolve()
    if recorded_path != expected_path or not recorded_path.is_relative_to(storage_root):
        raise ProcessingError("The stored document location is invalid.")
    if not recorded_path.is_file():
        raise ProcessingError("The stored original document file is missing.")
    return recorded_path


def _extract(file_path: Path, file_type: str) -> list[ExtractedItem]:
    processor = PROCESSORS.get(file_type.lower().lstrip("."))
    if processor is None:
        raise ProcessingError(f"Unsupported document format: {file_type}.")
    return processor(file_path)


def _set_failed(document_id: uuid.UUID, message: str) -> None:
    try:
        with SessionLocal() as db:
            job = db.get(DocumentProcessing, document_id)
            if job is None:
                logger.error("Processing status is missing for document %s", document_id)
                return
            job.status = "failed"
            job.error_message = message
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    except SQLAlchemyError:
        logger.exception("Could not save processing failure for document %s", document_id)


def process_document(document_id: uuid.UUID) -> None:
    try:
        with SessionLocal() as db:
            job = db.get(DocumentProcessing, document_id)
            document = db.get(Document, document_id)
            if job is None or document is None:
                logger.error("Queued processing references missing document %s", document_id)
                return
            if job.status != "queued":
                logger.warning(
                    "Skipping processing for document %s with status %s",
                    document_id,
                    job.status,
                )
                return
            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            job.error_message = None
            db.commit()
            file_path = _original_file_path(document)
            file_type = document.file_type
            filename = document.filename

        extracted_items = _extract(file_path, file_type)
        completed_at = datetime.now(timezone.utc)

        with SessionLocal() as db:
            job = db.get(DocumentProcessing, document_id)
            if job is None:
                raise ProcessingError("Processing state was removed before completion.")
            db.execute(
                delete(DocumentContent).where(
                    DocumentContent.document_id == document_id
                )
            )
            for order, item in enumerate(extracted_items):
                db.add(
                    DocumentContent(
                        document_id=document_id,
                        content_type=item.content_type,
                        content=item.content,
                        page_number=item.page_number,
                        slide_number=item.slide_number,
                        sheet_name=item.sheet_name,
                        cell_reference=item.cell_reference,
                        content_order=order,
                        source={
                            "filename": filename,
                            "file_type": file_type,
                            **item.source,
                        },
                    )
                )
            job.status = "completed"
            job.error_message = None
            job.completed_at = completed_at
            db.commit()
    except ProcessingError as error:
        logger.warning("Processing failed for document %s: %s", document_id, error)
        _set_failed(document_id, str(error))
    except (OSError, SQLAlchemyError):
        logger.exception("Processing failed for document %s", document_id)
        _set_failed(document_id, "Document processing failed due to a storage or database error.")
    except Exception:
        logger.exception("Unexpected processing failure for document %s", document_id)
        _set_failed(document_id, "Document processing failed unexpectedly.")
