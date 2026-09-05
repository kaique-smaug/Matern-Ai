"""
Reindexação densa do corpus de maternidade (MaterAI).

Lê `chunks.jsonl` — a fonte de verdade do corpus, versionada no
repositório — e constrói a coleção ChromaDB `maternidade_docs_v2` com
embeddings semânticos gerados localmente.

Por que existe: a coleção original usa TF-IDF (`tfidf_word_char_offline`),
que é recuperação lexical. A auditoria da seção 10.2 do documento de
escopo mostrou que perguntas em linguagem coloquial recuperam contexto
irrelevante — inclusive em casos de sinal de alerta. Este script produz o
componente denso do retriever híbrido.

Não depende dos PDFs originais: o JSONL já contém o texto íntegro e os
metadados de cada chunk.

Uso:

    python reindex_dense.py                    # reindexa
    python reindex_dense.py --auditar          # só relatório, não escreve
    python reindex_dense.py --force            # recria coleção existente

Referência: seções 10.2, 10.3 e 19.1 do documento de escopo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent

# Prefixos exigidos pela família E5. Omiti-los não gera erro: o modelo
# funciona e recupera pior, silenciosamente. É a pegadinha mais comum
# com esses modelos.
PREFIXO_PASSAGEM = "passage: "
PREFIXO_CONSULTA = "query: "

MODELO_PADRAO = "intfloat/multilingual-e5-base"
COLECAO_PADRAO = "maternidade_docs_v2"

CAMPOS_OBRIGATORIOS = (
    "document_title",
    "source_file",
    "section_path",
    "page_start",
    "page_end",
)


# --------------------------------------------------------------------------
# Leitura e auditoria do corpus
# --------------------------------------------------------------------------


def ler_chunks(caminho: Path) -> list[dict[str, Any]]:
    if not caminho.exists():
        raise FileNotFoundError(f"chunks.jsonl não encontrado em {caminho}")
    linhas: list[dict[str, Any]] = []
    with caminho.open(encoding="utf-8") as f:
        for n, linha in enumerate(f, start=1):
            if not linha.strip():
                continue
            try:
                linhas.append(json.loads(linha))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido na linha {n}: {exc}") from exc
    return linhas


def auditar(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Relatório do corpus antes de indexar.

    Resolve a pendência registrada na seção 19.2: o manifesto declarava
    2.177 chunks e o JSONL tinha 2.771 linhas. O número correto é o que
    sai daqui, e o manifesto é regravado a partir dele.
    """
    vistos_conteudo: dict[str, str] = {}
    duplicados: list[str] = []
    ids_repetidos: list[str] = []
    sem_metadado: list[str] = []
    vazios: list[str] = []
    ids_vistos: set[str] = set()

    for row in rows:
        cid = row.get("id", "")
        meta = row.get("metadata", {})
        texto = (row.get("text") or "").strip()

        if cid in ids_vistos:
            ids_repetidos.append(cid)
        ids_vistos.add(cid)

        if not texto:
            vazios.append(cid)
            continue

        sha = meta.get("content_sha256") or hashlib.sha256(texto.encode()).hexdigest()
        if sha in vistos_conteudo:
            duplicados.append(cid)
        else:
            vistos_conteudo[sha] = cid

        faltando = [c for c in CAMPOS_OBRIGATORIOS if meta.get(c) in (None, "")]
        if faltando:
            sem_metadado.append(f"{cid}: {', '.join(faltando)}")

    docs = Counter(r.get("metadata", {}).get("source_file", "?") for r in rows)
    tipos = Counter(r.get("metadata", {}).get("document_type", "?") for r in rows)
    tokens = [r.get("metadata", {}).get("token_count", 0) or 0 for r in rows]

    return {
        "linhas_no_jsonl": len(rows),
        "chunks_unicos": len(rows) - len(duplicados) - len(vazios),
        "duplicados_por_conteudo": len(duplicados),
        "ids_repetidos": len(ids_repetidos),
        "chunks_vazios": len(vazios),
        "documentos_distintos": len(docs),
        "tipos_de_documento": dict(tipos),
        "tokens_min": min(tokens) if tokens else 0,
        "tokens_max": max(tokens) if tokens else 0,
        "tokens_media": round(sum(tokens) / len(tokens), 1) if tokens else 0,
        "chunks_sem_metadado_obrigatorio": sem_metadado[:20],
        "total_sem_metadado": len(sem_metadado),
    }


def deduplicar(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mantém o primeiro chunk de cada conteúdo e descarta vazios."""
    vistos: set[str] = set()
    saida: list[dict[str, Any]] = []
    for row in rows:
        texto = (row.get("text") or "").strip()
        if not texto:
            continue
        meta = row.get("metadata", {})
        sha = meta.get("content_sha256") or hashlib.sha256(texto.encode()).hexdigest()
        if sha in vistos:
            continue
        vistos.add(sha)
        saida.append(row)
    return saida


def limpar_metadados(meta: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """ChromaDB aceita apenas escalares nos metadados."""
    limpo: dict[str, str | int | float | bool] = {}
    for chave, valor in meta.items():
        if valor is None:
            limpo[chave] = ""
        elif isinstance(valor, (str, int, float, bool)):
            limpo[chave] = valor
        else:
            limpo[chave] = json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return limpo


def lotes(seq: list[Any], tamanho: int) -> Iterator[list[Any]]:
    for i in range(0, len(seq), tamanho):
        yield seq[i : i + tamanho]


# --------------------------------------------------------------------------
# Indexação
# --------------------------------------------------------------------------


def indexar(
    rows: list[dict[str, Any]],
    db_path: Path,
    colecao: str,
    modelo: str,
    tamanho_lote: int,
    force: bool,
) -> dict[str, Any]:
    import chromadb  # importado aqui para que --auditar funcione sem as libs pesadas
    from sentence_transformers import SentenceTransformer

    print(f"Carregando modelo {modelo} (primeira execução baixa ~280 MB)...")
    encoder = SentenceTransformer(modelo)
    dimensao = encoder.get_sentence_embedding_dimension()
    print(f"Modelo carregado. Dimensão: {dimensao}")

    cliente = chromadb.PersistentClient(path=str(db_path))
    existentes = {c.name for c in cliente.list_collections()}
    if colecao in existentes:
        if not force:
            raise SystemExit(
                f"A coleção {colecao!r} já existe. Use --force para recriá-la."
            )
        cliente.delete_collection(colecao)
        print(f"Coleção {colecao!r} anterior removida.")

    col = cliente.create_collection(
        colecao,
        metadata={
            "hnsw:space": "cosine",
            "description": "Corpus materno-infantil, embeddings densos",
            "embedding_backend": modelo,
            "embedding_dimension": int(dimensao),
            "query_prefix": PREFIXO_CONSULTA.strip(),
            "passage_prefix": PREFIXO_PASSAGEM.strip(),
        },
    )

    total = len(rows)
    processados = 0
    for lote in lotes(rows, tamanho_lote):
        # `document` já vem enriquecido com título e caminho de seção pelo
        # pipeline de construção do corpus; é o texto certo para indexar.
        textos = [PREFIXO_PASSAGEM + (r.get("document") or r["text"]) for r in lote]
        vetores = encoder.encode(
            textos,
            batch_size=min(tamanho_lote, 32),
            normalize_embeddings=True,  # necessário para que cosseno seja produto interno
            show_progress_bar=False,
        )
        col.add(
            ids=[r["id"] for r in lote],
            documents=[r.get("document") or r["text"] for r in lote],
            metadatas=[limpar_metadados(r.get("metadata", {})) for r in lote],
            embeddings=[v.tolist() for v in vetores],
        )
        processados += len(lote)
        print(f"  {processados}/{total} chunks indexados", end="\r", flush=True)

    print(f"\nColeção {colecao!r} criada com {col.count()} chunks.")
    return {"colecao": colecao, "modelo": modelo, "dimensao": int(dimensao), "chunks": col.count()}


def gravar_manifesto(
    caminho: Path, auditoria: dict[str, Any], indexacao: dict[str, Any] | None
) -> None:
    manifesto = {
        "package_name": "chromadb_maternidade",
        "regenerated_at_utc": datetime.now(timezone.utc).isoformat(),
        "collection_name": indexacao["colecao"] if indexacao else None,
        "collection_count": indexacao["chunks"] if indexacao else None,
        "embedding_backend": indexacao["modelo"] if indexacao else None,
        "embedding_dimension": indexacao["dimensao"] if indexacao else None,
        "distance_metric": "cosine",
        "query_prefix": PREFIXO_CONSULTA.strip(),
        "passage_prefix": PREFIXO_PASSAGEM.strip(),
        "corpus_audit": auditoria,
        "content_file": "chunks.jsonl",
        "nota": (
            "Contagem obtida a partir do chunks.jsonl, fonte de verdade do corpus. "
            "Substitui o valor divergente do manifesto anterior."
        ),
    }
    caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifesto regravado em {caminho}")


# --------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(description="Reindexação densa do corpus de maternidade.")
    p.add_argument("--chunks", type=Path, default=BASE_DIR / "chunks.jsonl")
    p.add_argument("--db", type=Path, default=BASE_DIR / "chroma_db")
    p.add_argument("--colecao", default=COLECAO_PADRAO)
    p.add_argument("--modelo", default=MODELO_PADRAO)
    p.add_argument("--lote", type=int, default=64)
    p.add_argument("--force", action="store_true", help="recria a coleção se já existir")
    p.add_argument("--auditar", action="store_true", help="só relatório, não indexa")
    p.add_argument("--manifesto", type=Path, default=BASE_DIR / "collection_manifest.json")
    args = p.parse_args()

    rows = ler_chunks(args.chunks)
    auditoria = auditar(rows)

    print("=" * 62)
    print("AUDITORIA DO CORPUS")
    print("=" * 62)
    for chave, valor in auditoria.items():
        if chave == "chunks_sem_metadado_obrigatorio":
            continue
        print(f"  {chave:.<42} {valor}")
    if auditoria["total_sem_metadado"]:
        print(f"\n  Atenção: {auditoria['total_sem_metadado']} chunks sem metadado obrigatório.")
        for item in auditoria["chunks_sem_metadado_obrigatorio"]:
            print(f"    - {item}")
    print()

    if args.auditar:
        gravar_manifesto(args.manifesto, auditoria, None)
        return 0

    limpos = deduplicar(rows)
    if len(limpos) != len(rows):
        print(f"Removidos {len(rows) - len(limpos)} chunks duplicados ou vazios.")

    indexacao = indexar(limpos, args.db, args.colecao, args.modelo, args.lote, args.force)
    gravar_manifesto(args.manifesto, auditoria, indexacao)
    print("\nPróximo passo: python calibrate_threshold.py --criar-exemplo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
