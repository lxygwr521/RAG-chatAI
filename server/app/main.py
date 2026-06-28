"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import init_db
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.knowledge import router as knowledge_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Create data directories
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)

    # Initialize database
    await init_db()

    # Initialize ChromaDB
    try:
        from app.services.rag_service import init_chroma
        init_chroma()
        logger.info("ChromaDB initialized successfully")
    except Exception as e:
        logger.warning(f"ChromaDB initialization failed (RAG unavailable): {e}")

    yield
    # Shutdown: nothing to clean up


app = FastAPI(title="Chat AI Server", version="0.1.0", lifespan=lifespan)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(knowledge_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
