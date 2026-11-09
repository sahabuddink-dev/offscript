# Module 1: Document Management

## Purpose and scope

Provide the application's document lifecycle foundation: upload and validate files, store their original bytes locally, manage metadata in PostgreSQL, list and retrieve metadata, and delete both metadata and the corresponding stored file.

Supported extensions: PDF (`.pdf`), DOCX (`.docx`), XLSX (`.xlsx`), PPTX (`.pptx`), and UTF-8 text (`.txt`). There is no arbitrary application-level file-size limit; uploads are streamed using bounded chunks.

Out of scope: document parsing/processing, OCR, embeddings, retrieval, AI responses, semantic caching, image-only upload, document version comparison, and RAG evaluation.

## Database design

The `documents` table stores:

| Column | Type/meaning |
|---|---|
| `id` | UUID primary key |
| `filename` | Sanitized original filename |
| `stored_filename` | Unique UUID-based filename used in local storage |
| `file_type` | Lowercase extension without the dot |
| `file_size` | Actual stored byte count |
| `file_path` | Internal server-side path; never included in API responses |
| `status` | Current Module 1 status (`uploaded`) |
| `created_at` | Creation timestamp |
| `updated_at` | Last-update timestamp |

The SQLAlchemy model is in `backend/app/models/document.py`; table creation currently occurs during FastAPI startup. Schema migrations are not yet configured.

## API

All endpoints are mounted under `/api/documents`.

### `POST /api/documents/upload`

Multipart form field: `file`.

Example request:

```bash
curl -F "file=@quarterly-report.pdf" http://localhost:8001/api/documents/upload
```

Success (`201 Created`):

```json
{
  "id": "8b4e5696-3c88-4f85-99f5-bef440b3135e",
  "filename": "quarterly-report.pdf",
  "file_type": "pdf",
  "file_size": 2048,
  "status": "uploaded",
  "created_at": "2026-11-09T06:30:00Z",
  "updated_at": "2026-11-09T06:30:00Z"
}
```

### `GET /api/documents/`

Example request: `GET http://localhost:8001/api/documents/`

Success (`200 OK`):

```json
{
  "documents": [
    {
      "id": "8b4e5696-3c88-4f85-99f5-bef440b3135e",
      "filename": "quarterly-report.pdf",
      "file_type": "pdf",
      "file_size": 2048,
      "status": "uploaded",
      "created_at": "2026-11-09T06:30:00Z",
      "updated_at": "2026-11-09T06:30:00Z"
    }
  ]
}
```

### `GET /api/documents/{id}`

Example request: `GET http://localhost:8001/api/documents/8b4e5696-3c88-4f85-99f5-bef440b3135e`

Returns the same document object as upload, or `404 Not Found` if the UUID is valid but no matching document exists. An invalid UUID is rejected with `422 Unprocessable Entity`.

### `DELETE /api/documents/{id}`

Example request: `DELETE http://localhost:8001/api/documents/8b4e5696-3c88-4f85-99f5-bef440b3135e`

Success (`200 OK`):

```json
{"message": "Document deleted successfully."}
```

Returns `404 Not Found` for an unknown UUID. File/metadata failures return a server error and are logged; the operation must not report success when consistency could not be maintained.

### Common upload errors

- `400 Bad Request`: missing/unsafe filename, unsupported extension, empty file, or extension/content mismatch.
- `422 Unprocessable Entity`: malformed request or missing multipart `file`.
- `500 Internal Server Error`: storage or database operation failed. Internal absolute paths and credentials are not returned.

## File storage and validation

- Root: project `storage/documents/`.
- Stored names use a generated UUID plus the accepted extension; the original name is retained only as metadata.
- Upload reads and writes bounded chunks; there is no configured application-level size cap.
- Strip supplied path components and reject empty, overlong, or unsafe names.
- Validate content where practical: PDF signature, Office Open XML ZIP container and expected package member, and UTF-8 text decoding. Extension alone is not sufficient.
- Never extract Office ZIP archives during validation.
- Do not return `file_path` or other absolute server paths from the API.
- On a metadata failure remove the new file. During deletion, stage the file change so a failed database transaction can restore it. Report/log cleanup failures rather than silently ignoring them.

## Frontend requirements

- Document upload with browse and drag/drop; support multiple files.
- Show supported formats, upload/loading states, and per-operation errors.
- List filename, type, size, upload date, and status.
- Show document details and provide deletion with confirmation.
- Provide loading, empty, and error states.
- Reuse `frontend/src/services/apiClient.js`; do not create a second Axios client.

## Implementation status

### Verified inspection baseline

- The project already had a PostgreSQL `Document` model and a partial chunked upload handler, but the handler was not mounted by `backend/app/main.py`.
- The React root rendered an empty `<main />`; the shared Axios client was already configured.
- The project contained no document API integration tests. PostgreSQL, ChromaDB, and Redis were configured in Docker Compose; only PostgreSQL is used by this module.

### Completed and verified

- [x] PostgreSQL SQLAlchemy model includes UUID, original/stored filenames, type, size, internal path, status, and timestamps.
- [x] Upload API is mounted at the specified route; files stream in 1 MiB chunks to a temporary file before validation and atomic placement.
- [x] PDF signature, Office Open XML package members/content type, UTF-8 text, empty files, extension, and filename checks are implemented.
- [x] UUID-based stored names and project-local `storage/documents/` are used; application code sets no file-size cap.
- [x] PostgreSQL metadata insert and rollback/physical-file cleanup are implemented.
- [x] List, detail, and delete endpoints are implemented; API schemas exclude internal paths.
- [x] Delete stages the physical file before the database commit and restores it if the database transaction fails.
- [x] React UI supports multi-file browse/drop, listing, details, confirmed deletion, loading/empty/error/success states, and shared Axios integration.
- [x] Integration tests ran against the configured PostgreSQL-backed FastAPI app: **5 tests passed**. They exercise all five accepted formats; rejected extension, empty and mismatched content; multiple files; a chunked 12 MiB upload; list/detail/nonexistent IDs; delete; and metadata/file consistency.
- [x] Frontend production build completed successfully with Vite.

### In progress

- None of the requested Module 1 features.

### Pending

- No remaining Module 1 acceptance criteria identified during this implementation.
- Database schema migrations and list pagination are useful future maintenance improvements, but are not part of the current Module 1 requirements.

### Known issues and limitations

- FastAPI startup currently creates tables with `Base.metadata.create_all`; a migration framework is not configured.
- The list endpoint is unpaginated.
- Format checks establish recognizable signatures/package structure; they do not fully parse or process document contents.
- ChromaDB reported unhealthy during local infrastructure inspection; Module 1 does not depend on it.
- If physical cleanup fails after a successful metadata deletion, the API reports an explicit server error and logs the cleanup failure; manual cleanup may be required.

### Important implementation decisions

- Keep document metadata in PostgreSQL and original file bytes on local disk; do not expose `file_path` or `stored_filename` to clients.
- Use standard-library streaming, ZIP inspection, and UUIDs rather than adding dependencies.
- Validate the content structure without extracting Office archives.
- Handle multiple frontend files as separate API uploads so one failed upload does not prevent other files from being stored.

### Next development task

No required Module 1 work remains. Before changing the metadata schema, add a database migration mechanism; do not begin another approved module within the current Module 1 task.

## Progress checklist

- [ ] Completed tasks: update after implementation verification.
- [ ] In-progress tasks: update during development.
- [ ] Pending tasks: update after implementation verification.
- [ ] Known issues: update with observed remaining issues.
- [ ] Next development task: complete and verify the remaining Module 1 work.

## Implementation decisions and remaining work

To be completed after implementation: record key choices, exact verification results, known issues, and the next Module 1 task. Later approved modules are not to be started as part of this document.
