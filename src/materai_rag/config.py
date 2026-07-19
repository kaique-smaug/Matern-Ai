from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-5-mini"
    embedding_provider: Literal["tfidf", "openai"] = "tfidf"
    openai_embedding_model: str = "text-embedding-3-small"

    chroma_dir: Path = Path("./chroma_db")
    collection_name: str = "materai_clinical"
    top_k: int = 6
    fetch_k: int = 20
    max_context_chars: int = 18_000
    min_relevance: float = 0.10

    @property
    def data_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data"

    @property
    def chunks_path(self) -> Path:
        return self.data_dir / "chunks.jsonl"

    @property
    def vectorizer_path(self) -> Path:
        return self.chroma_dir / "tfidf_vectorizer.joblib"
