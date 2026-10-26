import asyncio
from unittest.mock import AsyncMock

import numpy as np
import pytest

from utils.local_embeddings import LocalEmbeddingClient, get_vector_store


class Response:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return {"data": [{"embedding": [0.5] * 768}]}


class Session:
    def post(self, url, **kwargs):
        self.url, self.kwargs = url, kwargs
        return self.response


def test_local_endpoint_and_payload():
    session = Session()
    session.response = Response()
    client = LocalEmbeddingClient(base_url="http://localhost:1234/v1/", api_key="test")
    result = asyncio.run(client.embed("hello", session))
    assert session.url == "http://localhost:1234/v1/embeddings"
    assert session.kwargs["json"]["model"] == "text-embedding-nomic-embed-text-v1.5"
    assert session.kwargs["headers"]["Authorization"] == "Bearer test"
    assert result.shape == (768,)
    assert result.dtype == np.float32


@pytest.mark.parametrize("embedding", [[0.0] * 3, [float("nan")] * 768, [0.0] * 768])
def test_invalid_embeddings_raise(embedding):
    session = Session()
    session.response = Response()
    session.response.json = AsyncMock(return_value={"data": [{"embedding": embedding}]})
    with pytest.raises(ValueError):
        asyncio.run(LocalEmbeddingClient().embed("hello", session))


def test_http_error_raises_without_cloud_fallback():
    session = Session()
    session.response = Response()
    session.response.status = 404
    with pytest.raises(RuntimeError, match="404"):
        asyncio.run(LocalEmbeddingClient().embed("hello", session))


def test_store_isolated_and_scoped(tmp_path):
    store = get_vector_store(tmp_path)
    assert store.db_path == str(tmp_path / "local-nomic-v1")
    embedding = np.ones(768, dtype=np.float32)
    store.add("a", "channel", "mine", embedding)
    store.add("b", "channel", "other", embedding)
    assert [row["text"] for row in store.search("a", "channel", embedding)] == ["mine"]
    assert store.search("a", "different", embedding) == []


def test_store_rejects_persisted_dimension_mismatch(tmp_path):
    import faiss
    folder = tmp_path / "local-nomic-v1"
    folder.mkdir()
    faiss.write_index(faiss.IndexFlatL2(3), str(folder / "faiss.index"))
    with pytest.raises(ValueError, match="dimension"):
        get_vector_store(tmp_path)
