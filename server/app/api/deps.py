"""FastAPI dependency injection."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session with commit on success, rollback on error."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
