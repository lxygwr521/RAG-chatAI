"""Memory management endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.memory import UserMemoryFact
from app.services.memory_service import (
    delete_user_memory_fact,
    get_user_profile,
    list_user_memory_facts,
    rebuild_user_profile_snapshot,
    update_user_memory_fact,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


class UserFactPatch(BaseModel):
    status: str | None = None
    value: dict | None = None
    confidence: float | None = None


def _fact_out(fact: UserMemoryFact) -> dict:
    try:
        value = json.loads(fact.value_json)
    except (json.JSONDecodeError, TypeError):
        value = fact.value_json

    return {
        "id": fact.id,
        "category": fact.category,
        "key": fact.key,
        "value": value,
        "status": fact.status,
        "confidence": fact.confidence,
        "source_conversation_id": fact.source_conversation_id,
        "source_message_id": fact.source_message_id,
        "evidence_text": fact.evidence_text,
        "extracted_at": fact.extracted_at,
        "updated_at": fact.updated_at,
    }


@router.get("/profile")
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Return the current user profile snapshot."""
    profile = await get_user_profile(db)
    try:
        traits = json.loads(profile.traits_json) if profile.traits_json else {}
    except json.JSONDecodeError:
        traits = {}
    return {
        "id": profile.id,
        "traits": traits,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.get("/facts")
async def list_facts(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List traceable user memory facts."""
    facts = await list_user_memory_facts(db, status=status)
    return [_fact_out(f) for f in facts]


@router.patch("/facts/{fact_id}")
async def patch_fact(
    fact_id: str,
    body: UserFactPatch,
    db: AsyncSession = Depends(get_db),
):
    """Patch a user memory fact and rebuild the profile snapshot."""
    if body.status and body.status not in {"active", "inactive", "corrected", "pending"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    fact = await update_user_memory_fact(
        db,
        fact_id,
        status=body.status,
        value=body.value,
        confidence=body.confidence,
    )
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    await db.commit()
    return _fact_out(fact)


@router.delete("/facts/{fact_id}")
async def delete_fact(
    fact_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a user memory fact and rebuild the profile snapshot."""
    deleted = await delete_user_memory_fact(db, fact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fact not found")
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/profile/rebuild")
async def rebuild_profile(db: AsyncSession = Depends(get_db)):
    """Rebuild the profile snapshot from active facts."""
    profile = await rebuild_user_profile_snapshot(db)
    await db.commit()
    try:
        traits = json.loads(profile.traits_json) if profile.traits_json else {}
    except json.JSONDecodeError:
        traits = {}
    return {"id": profile.id, "traits": traits, "updated_at": profile.updated_at}
