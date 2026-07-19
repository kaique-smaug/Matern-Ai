from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    gestational_week: int | None = Field(default=None, ge=1, le=45)
    language: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=15)


class Source(BaseModel):
    chunk_id: str
    title: str
    source_file: str
    section_path: str
    page_start: int
    page_end: int
    url: str | None = None
    language: str
    relevance: float


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    emergency: bool = False
    grounded: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
