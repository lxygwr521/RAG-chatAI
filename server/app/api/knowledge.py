"""Knowledge base CRUD endpoints."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.schemas.chat import DocumentOut
from app.services.rag_service import ingest_document, delete_document

router = APIRouter(prefix="/api/knowledge")

# 支持的文件类型（与 frontend FileUpload 对齐 + PDF）
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".pdf",
    ".csv", ".json", ".log", ".xml", ".yml", ".yaml",
    ".ini", ".conf",
}


@router.post("/documents", response_model=list[DocumentOut])
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload one or more documents to the knowledge base.

    Files are saved, chunked, embedded, and stored in ChromaDB.
    Returns the list of created document records.
    """
    results: list[DocumentOut] = []

    for file in files:
        # Validate extension
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {ext}。支持: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # Validate size
        content = await file.read()
        file_size = len(content)
        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，最大 {settings.max_upload_size_mb}MB",
            )

        # Save to disk
        file_id = str(uuid.uuid4())
        safe_name = f"{file_id}{ext}"
        save_path = os.path.join(settings.upload_dir, safe_name)
        with open(save_path, "wb") as f:
            f.write(content)

        # Ingest
        doc = await ingest_document(
            file_path=save_path,
            filename=file.filename or "unknown",
            file_type=ext.lstrip("."),
            file_size=file_size,
            db=db,
        )

        results.append(DocumentOut(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            chunk_count=doc.chunk_count,
            status=doc.status,
            created_at=doc.created_at,
        ))

    return results


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(db: AsyncSession = Depends(get_db)):
    """List all documents in the knowledge base."""
    result = await db.execute(
        select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        DocumentOut(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size=d.file_size,
            chunk_count=d.chunk_count,
            status=d.status,
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.delete("/documents/{doc_id}")
async def remove_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a document: removes file, chunks, and ChromaDB vectors."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.id == doc_id)
        .options(selectinload(KnowledgeDocument.chunks))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete ChromaDB vectors + file on disk
    await delete_document(doc_id, doc)

    # Delete SQLite records (chunks cascade via relationship)
    for chunk in doc.chunks:
        await db.delete(chunk)
    await db.delete(doc)

    return {"detail": "Deleted"}
