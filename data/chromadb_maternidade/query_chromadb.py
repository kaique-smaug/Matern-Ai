from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import chromadb
import joblib
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
COLLECTION_NAME = 'maternidade_docs'


def load_runtime() -> tuple[Any, Any]:
    vectorizer_path = BASE_DIR / 'tfidf_vectorizer.joblib'
    db_path = BASE_DIR / 'chroma_db'
    if not vectorizer_path.exists():
        raise FileNotFoundError(f'Vetorizador não encontrado: {vectorizer_path}')
    if not db_path.exists():
        raise FileNotFoundError(f'Banco ChromaDB não encontrado: {db_path}')

    vectorizer = joblib.load(vectorizer_path)
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection(COLLECTION_NAME)
    return vectorizer, collection


def build_where(args: argparse.Namespace) -> dict[str, Any] | None:
    conditions: list[dict[str, Any]] = []
    if args.document_type:
        conditions.append({'document_type': {'$eq': args.document_type}})
    if args.source_file:
        conditions.append({'source_file': {'$eq': args.source_file}})
    if args.language:
        conditions.append({'language': {'$eq': args.language}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {'$and': conditions}


def query(question: str, n_results: int, where: dict[str, Any] | None = None) -> dict[str, Any]:
    vectorizer, collection = load_runtime()
    query_embedding = vectorizer.transform([question]).toarray().astype(np.float32).tolist()

    kwargs: dict[str, Any] = {
        'query_embeddings': query_embedding,
        'n_results': n_results,
        'include': ['documents', 'metadatas', 'distances'],
    }
    if where:
        kwargs['where'] = where
    return collection.query(**kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Consulta local à coleção ChromaDB de maternidade.'
    )
    parser.add_argument('pergunta', help='Texto da consulta.')
    parser.add_argument('-n', '--n-results', type=int, default=5, help='Quantidade de resultados.')
    parser.add_argument('--document-type', help='Filtrar por document_type.')
    parser.add_argument('--source-file', help='Filtrar pelo nome exato do PDF.')
    parser.add_argument('--language', help='Filtrar pelo idioma, por exemplo pt.')
    parser.add_argument('--json', action='store_true', help='Exibir o retorno integral como JSON.')
    args = parser.parse_args()

    if args.n_results < 1:
        parser.error('--n-results deve ser maior que zero.')

    results = query(args.pergunta, args.n_results, build_where(args))
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    ids = results.get('ids', [[]])[0]
    documents = results.get('documents', [[]])[0]
    metadatas = results.get('metadatas', [[]])[0]
    distances = results.get('distances', [[]])[0]

    if not ids:
        print('Nenhum resultado encontrado.')
        return

    for position, (chunk_id, document, metadata, distance) in enumerate(
        zip(ids, documents, metadatas, distances), start=1
    ):
        score = max(0.0, 1.0 - float(distance))
        print(f'\n[{position}] score={score:.4f}')
        print(f"Documento: {metadata.get('document_title', '')}")
        print(f"Arquivo: {metadata.get('source_file', '')}")
        print(f"Páginas: {metadata.get('page_start', '')}-{metadata.get('page_end', '')}")
        print(f"Seção: {metadata.get('section_path', '')}")
        print(f'Chunk ID: {chunk_id}')
        print('-' * 80)
        print(document)


if __name__ == '__main__':
    main()
