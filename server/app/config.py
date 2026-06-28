from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from .env file and environment variables."""

    # LLM Provider (DeepSeek)
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_max_tokens: int = 8192

    # Embedding Provider (OpenAI)
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/chat.db"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "knowledge_base"

    # Upload
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 10

    # Server
    host: str = "0.0.0.0"
    port: int = 3001
    cors_origins: str = "http://localhost:3000"

    # Context
    max_context_tokens: int = 80000
    recent_window_size: int = 20

    # Mock
    mock_chunk_size: int = 100
    mock_interval_ms: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
