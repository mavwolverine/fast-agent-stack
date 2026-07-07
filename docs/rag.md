# RAG Pipeline

fast-agent-stack provides a full retrieval-augmented generation pipeline: chunk documents, embed them, store vectors, and retrieve at query time.

## Installation

```bash
pip install "fast-agent-stack[vector-qdrant,embedding-openai,extract-pdf]"
```

Mix and match vector, embedding, and extraction extras as needed.

## Vector Stores

### Qdrant

```python
class Settings(BaseSettings):
    vector_db: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
```

### pgvector

```python
class Settings(BaseSettings):
    vector_db: str = "pgvector"
    pgvector_database_url: str = "postgresql+asyncpg://user:pass@localhost/db"
    pgvector_collection_schema: str = "public"
```

### OpenSearch / Weaviate

Set `vector_db = "opensearch"` or `vector_db = "weaviate"` with the corresponding URL settings.

## Embedding Backends

```python
class Settings(BaseSettings):
    embedding_provider: str = "local"       # fastembed, no API key needed
    # embedding_provider: str = "openai"    # text-embedding-3-small
    # embedding_provider: str = "bedrock"   # amazon.titan-embed-text-v2
```

## Document Extraction

Extract text from uploaded files before chunking:

```python
from fast_agent_stack.core.extraction import get_extraction_backend

extractor = get_extraction_backend("pdf")   # "docx", "xlsx", "eml"
text = await extractor.extract(file_bytes)
```

## RAG Service

```python
from fast_agent_stack.core.rag import RagService

rag = RagService(settings)

# Ingest a document
await rag.ingest(
    collection="docs",
    document_id="doc-1",
    text=extracted_text,
    metadata={"source": "manual.pdf"},
)

# Retrieve relevant chunks
results = await rag.retrieve(
    collection="docs",
    query="how to configure auth",
    top_k=5,
)
# results: list[VectorSearchResult(id, score, content, metadata)]
```

## Chunking

Configure chunking strategy in settings:

```python
class Settings(BaseSettings):
    rag_chunk_size: int = 512          # characters per chunk
    rag_chunk_overlap: int = 64        # overlap between chunks
    rag_chunking_strategy: str = "fixed"  # "fixed" or "sentence"
```

## Custom Vector Store

Point `vector_db` at a dotted Python path:

```python
vector_db: str = "myproject.stores.MyVectorStore"
```

Your class must implement `VectorStoreProtocol` (create_collection, upsert, search, delete, close).
