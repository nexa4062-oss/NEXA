from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Sovereign AI Workbench"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, demo, production

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sovereign_ai"
    DATABASE_ECHO: bool = False
    USE_SQLITE: bool = True  # Use SQLite for local dev when PostgreSQL is unavailable

    # Vector DB
    VECTOR_DB_URL: str = "http://localhost:6333"
    VECTOR_DB_COLLECTION: str = "documents"

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT: int = 120

    # Authentication
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    # Security
    AIR_GAPPED_MODE: bool = True
    BLOCKED_DOMAINS: list[str] = ["api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com"]
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Storage
    UPLOAD_DIR: str = "./data/uploads"
    GENERATED_DIR: str = "./data/generated"
    MAX_UPLOAD_SIZE_MB: int = 500

    # Sandbox
    SANDBOX_TIMEOUT_SECONDS: int = 30
    SANDBOX_MAX_MEMORY_MB: int = 512
    SANDBOX_ALLOWED_LANGUAGES: list[str] = ["python", "javascript", "bash"]

    # LangGraph agent workflow - durable checkpoint store for HITL
    # pause/resume (survives an app restart, unlike an in-memory saver)
    LANGGRAPH_CHECKPOINT_DB: str = "./data/langgraph_checkpoints.db"

    # Background Jobs
    REDIS_URL: str = "redis://localhost:6379/0"

    # Quotas
    DEFAULT_MAX_CONCURRENT_JOBS: int = 3
    DEFAULT_MAX_STORAGE_MB: int = 5000
    DEFAULT_MAX_REQUESTS_PER_HOUR: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
