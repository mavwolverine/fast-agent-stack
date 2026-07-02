# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — TBD

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
