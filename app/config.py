"""Settings loaded from environment / .env. See .env.example for docs."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # models / providers
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    llm_provider: str = "ollama"
    llm_model: str = "qwen2:7b"
    reranker: str = "local"  # local | off
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # optional paid keys (unused when providers are 'ollama')
    openai_api_key: str = ""
    cohere_api_key: str = ""
    anthropic_api_key: str = ""

    # infra
    ollama_url: str = "http://localhost:11434"
    qdrant_url: str = ""  # blank -> embedded on-disk mode
    qdrant_path: str = "data/qdrant"
    qdrant_collection: str = "finance_chunks"

    # durable conversation history (embedded SQLite, mirrors the on-disk Qdrant choice)
    session_db_path: str = "data/app.db"

    # retrieval tuning
    retrieve_top_k: int = 20
    final_top_k: int = 5

    # api
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:5500,http://localhost:5500"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
