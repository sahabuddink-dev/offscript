import codecs
import logging
import os
import uuid
import zipfile
import zlib
from pathlib import Path
from typing import Final

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Document
from app.schemas.document import (
    DocumentListResponse,
    DocumentRead,
    MessageResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter()

STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "documents"
ALLOWED_EXTENSIONS: Final = {".pdf", ".docx", ".xlsx", ".pptx", ".txt"}
CHUNK_SIZE: Final = 1024 * 1024
ZIP_METADATA_LIMIT: Final = 1024 * 1024

OFFICE_PACKAGE_CONTENT: Final = {
    ".docx": (
        "word/document.xml",
        b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    ),
    ".xlsx": (
        "xl/workbook.xml",
        b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    ),
    ".pptx": (
        "ppt/presentation.xml",
        b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
    ),
}


def _safe_original_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    safe_filename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if (
        not safe_filename
        or safe_filename in {".", ".."}
        or len(safe_filename) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in safe_filename)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is invalid.",
        )

    return safe_filename


async def _write_upload(upload: UploadFile, destination: Path, extension: str) -> tuple[int, bytes]:
    file_size = 0
    header = bytearray()
    text_decoder = codecs.getincrementaldecoder("utf-8-sig")() if extension == ".txt" else None

    with destination.open("xb") as output:
        while chunk := await upload.read(CHUNK_SIZE):
            output.write(chunk)
            file_size += len(chunk)

            if len(header) < 1024:
                header.extend(chunk[: 1024 - len(header)])

            if text_decoder is not None:
                try:
                    text_decoder.decode(chunk)
                except UnicodeDecodeError as error:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Text documents must contain valid UTF-8 text.",
                    ) from error

        if text_decoder is not None:
            try:
                text_decoder.decode(b"", final=True)
            except UnicodeDecodeError as error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text documents must contain valid UTF-8 text.",
                ) from error

    return file_size, bytes(header)


def _validate_office_document(file_path: Path, extension: str) -> None:
    required_member, content_type = OFFICE_PACKAGE_CONTENT[extension]

    try:
        with zipfile.ZipFile(file_path) as package:
            names = set(package.namelist())
            if (
                "[Content_Types].xml" not in names
                or "_rels/.rels" not in names
                or required_member not in names
                or package.getinfo(required_member).file_size == 0
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File contents do not match the selected Office document type.",
                )

            content_types = package.getinfo("[Content_Types].xml")
            if content_types.file_size > ZIP_METADATA_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Office document package metadata is invalid.",
                )
            if content_type not in package.read(content_types):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File contents do not match the selected Office document type.",
                )
    except (
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        zlib.error,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Office document package is invalid.",
        ) from error


def _validate_document_content(file_path: Path, extension: str, header: bytes) -> None:
    if extension == ".pdf" and b"%PDF-" not in header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File contents do not match the PDF extension.",
        )
    if extension in OFFICE_PACKAGE_CONTENT:
        _validate_office_document(file_path, extension)


def _storage_path(stored_filename: str) -> Path:
    candidate = Path(stored_filename)
    try:
        uuid.UUID(candidate.stem)
    except ValueError as error:
        raise ValueError("Stored document filename is invalid.") from error
    if (
        candidate.name != stored_filename
        or candidate.suffix.lower() not in ALLOWED_EXTENSIONS
        or "\\" in stored_filename
    ):
        raise ValueError("Stored document filename is invalid.")
    return STORAGE_DIR / stored_filename


def _remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not remove temporary document file %s", path.name)


@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentRead:
    temporary_path: Path | None = None
    stored_path: Path | None = None
    saved = False

    try:
        original_filename = _safe_original_filename(file.filename)
        extension = Path(original_filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Supported formats: PDF, DOCX, XLSX, PPTX, and TXT.",
            )

        try:
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            temporary_path = STORAGE_DIR / f".{uuid.uuid4()}.upload"
            stored_filename = f"{uuid.uuid4()}{extension}"
            stored_path = STORAGE_DIR / stored_filename

            file_size, header = await _write_upload(file, temporary_path, extension)
            if file_size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Empty files cannot be uploaded.",
                )
            _validate_document_content(temporary_path, extension, header)
            os.replace(temporary_path, stored_path)

            document = Document(
                filename=original_filename,
                stored_filename=stored_filename,
                file_type=extension.removeprefix("."),
                file_size=file_size,
                file_path=str(stored_path.resolve()),
                status="uploaded",
            )
            db.add(document)
            db.flush()
            db.refresh(document)
            response = DocumentRead.model_validate(document)
            db.commit()
            saved = True
            return response
        except HTTPException:
            db.rollback()
            raise
        except (OSError, SQLAlchemyError) as error:
            db.rollback()
            logger.exception("Document upload failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document upload failed.",
            ) from error
    finally:
        if not saved:
            if temporary_path is not None:
                _remove_file(temporary_path)
            if stored_path is not None:
                _remove_file(stored_path)
        await file.close()


@router.get("/", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)) -> DocumentListResponse:
    documents = db.scalars(
        select(Document).order_by(Document.created_at.desc(), Document.id)
    ).all()
    return DocumentListResponse(
        documents=[DocumentRead.model_validate(document) for document in documents]
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentRead:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> MessageResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    try:
        stored_path = _storage_path(document.stored_filename)
    except ValueError as error:
        logger.exception("Stored filename for document %s is invalid", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document metadata is invalid.",
        ) from error

    staged_path = STORAGE_DIR / f".{document_id}.deleting"
    staged = False
    try:
        if stored_path.exists():
            os.replace(stored_path, staged_path)
            staged = True
        else:
            logger.warning("Stored file is missing for document %s", document_id)

        db.delete(document)
        db.commit()
    except (OSError, SQLAlchemyError) as error:
        db.rollback()
        if staged:
            try:
                os.replace(staged_path, stored_path)
            except OSError:
                logger.exception("Could not restore file for document %s", document_id)
        logger.exception("Document deletion failed for document %s", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document deletion failed.",
        ) from error

    if staged:
        try:
            staged_path.unlink()
        except OSError as error:
            logger.exception("Could not remove deleted file for document %s", document_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document metadata was deleted, but file cleanup failed.",
            ) from error

    return MessageResponse(message="Document deleted successfully.")
