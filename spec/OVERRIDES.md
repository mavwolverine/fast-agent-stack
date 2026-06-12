# fast-agent-stack — Overrides

Reviewed findings that agents must not re-raise. Each entry references the original
invariant or ADR it suppresses.

<!-- Example:
## OVR-001: <title>

**Suppresses:** "<finding description>"
**References:** <invariant/ADR/file>
**Resolution:** <why this is accepted>
-->

## OVR-001: Zensical is alpha software

**Suppresses:** "ADR-013 dependency (Zensical) is alpha/unstable"
**References:** ADR-013
**Resolution:** Accepted risk. Zensical is author-maintained and fit for purpose. If it becomes unmaintained or breaks, fall back to MkDocs Material (already proven in the backup). Revisit at Phase 7.