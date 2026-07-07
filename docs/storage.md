# Storage & Extraction

## Storage Backends

fast-agent-stack supports three storage backends for file upload/download.

### Local Filesystem

```bash
pip install "fast-agent-stack[storage-local]"
```

```python
class Settings(BaseSettings):
    storage_backend: str = "local"
    storage_local_root: str = "./uploads"
```

### Amazon S3

```bash
pip install "fast-agent-stack[storage-s3]"
```

```python
class Settings(BaseSettings):
    storage_backend: str = "s3"
    storage_s3_bucket: str = "my-bucket"
    storage_s3_region: str = "us-east-1"
```

Uses instance role credentials by default. Set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` for explicit credentials.

### MinIO

```bash
pip install "fast-agent-stack[storage-minio]"
```

```python
class Settings(BaseSettings):
    storage_backend: str = "minio"
    storage_minio_endpoint: str = "http://localhost:9000"
    storage_minio_bucket: str = "my-bucket"
    storage_minio_access_key: str = "minioadmin"
    storage_minio_secret_key: str = "minioadmin"
```

## Using Storage in Routes

```python
from fast_agent_stack.core.storage import get_storage_backend

storage = get_storage_backend(settings)

# Upload
await storage.put("uploads/photo.jpg", file_bytes, content_type="image/jpeg")

# Download
data = await storage.get("uploads/photo.jpg")

# Delete
await storage.delete("uploads/photo.jpg")

# URL (for S3/MinIO: presigned; for local: path)
url = await storage.url("uploads/photo.jpg", expires_in=3600)
```

## Document Extraction

Extract plain text from common document formats before indexing or analysis.

```bash
pip install "fast-agent-stack[extract-pdf,extract-docx,extract-xlsx]"
```

| Extra | Formats | Library |
|-------|---------|---------|
| `extract-pdf` | PDF | pdfplumber |
| `extract-docx` | DOCX | python-docx |
| `extract-xlsx` | XLSX | openpyxl |

```python
from fast_agent_stack.core.extraction import get_extraction_backend

pdf_extractor = get_extraction_backend("pdf")
text = await pdf_extractor.extract(pdf_bytes)
```

## Custom Storage Backend

```python
storage_backend: str = "myproject.storage.MyS3CompatibleBackend"
```

Must implement `StorageProtocol` (put, get, delete, url).
