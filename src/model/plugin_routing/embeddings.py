"""Embedding provider interfaces and a deterministic local stub implementation."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Defines a narrow runtime embedding interface for plugin routing.

from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import math


class EmbeddingProvider(ABC):
    """Runtime-focused embedding provider interface for plugin routing."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Returns the identifier used to scope cache entries."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embeds one or more texts into dense numeric vectors."""

    def embed_text(self, text: str) -> list[float]:
        """Embeds a single text string."""
        return self.embed_texts([text])[0]


class HashEmbeddingProvider(EmbeddingProvider):
    """Generates deterministic local embeddings for development and tests."""

    def __init__(self, model_id: str = "hash-embedding-v1", dimensions: int = 32):
        if dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")
        self._model_id = model_id.strip()
        self._dimensions = dimensions

    @property
    def model_id(self) -> str:
        """Returns the embedding model identifier."""
        return self._model_id

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embeds text values into deterministic unit-length vectors."""
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> list[float]:
        raw_text = text.strip()
        if not raw_text:
            return [0.0] * self._dimensions

        values: list[float] = []
        counter = 0
        while len(values) < self._dimensions:
            digest = hashlib.sha256(f"{raw_text}|{counter}".encode("utf-8")).digest()
            for index in range(0, len(digest), 4):
                chunk = digest[index:index + 4]
                integer = int.from_bytes(chunk, byteorder="big", signed=False)
                values.append((integer / 4294967295.0) * 2.0 - 1.0)
                if len(values) == self._dimensions:
                    break
            counter += 1

        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            return [0.0] * self._dimensions
        return [value / norm for value in values]
