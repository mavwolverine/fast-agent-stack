# TODO

Tech debt and deferred items.

## mypy: Replace follow_imports=skip with targeted type: ignore

Currently `pyproject.toml` uses `follow_imports = "skip"` on all third-party modules, which disables type checking for external API calls. This should be replaced with targeted fixes.

- [ ] Remove `follow_imports = "skip"` from mypy overrides (keep only `ignore_missing_imports = true`)
- [ ] Fix anthropic/openai SDK type mismatches with proper casts or `type: ignore[arg-type]` on specific call sites (~14 lines)
- [ ] Remove `warn_unused_ignores = false` once all ignores are stable
