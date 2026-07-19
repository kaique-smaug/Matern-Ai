from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb

from .config import Settings
from .embeddings import TfidfEmbeddingFunction


@dataclass
class RetrievedChunk:
    chunk_id: str
    document: str
    metadata: dict[str, Any]
    relevance: float


class ClinicalRetriever:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self.collection = self.client.get_collection(settings.collection_name)
        self.provider = str(self.collection.metadata.get("embedding_provider", settings.embedding_provider))

        self._tfidf = None
        self._openai_embeddings = None
        if self.provider == "tfidf":
            self._tfidf = TfidfEmbeddingFunction(settings.vectorizer_path)
        else:
            from langchain_openai import OpenAIEmbeddings

            self._openai_embeddings = OpenAIEmbeddings(model=settings.openai_embedding_model)

    def _embed(self, query: str) -> list[float]:
        if self._tfidf is not None:
            return self._tfidf.embed_query(query)
        assert self._openai_embeddings is not None
        return self._openai_embeddings.embed_query(query)

    def search(
        self,
        query: str,
        *,
        k: int | None = None,
        language: str | None = None,
    ) -> list[RetrievedChunk]:
        n_results = k or self.settings.top_k
        where = None
        if language:
            where = {"language": {"$eq": language}}

        result = self.collection.query(
            query_embeddings=[self._embed(query)],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output: list[RetrievedChunk] = []
        for chunk_id, document, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            relevance = max(0.0, 1.0 - float(distance))
            if relevance < self.settings.min_relevance:
                continue
            output.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    document=document,
                    metadata=metadata,
                    relevance=relevance,
                )
            )
        return output
