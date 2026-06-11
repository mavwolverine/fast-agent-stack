---
managed-by: wolverine-kit
description: "Gatekeeper gate + implementation brief for a module. Usage: /fas-impl-brief <module_name>"
---

Run gatekeeper + spec-synthesizer for a module.

## Target

$ARGUMENTS

## Steps

**Step 1 — gatekeeper**: Verify the module is in `spec/ROADMAP.md` and its phase is unblocked. Check against invariants and ADRs.
If BLOCK or NEEDS-DECISION: stop and report.

**Step 2 — spec-synthesizer**: Produce the implementation brief.
If STATUS = DRAFT: stop and report blockers.
