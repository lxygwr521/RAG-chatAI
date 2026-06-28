from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Yield an async database session with commit on success, rollback on error."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Performance indexes (CREATE IF NOT EXISTS — idempotent)
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_messages_conv_id ON messages(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON knowledge_chunks(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_documents_created ON knowledge_documents(created_at)",
]


async def init_db():
    """Create all tables + indexes. Called during application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for idx_sql in _INDEXES:
            await conn.execute(text(idx_sql))
