# project_root/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
from functools import lru_cache

class Settings(BaseSettings):
    # Project configuration
    PROJECT_NAME: str = "rag-system"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Database configurations
    SQLITE_URL: str = "sqlite+aiosqlite:///./data/app.db"
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "documents"
    
    # Document processing
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    MAX_DOCS_PER_REQUEST: int = 5
    SUPPORTED_DOCUMENT_TYPES: list = ["pdf"]
    
    # Ollama Configuration
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2:3b"
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7
    SYSTEM_CONTEXT: str = "You are a helpful assistant that answers questions based on the provided documents."
    
    # Vector Store
    VECTOR_DIMENSION: int = 768
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "logs/app.log"
    
    # API Settings
    CORS_ORIGINS: list = ["*"]
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    SECRET_KEY: str = "your-secret-key-here"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()