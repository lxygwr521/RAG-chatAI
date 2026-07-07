from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, loaded from .env file and environment variables."""

    # LLM Provider (OpenRouter, OpenAI-compatible chat completions)
    openrouter_api_key: str = ""
    open_router_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "deepseek/deepseek-chat"
    openrouter_light_model: str = "deepseek/deepseek-chat"
    openrouter_judge_model: str = "z-ai/glm-5.2"
    openrouter_max_tokens: int = 8192
    openrouter_referer: str = ""
    openrouter_app_name: str = "chatAI"

    # Embedding Provider (智谱 ZhipuAI, OpenAI-compatible)
    zhipuai_api_key: str = ""
    zhipuai_embedding_model: str = "embedding-2"
    zhipuai_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"

    # Embedding Provider (OpenAI, fallback)
    openai_api_key: str = ""
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

    # Agent
    agent_recursion_limit: int = 10

    # Context
    max_context_tokens: int = 80000
    recent_window_size: int = 20

    # RAG retrieval
    rag_vector_top_k: int = 30
    rag_lexical_top_k: int = 30
    rag_score_threshold: float = 1.5
    rag_rrf_k: int = 60
    rag_vector_weight: float = 1.0
    rag_lexical_weight: float = 0.8
    rag_rerank_top_k: int = 12
    rag_reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    rag_reranker_batch_size: int = 16

    # Mock
    mock_chunk_size: int = 100
    mock_interval_ms: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
