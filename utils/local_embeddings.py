"""LM Studio semantic memory, isolated from legacy Gemini vector indexes."""

import logging
from pathlib import Path

import aiohttp
import numpy as np

import config
from utils.vector_db import VectorDB

logger = logging.getLogger(__name__)


class LocalEmbeddingClient:
    dimension = 768

    def __init__(self, base_url=None, api_key=None):
        base = (base_url or config.LMSTUDIO_API_URL).rstrip("/")
        self.url = base + ("/embeddings" if base.endswith("/v1") else "/v1/embeddings")
        self.api_key = config.LMSTUDIO_API_KEY if api_key is None else api_key
        # Changing model also requires a new vector-store namespace, even at 768 dimensions.
        self.model = "text-embedding-nomic-embed-text-v1.5"

    async def embed(self, text, session):
        """Return a validated local vector; callers decide how to surface failure."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with session.post(
                self.url,
                json={"model": self.model, "input": text},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"LM Studio embedding request failed (HTTP {response.status})")
                data = await response.json()
            vector = np.asarray(data["data"][0]["embedding"], dtype=np.float32)
            if vector.shape != (self.dimension,) or not np.isfinite(vector).all():
                raise ValueError(f"Expected {self.dimension} finite embedding dimensions")
            if np.linalg.norm(vector) == 0:
                raise ValueError("Embedding must not be a zero vector")
            return vector
        except Exception:
            logger.warning("Local semantic-memory embedding failed", exc_info=True)
            raise


def get_vector_store(root="vector_db"):
    """Keep original Gemini files untouched; same dimension does not imply compatibility."""
    return VectorDB(str(Path(root) / "local-nomic-v1"))
