from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import chromadb
import joblib
import numpy as np

from .config import Settings
from .embeddings import build_tfidf_vectorizer


def load_chunks(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("id") or not row.get("document"):
                raise ValueError(f"Chunk inválido na linha {line_number}")
            rows.append(row)
    return rows


def clean_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    clean: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            clean[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = json.dumps(value, ensure_ascii=False)
    return clean


def build_tfidf(settings: Settings, reset: bool = True) -> int:
    rows = load_chunks(settings.chunks_path)
    documents = [row["document"] for row in rows]

    if reset and settings.chroma_dir.exists():
        shutil.rmtree(settings.chroma_dir)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)

    vectorizer = build_tfidf_vectorizer(documents)
    joblib.dump(vectorizer, settings.vectorizer_path)
    embeddings = vectorizer.transform(documents).toarray().astype(np.float32)

    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    collection = client.get_or_create_collection(
        settings.collection_name,
        metadata={"hnsw:space": "cosine", "embedding_provider": "tfidf"},
    )

    batch_size = 100
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        collection.upsert(
            ids=[row["id"] for row in batch],
            documents=[row["document"] for row in batch],
            metadatas=[clean_metadata(row["metadata"]) for row in batch],
            embeddings=embeddings[start : start + len(batch)].tolist(),
        )
    return collection.count()


def build_openai(settings: Settings, reset: bool = True) -> int:
    if not settings.openai_api_key:
        raise RuntimeError("Defina OPENAI_API_KEY antes de usar embeddings OpenAI.")

    from langchain_chroma import Chroma
    from langchain_core.documents import Document
    from langchain_openai import OpenAIEmbeddings

    rows = load_chunks(settings.chunks_path)
    if reset and settings.chroma_dir.exists():
        shutil.rmtree(settings.chroma_dir)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)

    embedding = OpenAIEmbeddings(model=settings.openai_embedding_model)
    store = Chroma(
        collection_name=settings.collection_name,
        embedding_function=embedding,
        persist_directory=str(settings.chroma_dir),
        collection_metadata={"hnsw:space": "cosine", "embedding_provider": "openai"},
    )
    documents = [
        Document(page_content=row["document"], metadata=clean_metadata(row["metadata"]), id=row["id"])
        for row in rows
    ]
    for start in range(0, len(documents), 100):
        batch = documents[start : start + 100]
        store.add_documents(batch, ids=[doc.id for doc in batch])
    return len(documents)


def main() -> None:
    parser = argparse.ArgumentParser(description="Constrói a coleção vetorial MaterAI")
    parser.add_argument("--provider", choices=["tfidf", "openai"], default=None)
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    provider = args.provider or settings.embedding_provider
    count = (
        build_tfidf(settings, reset=not args.no_reset)
        if provider == "tfidf"
        else build_openai(settings, reset=not args.no_reset)
    )
    print(f"Coleção '{settings.collection_name}' criada com {count} chunks ({provider}).")


if __name__ == "__main__":
    main()
