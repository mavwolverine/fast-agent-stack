# fast-agent-stack — Overrides

Reviewed findings that agents must not re-raise. Each entry references the original
invariant or ADR it suppresses.

<!-- Example:
## OVR-001: <title>

**Suppresses:** "<finding description>"
**References:** <invariant/ADR/file>
**Resolution:** <why this is accepted>
-->

## OVR-003: I9 INVARIANTS.md is correct post-Phase-8

**Suppresses:** "INVARIANTS.md I9 is stale — describes FastAPIRedisLifespanHook which no longer exists after ADR-037"
**References:** I9, ADR-037, Phase 8
**Resolution:** I9 is correct as-is. FastAPIRedisLifespanHook exists and is the current implementation. The architect-reviewer's claim that it was replaced by a different class was a false positive. Do not re-raise this finding.

## OVR-002: fas_ai migration has no depends_on fas_auth

**Suppresses:** "0001_fas_ai_conversation.py depends_on should be fas_auth_0001"
**References:** fas_ai Alembic branch, fas_auth Alembic branch
**Resolution:** The AI and auth migration branches are intentionally independent. A project may install the AI module without auth, or run them in any order. Alembic's `upgrade heads` handles both. No cross-branch dependency is required or desired.

## OVR-001: Zensical is alpha software

**Suppresses:** "ADR-013 dependency (Zensical) is alpha/unstable"
**References:** ADR-013
**Resolution:** Accepted risk. Zensical is author-maintained and fit for purpose. If it becomes unmaintained or breaks, fall back to MkDocs Material (already proven in the backup). Revisit at Phase 7.