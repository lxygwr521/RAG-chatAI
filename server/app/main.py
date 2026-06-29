"""FastAPI application entry point."""

import logging
import os
import time
from contextlib import asynccontextmanager

# Suppress protobuf "MessageFactory.GetPrototype" startup noise
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

class _NoiseFilter(logging.Filter):
    def filter(self, record):
        return "MessageFactory" not in record.getMessage()

logging.getLogger().addFilter(_NoiseFilter())

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.database import init_db
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.knowledge import router as knowledge_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)

    await init_db()

    try:
        from app.services.rag_service import init_chroma
        init_chroma()
        logger.info("ChromaDB initialized successfully")
    except Exception as e:
        logger.warning("ChromaDB initialization failed (RAG unavailable): %s", e)

    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Chat AI Server", version="0.1.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with duration."""
    t0 = time.time()
    response = await call_next(request)
    duration = time.time() - t0
    logger.info(
        "%s %s → %d (%.2fs)",
        request.method, request.url.path, response.status_code, duration,
    )
    return response


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning("ValueError: %s", exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(knowledge_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
