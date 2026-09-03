"""Provider-neutral evidence embeddings with a deterministic local adapter."""

from __future__ import annotations

import hashlib
import math
import os
from typing import Protocol


DETERMINISTIC_EMBEDDING_DIMENSION = 1536


class EmbeddingProvider(Protocol):
    name: str
    version: str
    dimension: int

    def embed(self, text: str) -> tuple[float, ...]: ...


class DeterministicEmbeddingProvider:
    """Generate reproducible unit vectors without an external model or secret."""

    name = "deterministic-fake"
    version = "embedding-v1"
    dimension = DETERMINISTIC_EMBEDDING_DIMENSION

    def embed(self, text: str) -> tuple[float, ...]:
        normalized = text.strip()
        if not normalized:
            raise ValueError("cannot embed empty evidence text")
        seed = hashlib.sha256(normalized.encode("utf-8")).digest()
        values = []
        for index in range(self.dimension):
            digest = hashlib.sha256(seed + index.to_bytes(4, "big")).digest()
            integer = int.from_bytes(digest[:8], "big")
            values.append((integer / 2**64) * 2.0 - 1.0)
        norm = math.sqrt(sum(value * value for value in values))
        return tuple(value / norm for value in values)


def embedding_provider_from_env() -> EmbeddingProvider:
    mode = os.getenv("AUTODATA_EMBEDDING_MODE", "deterministic-fake")
    if mode == "deterministic-fake":
        return DeterministicEmbeddingProvider()
    raise ValueError(f"unsupported embedding provider mode: {mode}")


def format_pgvector(vector: tuple[float, ...]) -> str:
    if len(vector) != DETERMINISTIC_EMBEDDING_DIMENSION:
        raise ValueError(
            f"embedding dimension must be {DETERMINISTIC_EMBEDDING_DIMENSION}, got {len(vector)}"
        )
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("embedding vector must contain only finite values")
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
