from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.llm import LLMService


async def test_embedding_sends_text_dimensions_and_batches():
    service = LLMService()
    service.settings = SimpleNamespace(
        EMBEDDING_MODEL='qwen3.7-text-embedding',
        EMBEDDING_API_KEY='test-key',
        EMBEDDING_API_BASE='https://example.invalid/v1',
        EMBEDDING_DIM=1024,
        EMBEDDING_BATCH_SIZE=10,
    )
    embeddings = service.embeddings
    assert embeddings.chunk_size == 10
    assert embeddings.dimensions == 1024
    assert embeddings.check_embedding_ctx_length is False

    async def respond(**kwargs):
        return {'data': [{'embedding': [0.0] * 1024} for _ in kwargs['input']]}

    client = AsyncMock()
    client.create.side_effect = respond
    embeddings.async_client = client
    texts = [f'金融文档{i}' for i in range(11)]
    vectors = await service.embed(texts)
    assert len(vectors) == 11
    assert all(len(vector) == 1024 for vector in vectors)
    calls = client.create.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs['input'] == texts[:10]
    assert calls[1].kwargs['input'] == texts[10:]
    for call in calls:
        assert call.kwargs['dimensions'] == 1024
        assert call.kwargs['encoding_format'] == 'float'
        assert 'batch_size' not in call.kwargs


async def test_embedding_rejects_wrong_dimensions_and_nonfinite_values():
    import pytest
    service = LLMService()
    service.settings = SimpleNamespace(EMBEDDING_DIM=2)
    service._embeddings = AsyncMock()
    for vectors in ([], [[1.]], [[float('nan'), 0.]], [[float('inf'), 0.]]):
        service._embeddings.aembed_documents.return_value = vectors
        with pytest.raises(ValueError, match='Embedding'):
            await service.embed(['text'])


async def test_embedding_caps_provider_batch_size():
    service = LLMService()
    service.settings = SimpleNamespace(
        EMBEDDING_MODEL='qwen3.7-text-embedding',
        EMBEDDING_API_KEY='test-key',
        EMBEDDING_API_BASE='https://example.invalid/v1',
        EMBEDDING_DIM=2,
        EMBEDDING_BATCH_SIZE=100,
    )
    embeddings = service.embeddings
    assert embeddings.chunk_size == 20
