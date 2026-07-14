# fast-agent-stack — Overrides

Reviewed findings that agents must not re-raise. Each entry references the original
invariant or ADR it suppresses.

<!-- Example:
## OVR-001: <title>

**Suppresses:** "<finding description>"
**References:** <invariant/ADR/file>
**Resolution:** <why this is accepted>
-->

## OVR-002: fas_ai migration has no depends_on fas_auth

**Suppresses:** "0001_fas_ai_conversation.py depends_on should be fas_auth_0001"
**References:** fas_ai Alembic branch, fas_auth Alembic branch
**Resolution:** The AI and auth migration branches are intentionally independent. A project may install the AI module without auth, or run them in any order. Alembic's `upgrade heads` handles both. No cross-branch dependency is required or desired.

## OVR-001: Zensical is alpha software

**Suppresses:** "ADR-013 dependency (Zensical) is alpha/unstable"
**References:** ADR-013
**Resolution:** Accepted risk. Zensical is author-maintained and fit for purpose. If it becomes unmaintained or breaks, fall back to MkDocs Material (already proven in the backup). Revisit at Phase 7.