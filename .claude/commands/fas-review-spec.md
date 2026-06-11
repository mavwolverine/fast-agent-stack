---
managed-by: wolverine-kit
description: "Run the architect-reviewer on fast-agent-stack spec files. Usage: /fas-review-spec [spec-file]"
---

Run the architect-reviewer on the fast-agent-stack spec.

## Scope

$ARGUMENTS

If no argument is provided, review all spec files holistically.
If a specific file is provided (e.g., `ARCHITECTURE.md`), focus on that file but still check cross-file consistency.

## Steps

**Step 1 — architect-reviewer**: Read the relevant spec files. Evaluate across all five dimensions:
1. Invariant completeness
2. ADR coverage
3. Module boundary integrity
4. Roadmap sequencing
5. Scenario coverage

Produce the full SPEC REVIEW report.

## After the review

If **CRITICAL** findings:
- Do not proceed with /fas-impl for modules affected by the gap.
- Resolve the spec gap first, then re-run /fas-review-spec.

If **NEEDS-ATTENTION** or **OBSERVATION** only:
- Note the findings but implementation may proceed.
