from infrastructure.vector_store.embedding_pipeline import PersonaEmbeddingPipeline


class _FakeEmptyCollection:
    def get(self, *args, **kwargs):
        # Chroma-like shape
        return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}


def test_get_collection_contents_empty_returns_empty_list():
    pipeline = PersonaEmbeddingPipeline(client=object(), collection=_FakeEmptyCollection())
    assert pipeline.get_collection_contents(account_id="dreamer") == []


