# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0a1] — 2026-07-19

### Added

- **Phase 8** — Redis SDK migration (`fastapi-redis-sdk`), response caching
- **Phase 9** — Documentation site, README, all reference guides
- **Phase 10** — Progressive tutorial (Parts 0-8), `@tool` decorator, `agent_loop`, tool calling on all LLM backends, reranker backends, public facades (`fast_agent_stack.ai`, `fast_agent_stack.rag`)
- **Phase 11** — Framework integration guides (Strands Agents, Pydantic AI), `ai/` scaffolder package layout
- `get_llm(settings)` factory for one-line LLM backend resolution
- `llm_provider` setting field
- `fast_agent_stack.storage` public facade
- Tutorial Part 5 branch-point (choose built-in, Strands, or Pydantic AI)
- `createsuperuser --force` flag for updating existing users
- Frontend: conversation_id support, auto-refresh for indexing status, upload modal UX fix

### Fixed

- S18 scenario description now matches actual `agent_loop` implementation (async generator, `backend.stream()`)
- DX.md minimal app example uses real `get_llm()` import
- ARCHITECTURE.md package tree: `core/database/` subpackage, `core/email/`, `core/redis/`
- I22 "Applies to" includes `core/ai/reranker/`
- Tutorial import paths updated for `ai/` package layout

## [0.1.0] — 2026-07-06

### Added

- **Phase 1** — Package skeleton, `FastAgentStack` wrapper, `BaseSettings`, CLI (`dev`, `run`, `version`), minimal scaffolder preset
- **Phase 2** — SQLAlchemy async engine, Alembic integration, CLI (`migrate`, `makemigrations`, `seed`), `/health/live` + `/health/ready`
- **Phase 3a** — User, Group, Permission models; `auth_verification_token` + `api_keys` tables; `createsuperuser` CLI
- **Phase 3b** — JWT + session auth backends, `/auth/token`, `/auth/refresh`, `/auth/logout`, permission dependencies
- **Phase 3c** — Redis client, JTI denylist, API key management, SQLAdmin integration
- **Phase 4a** — `Message`, `CompletionResult`, `LLMBackend` Protocol, `stream_sse` helper, `UsageService` stub
- **Phase 4b** — Bedrock, OpenAI, Anthropic, LiteLLM backends (extras-gated)
- **Phase 4c** — `@app.agent()` decorator, conversation persistence, token usage logging, `agent` preset
- **Phase 5** — StorageProtocol (S3/MinIO/local), VectorStoreProtocol (Qdrant/pgvector/OpenSearch/Weaviate), EmbeddingProtocol (Bedrock/OpenAI/local), ExtractionProtocol (PDF/DOCX/XLSX/EML), RAG pipeline service
- **Phase 6** — Dramatiq background tasks + Periodiq scheduler, Redis fixed-window rate limiting, OpenTelemetry tracing, EmailProtocol + SmtpEmailBackend, auth email routes (verification, password reset), secrets manager backends (AWS/GCP), `UsageService.get_usage()` + `get_usage_by_model()`
- **Phase 7** — Full scaffolder (all presets, Docker + K8s templates), CI/CD (GitHub Actions lint/test/publish), documentation site (Zensical)
