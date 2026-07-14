from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Iterable

from chromadb.utils import embedding_functions


class LocalHashEmbeddingFunction:
    def __init__(self, dimensions: int = 64):
        self.dimensions = dimensions

    def __call__(self, input: Iterable[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"\b[a-z0-9_]+\b", text.lower())

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            index = int(digest, 16) % self.dimensions
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def name(self) -> str:
        return f"local-hash-{self.dimensions}"


class ResilientEmbeddingFunction:
    def __init__(self, model_name: str = "BAAI/bge-small-en", fallback_dimensions: int = 64):
        self.model_name = model_name
        self._primary = None
        self._fallback = LocalHashEmbeddingFunction(dimensions=fallback_dimensions)
        self._use_fallback = False

    def __call__(self, input: Iterable[str]) -> list[list[float]]:
        if not self._use_fallback:
            try:
                if self._primary is None:
                    self._primary = embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name=self.model_name
                    )
                return self._primary(input)
            except Exception:
                self._use_fallback = True
        return self._fallback(input)

    def name(self) -> str:
        if self._use_fallback:
            return self._fallback.name()
        return self.model_name


def build_embedding_function(model_name: str = "BAAI/bge-small-en"):
    if os.getenv("CHROMA_LEGACY_EMBEDDINGS", "local").lower() == "local":
        return LocalHashEmbeddingFunction()
    return ResilientEmbeddingFunction(model_name=model_name)
