# OffScript

OffScript is an Enterprise Document Intelligence and Knowledge Retrieval Platform.

This repository currently contains development scaffolding only. Application features are under development.

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

## Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5174

## Development Status

Initial project environment and infrastructure setup. Application features will be implemented incrementally.