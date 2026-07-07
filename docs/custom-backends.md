# Custom Backends

Every backend family in fast-agent-stack accepts a dotted Python path in place of a built-in alias (ADR-012). This lets you plug in any implementation without forking the framework.

## How It Works

In settings, wherever you'd normally write a backend alias like `"qdrant"`, you can instead write a fully-qualified class name:

```python
class Settings(BaseSettings):
    vector_db: str = "myproject.stores.PineconeVectorStore"
    embedding_provider: str = "myproject.embeddings.CohereEmbeddingBackend"
    storage_backend: str = "myproject.storage.GCSStorageBackend"
    llm_provider: str = "myproject.llm.VertexAIBackend"
    auth_backends: list[str] = ["myproject.auth.OktaBackend"]
    email_backend: str = "myproject.email.SendGridBackend"
```

The factory uses `importlib` to import and instantiate the class, passing `settings` as the first argument.

## Required Protocols

Each family has a Protocol your class must fully implement (Invariant I1):

| Family | Protocol | Required methods |
|--------|----------|-----------------|
| LLM | `LLMBackend` | `model_id`, `complete`, `stream`, `count_tokens` |
| Vector store | `VectorStoreProtocol` | `create_collection`, `upsert`, `search`, `delete`, `close` |
| Embedding | `EmbeddingProtocol` | `embed`, `embed_batch`, `dimensions`, `close` |
| Storage | `StorageProtocol` | `put`, `get`, `delete`, `url` |
| Auth backend | `AuthBackendProtocol` | `authenticate`, `create_tokens`, `refresh`, `revoke` |
| Email | `EmailProtocol` | `send` |

## Example: Custom Vector Store

```python
from fast_agent_stack.core.vector import VectorStoreProtocol, VectorSearchResult

class PineconeVectorStore:
    def __init__(self, settings) -> None:
        import pinecone
        self._client = pinecone.Pinecone(api_key=settings.pinecone_api_key)

    async def create_collection(self, name, dimensions, *, distance_metric="cosine"):
        self._client.create_index(name, dimension=dimensions, metric=distance_metric)

    async def upsert(self, collection, id, vector, metadata, *, content=None):
        index = self._client.Index(collection)
        index.upsert([(id, vector, metadata)])

    async def search(self, collection, vector, *, top_k=10, filter=None):
        index = self._client.Index(collection)
        results = index.query(vector=vector, top_k=top_k, filter=filter, include_metadata=True)
        return [
            VectorSearchResult(id=m.id, score=m.score, metadata=m.metadata, content=None)
            for m in results.matches
        ]

    async def delete(self, collection, id):
        self._client.Index(collection).delete(ids=[id])

    async def close(self) -> None:
        pass
```

## Escape Hatch (I4)

Every wrapped component must expose its underlying client as `_client`:

```python
class MyBackend:
    def __init__(self, settings) -> None:
        self._client = ThirdPartySDK(...)  # always accessible
```

Users can access `backend._client` directly when they need something the abstraction doesn't expose.

## Dependencies

Custom backends are your responsibility. Add their dependencies to your project's `pyproject.toml` — not to the framework package.
