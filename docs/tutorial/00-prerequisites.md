# Part 0 — Prerequisites

> **Series:** [Tutorial index](index.md) · **You are here:** Part 0 · [Part 1 →](01-hello-world.md)

Before building the **Document Q&A Assistant** you need three backing services running locally and the Ollama model server installed with the models the tutorial uses.

**What you need:**

- Docker and Docker Compose (Docker Desktop or Docker Engine + Compose plugin)
- Python 3.11 or newer
- [Ollama](https://ollama.com) — local model server

This takes about 10–15 minutes the first time (mostly waiting for model downloads).

---

## 1. Start the backing services

The tutorial uses **PostgreSQL** (database), **Valkey/Redis** (auth tokens + rate limiting), and **Qdrant** (vector store for the RAG pipeline).

Copy [docker-compose.yml](docker-compose.yml) into the directory you'll use for the tutorial (e.g. `~/docqa`):

```bash
cp /path/to/docs/tutorial/docker-compose.yml .
```

Or download it directly if you're working from the published docs:

```bash
curl -O https://raw.githubusercontent.com/your-org/fast-agent-stack/main/docs/tutorial/docker-compose.yml
```

Start all three services:

```bash
docker compose up -d
```

Verify they are healthy (all three should show `healthy` or `running`):

```bash
docker compose ps
```

You can also ping each service directly:

```bash
# PostgreSQL
docker compose exec postgres pg_isready -U docqa -d docqa

# Valkey/Redis
docker compose exec redis valkey-cli ping

# Qdrant
curl -s http://localhost:6333/healthz
```

---

## 2. Install Ollama

Download and install Ollama from [ollama.com](https://ollama.com) for your OS (macOS, Linux, or Windows). After installation, the `ollama` CLI is available in your terminal.

Confirm Ollama is running:

```bash
curl http://localhost:11434/api/tags
```

You should get a JSON response. If Ollama isn't running, start it:

```bash
ollama serve
```

---

## 3. Pull the tutorial models

The Document Q&A Assistant uses three Ollama models across different tutorial parts:

```bash
# Chat model — used from Part 1 onwards for the conversational agent
ollama pull llama3.2

# Embedding model — used in Part 4 to embed uploaded documents
ollama pull nomic-embed-text

# Reranking model — used in Part 5 to rerank retrieved document chunks
ollama pull qllama/bge-reranker-v2-m3
```

> **Disk space:** `llama3.2` is ~2 GB, `nomic-embed-text` is ~274 MB, and `qllama/bge-reranker-v2-m3` is ~570 MB. Make sure you have at least 4 GB free.

Verify the pulls succeeded:

```bash
ollama list
```

You should see all three models listed with their sizes.

---

## 4. Prepare your environment file

The tutorial app reads connection details from a `.env` file. You'll create this in Part 1 when you scaffold the project, but knowing the values now is useful.

The connection strings for the services above are:

```bash
DATABASE_URL=postgresql+asyncpg://docqa:docqa@localhost:5432/docqa
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
```

You do not need to create this file yet — `fas new` generates a `.env.example` you'll copy and fill in during Part 1.

---

## Checklist

Before continuing, confirm:

- [ ] `docker compose ps` shows **postgres**, **redis**, and **qdrant** as healthy
- [ ] `curl http://localhost:11434/api/tags` returns JSON
- [ ] `ollama list` shows `llama3.2`, `nomic-embed-text`, and `qllama/bge-reranker-v2-m3`

---

## Next steps

You're ready to build. Head to [Part 1 — Hello World](01-hello-world.md) to scaffold the `docqa` project.
