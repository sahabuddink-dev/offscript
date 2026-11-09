# OffScript

OffScript is an Enterprise Document Intelligence and Knowledge Retrieval Platform.

Module 1, Document Management, provides document upload, validation, local file storage, PostgreSQL metadata, listing, details, and deletion. The other approved modules remain future work.

Project context, architecture, development rules, stack choices, and Module 1 specifications/status are documented in [`docs/`](./docs/).

## Technology Stack

- **Frontend:** React, Vite, JavaScript, CSS, Axios
- **Backend:** Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy, Psycopg
- **Databases:** PostgreSQL, ChromaDB, Redis
- **Infrastructure:** Docker, Docker Compose

## Project Structure

```text
offscript/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── workers/
│   └── requirements.txt
├── frontend/
│   ├── public/
│   └── src/
│       ├── assets/
│       ├── components/
│       ├── hooks/
│       ├── layouts/
│       ├── pages/
│       ├── services/
│       └── styles/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js and npm
- Docker Desktop
- Git

## Environment Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Configure your local environment variables and database credentials.

Never commit your actual `.env` file.

## Infrastructure Setup

Start PostgreSQL, ChromaDB and Redis:

```bash
docker compose up -d
```

If port 8000 is already in use on your machine, update the `CHROMA_PORT` value in your root `.env` file before starting the stack. The project also exposes PostgreSQL on port `5433` via the `POSTGRES_PORT` setting.

Check running containers:

```bash
docker compose ps
```

Stop containers:

```bash
docker compose down
```

Persistent data is stored in Docker volumes.

## Backend Setup

Activate the Python virtual environment:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Start FastAPI:

```bash
cd backend
uvicorn app.main:app --reload --port 8001
```

Backend: http://localhost:8001

API documentation: http://localhost:8001/docs

Module 1 API routes are under `/api/documents`.

Run the backend integration tests (PostgreSQL and the project `.env` must be available):

```bash
cd ..
.venv/bin/python -m unittest discover -s tests -v
```

## Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5174

## Development Status

See [`docs/MODULE_1_DOCUMENT_MANAGEMENT.md`](./docs/MODULE_1_DOCUMENT_MANAGEMENT.md) for verified implementation status and remaining Module 1 work.