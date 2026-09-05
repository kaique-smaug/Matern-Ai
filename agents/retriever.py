"""
Retriever híbrido do MaterAI: denso + lexical, com fusão RRF.

Combina dois sinais complementares:

* **Denso** — embeddings E5 sobre a coleção `maternidade_docs_v2`.
  Captura significado. Resolve "meu bebê não está mexendo" -> movimentação
  fetal, que a busca lexical erra.

* **Lexical** — o índice TF-IDF já construído pelo projeto. Captura termo
  exato. Resolve siglas e nomes de exames (TOTG, VDRL, HbA1c), onde o
  denso costuma ser mais fraco.

A fusão é por Reciprocal Rank Fusion, que combina *posições* e não
*pontuações* — assim não é preciso normalizar escalas entre dois métodos
que produzem números incomparáveis.

Sobre o limiar: o retriever sempre devolve os k mais próximos, mesmo
quando nada é relevante. Sem um piso, texto irrelevante entra no prompt
como se fosse fundamentação. Quando nenhum candidato passa do limiar, a
resposta é uma lista vazia, e o chamador deve aplicar RN-06 — declarar
que a informação não está na base, em vez de improvisar.

Referência: seções 10.3 e 19.3 do documento de escopo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

BASE_DIR = Path(__file__).resolve().parent

PREFIXO_CONSULTA = "query: "
PREFIXO_PASSAGEM = "passage: "

MODELO_PADRAO = "intfloat/multilingual-e5-base"
COLECAO_PADRAO = "maternidade_docs_v2"

# Valor inicial da seção 19.3, deliberadamente enviesado para a recusa.
# Confirmar com calibrate_threshold.py na etapa 4; não reaproveitar
# números do TF-IDF, as escalas são diferentes.
LIMIAR_DENSO_PADRAO = 0.78

# O TF-IDF produz cossenos bem mais baixos. Este limiar existe para o caso
# de siglas, em que o lexical acerta e o denso fica abaixo do piso.
LIMIAR_LEXICAL_PADRAO = 0.35

K_CANDIDATOS = 10   # por método, antes da fusão
K_FINAL = 4         # chunks enviados ao LLM
RRF_K = 60          # constante da fusão; 60 é o valor usual da literatura


# --------------------------------------------------------------------------
# Estruturas
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ChunkRecuperado:
    """Um trecho recuperado, com o necessário para citar a fonte (RF-10)."""

    chunk_id: str
    texto: str
    document_title: str
    source_file: str
    section_path: str
    page_start: int | None
    page_end: int | None
    score_denso: float
    score_lexical: float
    score_rrf: float

    def citacao(self) -> str:
        paginas = ""
        if self.page_start:
            paginas = (
                f", p. {self.page_start}"
                if self.page_start == self.page_end or not self.page_end
                else f", p. {self.page_start}-{self.page_end}"
            )
        return f"{self.document_title}{paginas}"

    def para_prompt(self) -> str:
        return f"[Fonte: {self.citacao()} | Seção: {self.section_path}]\n{self.texto}"


@dataclass
class ResultadoRecuperacao:
    chunks: list[ChunkRecuperado]
    melhor_denso: float
    melhor_lexical: float
    descartados_por_limiar: int

    @property
    def vazio(self) -> bool:
        """True quando nada passou do limiar. O chamador deve aplicar RN-06."""
        return not self.chunks

    def contexto_para_prompt(self) -> str:
        return "\n\n---\n\n".join(c.para_prompt() for c in self.chunks)

    def fontes(self) -> list[dict[str, Any]]:
        return [
            {
                "documento": c.document_title,
                "arquivo": c.source_file,
                "secao": c.section_path,
                "pagina_inicio": c.page_start,
                "pagina_fim": c.page_end,
                "chunk_id": c.chunk_id,
            }
            for c in self.chunks
        ]


# --------------------------------------------------------------------------
# Fusão — função pura, testável sem ChromaDB
# --------------------------------------------------------------------------


def fundir_rrf(
    rankings: Sequence[Sequence[str]], k: int = RRF_K
) -> dict[str, float]:
    """
    Reciprocal Rank Fusion.

        score(d) = Σ_i  1 / (k + rank_i(d))

    `rankings` é uma lista de listas de ids, cada uma já ordenada do melhor
    para o pior. Documentos ausentes de um ranking simplesmente não somam
    por ele. A constante k amortece o peso das primeiras posições, evitando
    que um único método domine a fusão.
    """
    pontos: dict[str, float] = {}
    for ranking in rankings:
        for posicao, doc_id in enumerate(ranking, start=1):
            pontos[doc_id] = pontos.get(doc_id, 0.0) + 1.0 / (k + posicao)
    return pontos


# --------------------------------------------------------------------------
# Índices
# --------------------------------------------------------------------------


class IndiceDenso:
    """Busca semântica sobre a coleção ChromaDB densa."""

    def __init__(
        self,
        db_path: Path = BASE_DIR / "chroma_db",
        colecao: str = COLECAO_PADRAO,
        modelo: str = MODELO_PADRAO,
    ) -> None:
        import chromadb
        from sentence_transformers import SentenceTransformer

        self._encoder = SentenceTransformer(modelo)
        cliente = chromadb.PersistentClient(path=str(db_path))
        self._col = cliente.get_collection(colecao)

    def buscar(self, pergunta: str, k: int = K_CANDIDATOS) -> list[tuple[str, float, dict]]:
        """Devolve (chunk_id, similaridade_cosseno, metadados)."""
        vetor = self._encoder.encode(
            [PREFIXO_CONSULTA + pergunta],  # o prefixo não é opcional em E5
            normalize_embeddings=True,
        )[0]
        r = self._col.query(
            query_embeddings=[vetor.tolist()],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        saida = []
        for cid, doc, meta, dist in zip(
            r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]
        ):
            # ChromaDB com hnsw:space=cosine devolve DISTÂNCIA, não similaridade.
            similaridade = 1.0 - float(dist)
            meta = dict(meta)
            meta["_documento"] = doc
            saida.append((cid, similaridade, meta))
        return saida


class IndiceLexical:
    """
    Busca por TF-IDF, mantida em memória a partir do chunks.jsonl.

    Deliberadamente não usa a coleção ChromaDB legada: assim o corpus tem
    uma fonte de verdade só (o JSONL), e o índice lexical é reconstruído
    junto com o denso, sem risco de ficarem dessincronizados.
    """

    def __init__(
        self,
        chunks_path: Path = BASE_DIR / "chunks.jsonl",
        vectorizer_path: Path | None = BASE_DIR / "tfidf_vectorizer.joblib",
    ) -> None:
        import joblib
        import numpy as np

        self._np = np
        self._rows = [
            json.loads(l) for l in chunks_path.read_text(encoding="utf-8").splitlines() if l.strip()
        ]
        documentos = [r.get("document") or r["text"] for r in self._rows]
        self._ids = [r["id"] for r in self._rows]

        if vectorizer_path and vectorizer_path.exists():
            self._vec = joblib.load(vectorizer_path)
            matriz = self._vec.transform(documentos)
        else:
            # Reconstrói com os mesmos parâmetros do rebuild_chromadb.py
            # original, para que o comportamento não mude se o .joblib
            # estiver ausente.
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.pipeline import FeatureUnion

            self._vec = FeatureUnion([
                ("word", TfidfVectorizer(
                    analyzer="word", ngram_range=(1, 2), max_features=1024, min_df=2,
                    max_df=0.98, strip_accents="unicode", lowercase=True,
                    sublinear_tf=True, norm="l2", dtype=np.float32)),
                ("char", TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(3, 5), max_features=512, min_df=2,
                    max_df=0.995, strip_accents="unicode", lowercase=True,
                    sublinear_tf=True, norm="l2", dtype=np.float32)),
            ])
            matriz = self._vec.fit_transform(documentos)

        m = np.asarray(matriz.todense(), dtype=np.float32)
        normas = np.linalg.norm(m, axis=1, keepdims=True)
        self._matriz = m / np.maximum(normas, 1e-9)
        self._por_id = {r["id"]: r for r in self._rows}

    def buscar(self, pergunta: str, k: int = K_CANDIDATOS) -> list[tuple[str, float, dict]]:
        np = self._np
        v = np.asarray(self._vec.transform([pergunta]).todense(), dtype=np.float32)[0]
        v = v / max(float(np.linalg.norm(v)), 1e-9)
        sims = self._matriz @ v
        topo = np.argsort(-sims)[:k]
        saida = []
        for i in topo:
            row = self._rows[int(i)]
            meta = dict(row.get("metadata", {}))
            meta["_documento"] = row.get("document") or row["text"]
            saida.append((row["id"], float(sims[int(i)]), meta))
        return saida


# --------------------------------------------------------------------------
# Retriever híbrido
# --------------------------------------------------------------------------


class RetrieverHibrido:
    """Orquestra os dois índices, funde por RRF e aplica o limiar."""

    def __init__(
        self,
        indice_denso: IndiceDenso | None = None,
        indice_lexical: IndiceLexical | None = None,
        limiar_denso: float = LIMIAR_DENSO_PADRAO,
        limiar_lexical: float = LIMIAR_LEXICAL_PADRAO,
    ) -> None:
        self.denso = indice_denso if indice_denso is not None else IndiceDenso()
        self.lexical = indice_lexical if indice_lexical is not None else IndiceLexical()
        self.limiar_denso = limiar_denso
        self.limiar_lexical = limiar_lexical

    def buscar(
        self,
        pergunta: str,
        k_final: int = K_FINAL,
        k_candidatos: int = K_CANDIDATOS,
        aplicar_limiar: bool = True,
    ) -> ResultadoRecuperacao:
        """
        `aplicar_limiar=False` é usado pelo calibrate_threshold.py, que
        precisa observar as pontuações brutas. Em produção, sempre True.
        """
        densos = self.denso.buscar(pergunta, k_candidatos)
        lexicais = self.lexical.buscar(pergunta, k_candidatos)

        score_denso = {cid: s for cid, s, _ in densos}
        score_lexical = {cid: s for cid, s, _ in lexicais}
        metadados: dict[str, dict] = {}
        for cid, _, meta in list(densos) + list(lexicais):
            metadados.setdefault(cid, meta)

        pontos = fundir_rrf([[c for c, _, _ in densos], [c for c, _, _ in lexicais]])
        ordenados = sorted(pontos.items(), key=lambda kv: -kv[1])

        chunks: list[ChunkRecuperado] = []
        descartados = 0
        for cid, rrf in ordenados:
            sd = score_denso.get(cid, 0.0)
            sl = score_lexical.get(cid, 0.0)

            # Basta um dos sinais passar: o denso cobre linguagem coloquial,
            # o lexical cobre sigla e nome de exame.
            if aplicar_limiar and sd < self.limiar_denso and sl < self.limiar_lexical:
                descartados += 1
                continue

            meta = metadados.get(cid, {})
            chunks.append(
                ChunkRecuperado(
                    chunk_id=cid,
                    texto=meta.get("_documento", ""),
                    document_title=meta.get("document_title", "documento sem título"),
                    source_file=meta.get("source_file", ""),
                    section_path=meta.get("section_path", ""),
                    page_start=_int_ou_none(meta.get("page_start")),
                    page_end=_int_ou_none(meta.get("page_end")),
                    score_denso=sd,
                    score_lexical=sl,
                    score_rrf=rrf,
                )
            )
            if len(chunks) >= k_final:
                break

        return ResultadoRecuperacao(
            chunks=chunks,
            melhor_denso=max(score_denso.values(), default=0.0),
            melhor_lexical=max(score_lexical.values(), default=0.0),
            descartados_por_limiar=descartados,
        )


def _int_ou_none(valor: Any) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import argparse

    p = argparse.ArgumentParser(description="Consulta ao retriever híbrido.")
    p.add_argument("pergunta")
    p.add_argument("-n", type=int, default=K_FINAL)
    p.add_argument("--sem-limiar", action="store_true")
    args = p.parse_args()

    r = RetrieverHibrido().buscar(
        args.pergunta, k_final=args.n, aplicar_limiar=not args.sem_limiar
    )
    if r.vazio:
        print("Nada acima do limiar. Aplicar RN-06: declarar que não há a informação na base.")
        print(f"Melhor denso: {r.melhor_denso:.3f} | melhor lexical: {r.melhor_lexical:.3f}")
    else:
        for c in r.chunks:
            print(f"\n[{c.score_rrf:.4f}] denso={c.score_denso:.3f} lexical={c.score_lexical:.3f}")
            print(f"  {c.citacao()}")
            print(f"  {c.section_path[:90]}")
            print(f"  {c.texto[:200].strip()}...")
