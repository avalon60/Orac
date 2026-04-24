"""In-memory similarity index for plugin routing candidates."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Provides brute-force cosine similarity search over plugin embeddings.

from __future__ import annotations

import math

from model.plugin_routing.models import PluginCandidate


class PluginIntentIndex:
    """Stores plugin vectors in memory and returns scored candidates."""

    def __init__(self):
        self._vectors: dict[str, tuple[float, ...]] = {}
        self._vector_size = 0

    def build(self, vectors: dict[str, list[float]]) -> None:
        """Rebuilds the in-memory index from plugin vectors."""
        self._vectors = {}
        self._vector_size = 0

        for plugin_id, vector in vectors.items():
            if not vector:
                raise ValueError(f"Vector for plugin '{plugin_id}' must not be empty")
            if self._vector_size == 0:
                self._vector_size = len(vector)
            elif len(vector) != self._vector_size:
                raise ValueError("All plugin vectors must share the same dimensionality")
            self._vectors[plugin_id] = tuple(self._normalise(vector))

    def search(
        self,
        query_vector: list[float],
        top_n: int = 5,
        min_score: float | None = None,
    ) -> list[PluginCandidate]:
        """Returns top-N scored plugin candidates using cosine similarity."""
        if top_n <= 0 or not self._vectors:
            return []
        if self._vector_size == 0:
            return []
        if len(query_vector) != self._vector_size:
            raise ValueError(
                f"Query vector dimension {len(query_vector)} does not match index dimension {self._vector_size}"
            )

        query = self._normalise(query_vector)
        candidates: list[PluginCandidate] = []
        for plugin_id, vector in self._vectors.items():
            score = sum(left * right for left, right in zip(query, vector))
            if min_score is not None and score < min_score:
                continue
            candidates.append(PluginCandidate(plugin_id=plugin_id, score=score))

        return sorted(candidates, key=lambda item: item.score, reverse=True)[:top_n]

    def size(self) -> int:
        """Returns the number of indexed plugins."""
        return len(self._vectors)

    @staticmethod
    def _normalise(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(float(value) * float(value) for value in vector))
        if norm == 0.0:
            return [0.0 for _ in vector]
        return [float(value) / norm for value in vector]
