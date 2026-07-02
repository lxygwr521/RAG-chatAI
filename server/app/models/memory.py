"""Memory-related ORM models."""

import time

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    traits_json: Mapped[str] = mapped_column(Text, default="{}")
    # traits_json structure:
    # {
    #   "basic": {"age": null, "gender": null, "height": null, "weight": null},
    #   "conditions": [{"name": "高血压", "since": "2024", "details": "..."}],
    #   "allergies": ["青霉素"],
    #   "medications": [{"name": "...", "dosage": "..."}],
    #   "preferences": {"diet": "低盐", "exercise": "快走"},
    #   "goals": ["控制血压", "减重5kg"]
    # }
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))


class UserMemoryFact(Base):
    """A traceable long-term user fact.

    UserProfile.traits_json is the current snapshot; this table is the audit log
    that lets us correct, deactivate, delete, and cite profile facts.
    """

    __tablename__ = "user_memory_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category: Mapped[str] = mapped_column(String(50))
    key: Mapped[str] = mapped_column(String(100))
    value_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    source_conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))


class EpisodicMemoryRecord(Base):
    """SQLite metadata for a cross-conversation episodic memory.

    ChromaDB stores embeddings for semantic search; this table is the durable
    source for provenance, deletion, and auditability.
    """

    __tablename__ = "episodic_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(Text)
    facts_json: Mapped[str] = mapped_column(Text, default="[]")
    importance: Mapped[int] = mapped_column(Integer, default=5)
    embedding_id: Mapped[str] = mapped_column(String(80))
    source_message_start_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_message_end_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))
