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

    # corrective RAG (LangGraph layer between retrieval and generation)
    crag_enabled: bool = True             # false -> linear retrieve->generate pipeline
    crag_max_attempts: int = 2            # max query-correction rounds (loop guard)
    crag_grade_top_k: int = 4             # how many reranked docs to grade (1 LLM call each)
    crag_relevance_threshold: float = 0.7  # per-doc score >= this counts as relevant
    crag_incorrect_max: float = 0.3       # best doc score <= this -> 'incorrect'
    crag_web_search: bool = False         # off by default; finance data stays first-party

    # api
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:5500,http://localhost:5500"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
