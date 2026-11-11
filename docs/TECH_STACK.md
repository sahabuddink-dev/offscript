# Technology Stack

This list distinguishes installed project dependencies from selected future technologies. A technology appearing in this document does not imply it is implemented.

## Installed/current stack

### Frontend

| Technology | Purpose | Status |
|---|---|---|
| React | Component-based document-management interface | Installed |
| Vite | Frontend development server and production build | Installed |
| JavaScript | Frontend application language | In use |
| CSS | Frontend styling | In use |
| Axios | HTTP client; a shared client is configured in `frontend/src/services/apiClient.js` | Installed |

### Backend

| Technology | Purpose | Status |
|---|---|---|
| Python | Backend language | In use |
| FastAPI | HTTP API framework | Installed |
| Uvicorn | ASGI server | Installed |
| Pydantic | API data validation and serialization (also used by FastAPI) | Installed |
| SQLAlchemy | ORM and database access | Installed |
| Psycopg | PostgreSQL driver | Installed |
| python-multipart | Multipart form/file parsing | Installed |
| python-dotenv | Load local environment configuration | Installed |

### Infrastructure

| Technology | Purpose | Status |
|---|---|---|
| PostgreSQL | Relational document metadata store | Docker service configured |
| ChromaDB | Planned vector store | Docker service configured; not used by Module 1 |
| Redis | Planned cache/coordination service | Docker service configured; not used by Module 1 |
| Docker | Container runtime for local infrastructure | Configured |
| Docker Compose | Local infrastructure orchestration | Configured |

## Document processing and future AI technologies

| Technology | Purpose | Status |
|---|---|---|
| PyMuPDF | PDF text, layout, table, and image-reference extraction | Installed and used by Module 2 |
| python-docx | DOCX paragraphs, headings, tables, and image references | Installed and used by Module 2 |
| OpenPyXL | XLSX worksheets, cells, tables, charts, and image references | Installed and used by Module 2 |
| python-pptx | PPTX slides, text, tables, charts, and image references | Installed and used by Module 2 |
| PaddleOCR / PaddlePaddle | OCR of scanned PDF pages | Optional runtime dependencies; loaded only when OCR is needed |
| Gemini API | Optional descriptions of selected embedded visuals | Called directly over HTTP; `GEMINI_API_KEY` is environment configuration, no SDK dependency |
| Docling | Optional richer PDF layout conversion | Not installed or currently used; PyMuPDF is the current PDF parser |
| Sentence Transformers / BGE | Text embeddings | Future Module 3 work |
| BM25 | Lexical retrieval | Future Module 3 work |
| BGE reranker | Candidate reranking | Future Module 3 work |

These processing libraries are not used by Module 1's upload and document-management paths. No whole-system LangChain dependency is selected; keep future integrations modular and use focused libraries where they fit.
