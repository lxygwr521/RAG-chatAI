import time
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    model: Mapped[str] = mapped_column(String(50), default="openrouter")
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summarized_count: Mapped[int] = mapped_column(Integer, default=0)
    summarized_through_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_updated_at: Mapped[int | None] = mapped_column(Integer, nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    thinking_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    files_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time() * 1000))

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
