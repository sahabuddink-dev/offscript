
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.document import router as document_router
from app.api.processing import router as processing_router
from app.database.base import Base
from app.database.connection import engine
from app.models import Document


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables when the application starts
    Base.metadata.create_all(bind=engine)

    yield

    # Application shutdown


app = FastAPI(
    title="OffScript API",
    description="Enterprise Document Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_router, prefix="/api/documents", tags=["documents"])
app.include_router(
    processing_router,
    prefix="/api/documents",
    tags=["document-processing"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to OffScript API",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
