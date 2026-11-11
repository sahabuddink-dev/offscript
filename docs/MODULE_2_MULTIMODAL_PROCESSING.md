# Module 2: Multimodal Document Processing

## Objectives and scope

Process a document already stored by Module 1, preserve source locations and document structure, and expose its processing state and extracted content. This module does not upload, delete, or manage original documents.

Included: PDF, DOCX, XLSX, PPTX, and the UTF-8 TXT format already accepted by Module 1. Processing output is structured and stored in PostgreSQL. There are no embeddings, chunking, BM25, vector search, retrieval, reranking, RAG, assistant, or cache features.

## Processing architecture

1. `POST /api/documents/{id}/process` verifies the document and queues a background task.
2. Processing state is written to `document_processing`; the original document record remains unchanged.
3. The processor validates the stored path against `storage/documents/`, uses the Module 1 file type to select a format processor, and reads the existing original.
4. Format processors emit normalized content items with source metadata. Items are ordered and persisted to `document_content`.
5. On success, the job is marked `completed`. On an extraction or persistence failure, the job is marked `failed` with an actionable error. Reprocessing is allowed unless the document is already queued or processing; old content is replaced only after a successful extraction.
6. `GET /api/documents/{id}/processing` reports status and `GET /api/documents/{id}/content` returns persisted items.

FastAPI background tasks keep parsing out of the request/response path. This is an in-process queue: a process restart can interrupt work, and deployments requiring durable scheduling or multiple workers should replace it with a persistent job queue.

## API endpoints

| Method and path | Behavior |
|---|---|
| `POST /api/documents/{id}/process` | Returns `202 Accepted` after queueing; returns `404` for an unknown document or `409` if a run is already active. |
| `GET /api/documents/{id}/processing` | Returns the current status, timestamps, and failure message, or `not_started`. |
| `GET /api/documents/{id}/content` | Returns the current processing status and ordered structured items. During a reprocess, previously completed items remain available until replacement succeeds. |

## Supported formats and extraction

| Format | Strategy | Structured output |
|---|---|---|
| PDF | PyMuPDF extracts text blocks and layout bounding boxes page-by-page, attempts native table detection, and records embedded image references. | Paragraphs, tables with headers/rows, image references, page numbers, and layout source data. |
| DOCX | python-docx walks paragraphs and tables in document order. | Heading/paragraph items and tables with headers and rows. Inline images are referenced and may be described selectively. |
| XLSX | OpenPyXL reads each worksheet, used dimensions, cell values, defined or inferred tables, chart anchors, and images. | Worksheet metadata, structured table items, and row items with each populated cell's coordinate, column, and value. Sheet names and ranges are preserved. |
| PPTX | python-pptx reads slide titles, text shapes, tables, and picture shapes. | Slide title/text items, tables with headers/rows, and image references with slide/shape metadata. |
| TXT | UTF-8 text is read line-by-line. | Non-empty paragraph items with line references. |

PyMuPDF is the PDF parser. Docling is not installed or enabled: PyMuPDF provides the current page-level text, layout, table, and image extraction path without adding Docling's larger dependency stack. A Docling-backed layout adapter remains a possible enhancement for documents that need richer layout reconstruction.

## OCR and visual content

- A PDF page with no extractable text but containing embedded page imagery is rendered and passed to PaddleOCR. OCR text includes confidence, bounding box, and the original PDF page number.
- Blank pages do not invoke OCR. PaddleOCR and its compatible PaddlePaddle runtime are optional, lazy-loaded dependencies; a scanned page requiring OCR fails with an explicit installation message if they are unavailable.
- Embedded images, charts, and diagrams are represented as references to their source page, slide, or worksheet/cell when available. They are not uploaded as separate documents.
- Gemini image descriptions are optional. If `GEMINI_API_KEY` is configured, only visuals at least 400x400 pixels are considered, with a maximum of ten visual requests per document. The key is read from the environment. The default model is `gemini-2.0-flash`; `GEMINI_MODEL` may override it. No image bytes are sent when the key is absent or the visual does not meet the selection threshold.

## Structured output and source references

Each `document_content` record contains the document ID, content type, structured JSON content, global content order, and applicable page number, slide number, worksheet name, or cell/range reference. A separate `source` JSON object records the parser, original filename/type, and format-specific location data (such as a PDF bounding box, DOCX paragraph/table index, or Office shape/cell reference). Tables retain a header row and a two-dimensional row array instead of being flattened into prose.

Processing status is stored separately from Module 1's upload status:

- `not_started`: no processing job exists.
- `queued`: accepted for background processing.
- `processing`: extraction is in progress.
- `completed`: the latest run succeeded; its content replaces previous extracted content.
- `failed`: extraction failed; the error is exposed through the status API. Previously completed content, if any, is retained.

## Error handling and temporary files

Missing documents return 404; duplicate active processing requests return 409. Corrupted/unsupported content, missing original files, missing optional OCR support, and Gemini API errors mark processing failed and expose a useful message without returning internal file paths or credentials. Unexpected exceptions are logged and surfaced as a generic processing error. OCR uses a managed temporary file that is closed and removed by its context manager.

## Implementation progress

- [x] PostgreSQL processing-job and extracted-content models with cascading document cleanup.
- [x] Background process start, status, content APIs, failure status, and reprocessing behavior.
- [x] Independent PDF, DOCX, XLSX, PPTX, and TXT processors.
- [x] Structured tables, page/slide/sheet/cell references, and embedded-visual references.
- [x] Selective PaddleOCR and opt-in Gemini visual descriptions.
- [x] Format-level unit tests and PostgreSQL-backed processing API test cases.
- [ ] Install and validate PaddleOCR/PaddlePaddle on the deployment platform; scanned-page OCR currently requires these optional dependencies.
- [ ] Evaluate a Docling adapter for PDFs requiring layout reconstruction beyond PyMuPDF's page/block/table extraction.
- [ ] Use a durable task queue if processing must survive backend restarts or scale across multiple workers.

## Testing strategy

`tests/test_document_processing.py` builds documents independently and checks text and tabular PDF extraction, scanned PDF OCR metadata (with the OCR engine isolated), DOCX paragraphs/headings/tables/images, multi-sheet XLSX data/tables/images and coordinates, PPTX text/tables/images, blank documents, corrupted files, and unsupported formats.

`tests/test_document_api.py` covers queued/status/content behavior, reprocessing, and persisted failure reporting against the configured PostgreSQL-backed FastAPI application. The existing Module 1 API tests remain applicable to upload/delete behavior. Record only commands and results actually run for each environment.

### Verification in this workspace

- `.venv/bin/python -m unittest discover -s tests -p 'test_document_processing.py' -v`: **8 tests passed**.
- `.venv/bin/python -m unittest discover -s tests -p 'test_document_api.py' -v`: attempted, but the test server could not start because PostgreSQL at `localhost:5433` refused connections; **0 API tests ran**.
- Python compilation, OpenAPI route checks, PostgreSQL DDL compilation, and `git diff --check`: passed.
