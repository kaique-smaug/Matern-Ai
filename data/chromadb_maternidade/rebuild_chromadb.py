from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import chromadb
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

BASE_DIR = Path(__file__).resolve().parent
COLLECTION_NAME = 'maternidade_docs'
BATCH_SIZE = 128


def read_chunks() -> list[dict[str, Any]]:
    path = BASE_DIR / 'chunks.jsonl'
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f'JSONL inválido na linha {line_no}: {exc}') from exc
    return rows


def clean_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    result: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            result[key] = ''
        elif isinstance(value, (str, int, float, bool)):
            result[key] = value
        else:
            result[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return result


def main() -> None:
    rows = read_chunks()
    if not rows:
        raise RuntimeError('chunks.jsonl está vazio.')

    documents = [row['document'] for row in rows]
    vectorizer = FeatureUnion([
        ('word', TfidfVectorizer(
            analyzer='word', ngram_range=(1, 2), max_features=1024,
            min_df=2, max_df=0.98, strip_accents='unicode', lowercase=True,
            sublinear_tf=True, norm='l2', dtype=np.float32,
        )),
        ('char', TfidfVectorizer(
            analyzer='char_wb', ngram_range=(3, 5), max_features=512,
            min_df=2, max_df=0.995, strip_accents='unicode', lowercase=True,
            sublinear_tf=True, norm='l2', dtype=np.float32,
        )),
    ])
    matrix = vectorizer.fit_transform(documents).astype(np.float32)
    joblib.dump(vectorizer, BASE_DIR / 'tfidf_vectorizer.joblib', compress=3)

    db_path = BASE_DIR / 'chroma_db'
    if db_path.exists():
        shutil.rmtree(db_path)
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.create_collection(
        COLLECTION_NAME,
        metadata={
            'hnsw:space': 'cosine',
            'description': 'Documentos materno-infantis divididos por seção/capítulo',
            'embedding_backend': 'tfidf_word_char_offline',
            'embedding_dimension': int(matrix.shape[1]),
        },
    )

    for start in range(0, len(rows), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(rows))
        collection.add(
            ids=[row['id'] for row in rows[start:end]],
            documents=documents[start:end],
            metadatas=[clean_metadata(row['metadata']) for row in rows[start:end]],
            embeddings=matrix[start:end].toarray().astype(np.float32).tolist(),
        )

    print(f'Coleção {COLLECTION_NAME!r} reconstruída com {collection.count()} chunks.')


if __name__ == '__main__':
    main()
