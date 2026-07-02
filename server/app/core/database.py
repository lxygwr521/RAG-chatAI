from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={
        # WAL mode: concurrent reads + 1 write, no read/write conflicts
        "timeout": 30,  # Wait up to 30s before giving up on a lock
    },
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL journal mode for concurrent read/write access."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")  # 5s busy wait
    cursor.close()


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
    "CREATE INDEX IF NOT EXISTS idx_messages_conv_id_id ON messages(conversation_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON knowledge_chunks(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_documents_created ON knowledge_documents(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_user_memory_status ON user_memory_facts(status)",
    "CREATE INDEX IF NOT EXISTS idx_user_memory_category ON user_memory_facts(category)",
    "CREATE INDEX IF NOT EXISTS idx_user_memory_source_conv ON user_memory_facts(source_conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_episodic_conv_id ON episodic_memories(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_episodic_created ON episodic_memories(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_episodic_embedding ON episodic_memories(embedding_id)",
]


async def _ensure_conversation_columns(conn) -> None:
    """Add columns that create_all cannot add to an existing SQLite table."""
    result = await conn.execute(text("PRAGMA table_info(conversations)"))
    existing_columns = {row[1] for row in result.fetchall()}

    if "summarized_through_message_id" not in existing_columns:
        await conn.execute(
            text("ALTER TABLE conversations ADD COLUMN summarized_through_message_id INTEGER")
        )
    if "summary_updated_at" not in existing_columns:
        await conn.execute(
            text("ALTER TABLE conversations ADD COLUMN summary_updated_at INTEGER")
        )


async def init_db():
    """Create all tables + indexes. Called during application startup."""
    # Ensure all ORM models are registered before create_all().
    import app.models.conversation  # noqa: F401
    import app.models.knowledge  # noqa: F401
    import app.models.memory  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_conversation_columns(conn)
        for idx_sql in _INDEXES:
            await conn.execute(text(idx_sql))
