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

## Selected future document-processing and AI technologies

The following are planned options for later processing and retrieval work. They are **not installed as backend dependencies or used by Module 1**:

- PyMuPDF: PDF text extraction.
- Docling: document parsing and layout-aware conversion.
- PaddleOCR: optical character recognition.
- OpenPyXL: Excel workbook parsing.
- python-pptx: PowerPoint parsing.
- Sentence Transformers / BGE: text embeddings.
- BM25: lexical retrieval.
- BGE reranker: candidate reranking.
- Gemini API: generative AI integration.

No whole-system LangChain dependency is selected. Future integrations should remain modular and use focused libraries where they fit.
