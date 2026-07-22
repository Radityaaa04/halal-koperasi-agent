"""
Configuration settings for HALAL Koperasi Agent
NVIDIA NIM Only Configuration
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    # App
    APP_NAME: str = "halal-koperasi-agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    KB_DIR: Path = DATA_DIR / "regulatory_chunks"
    SYNTHETIC_DIR: Path = DATA_DIR / "synthetic_docs"
    TEMPLATES_DIR: Path = DATA_DIR / "templates"
    EVAL_DIR: Path = DATA_DIR / "eval"
    PROFILES_DIR: Path = DATA_DIR / "koperasi_profiles"

    # LLM Provider: NVIDIA NIM Only
    LLM_PROVIDER: Literal["nvidia_nim"] = "nvidia_nim"

    # NVIDIA NIM Configuration
    NVIDIA_API_KEY: str = Field(default="", validation_alias="NVIDIA_NIM_API_KEY", description="Get from https://build.nvidia.com/explore/discover")
    NVIDIA_BASE_URL: str = Field(default="https://integrate.api.nvidia.com/v1", validation_alias="NVIDIA_NIM_BASE_URL")
    LLM_MODEL: str = "meta/llama-3.1-8b-instruct"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: int = 60

    # Embedding Provider: NVIDIA NIM
    EMBEDDING_PROVIDER: Literal["nvidia_nim"] = "nvidia_nim"
    EMBEDDING_MODEL: str = "nvidia/nv-embedqa-e5-v5"

    # Reranker Provider: NVIDIA NIM
    RERANKER_PROVIDER: Literal["nvidia_nim"] = "nvidia_nim"
    RERANKER_MODEL: str = "nvidia/rerank-qa-mistral-4b"

    # ChromaDB
    CHROMA_HOST: str = "http://localhost:8000"
    CHROMA_COLLECTION_PREFIX: str = "halal_regulations"

    # Vector Store Config
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K_RETRIEVAL: int = 20
    TOP_K_RERANK: int = 5
    SIMILARITY_THRESHOLD: float = -1.0  # Accept all (nv-embedqa-e5-v5 distances can be negative)

    # RAG Config
    MAX_CONTEXT_TOKENS: int = 4000
    CITATION_MAX_LENGTH: int = 200
    ENABLE_HYBRID_SEARCH: bool = True
    ENABLE_RERANKING: bool = True

    # Document Processing
    OCR_LANGUAGES: list = ["en", "id"]
    OCR_CONFIDENCE_THRESHOLD: float = 0.7
    PDF_DPI: int = 200

    # Agent Config
    MAX_ITERATIONS: int = 3
    HUMAN_REVIEW_THRESHOLD: float = 80.0
    CRITICAL_GAPS_THRESHOLD: int = 0

    # Evaluation
    EVAL_BATCH_SIZE: int = 10
    HALLUCINATION_CHECK_MODEL: str = "meta/llama-3.1-8b-instruct"

    # Streamlit
    STREAMLIT_PORT: int = 8501
    STREAMLIT_HOST: str = "0.0.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()