---
managed-by: wolverine-kit
description: "Full gate chain: gatekeeper → brief → test spec → implement. Usage: /fas-impl <module_name>"
---

Full implementation pipeline for a module.

## Target

$ARGUMENTS

## Steps (stop at first failure)

**Step 1 — gatekeeper**: Read `spec/INVARIANTS.md`, `spec/DECISIONS.md`, `spec/NFR.md`.
Verify the module is in ROADMAP.md and unblocked.
If BLOCK: stop. If NEEDS-DECISION: stop.

**Step 2 — spec-synthesizer**: Produce the implementation brief.
If STATUS = DRAFT: stop and report blockers.

**Step 3 — test-author**: Given the brief, produce a test spec across 5 families:
1. Behavior
2. Contract
3. Architectural
4. NFR
5. Failure-mode

**Step 4 — implement**:
1. Create files listed in INTERNAL STRUCTURE.
2. Write tests first (from test spec).
3. Implement until tests pass.
4. Run the test suite to confirm nothing broke.

## Constraints
- Never skip a step.
- If Step 1 or 2 fails, do NOT proceed to implementation.
