from __future__ import annotations

from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion


def build_tfidf_vectorizer(texts: Iterable[str]) -> FeatureUnion:
    vectorizer = FeatureUnion(
        [
            (
                "words",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    max_features=1024,
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "chars",
                TfidfVectorizer(
                    analyzer="char_wb",
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(3, 5),
                    max_features=512,
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
        ]
    )
    vectorizer.fit(list(texts))
    return vectorizer


class TfidfEmbeddingFunction:
    """Adapter compatível com Chroma para o vetorizador persistido."""

    def __init__(self, vectorizer_path: Path):
        self.vectorizer = joblib.load(vectorizer_path)

    def __call__(self, input: list[str]) -> list[list[float]]:  # Chroma protocol
        matrix = self.vectorizer.transform(input)
        return matrix.toarray().astype(np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self(text and [text] or [""])[0]
