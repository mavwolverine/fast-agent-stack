---
managed-by: wolverine-kit
description: "Full hygiene sweep — gatekeeper gate + glossary consistency. Usage: /fas-check [description of proposed change]"
---

Run a full hygiene sweep on fast-agent-stack.

## Scope

$ARGUMENTS

If no argument: do a read-only hygiene check of the current codebase against spec.
If a change description is provided: evaluate that specific proposal.

## Steps

**Step 1 — gatekeeper**: Read `spec/INVARIANTS.md`, `spec/DECISIONS.md`, `spec/NFR.md`.
Check the proposed change (or current state) against all invariants, ADRs, and NFRs.

Output: PASS | BLOCK: <reason> | NEEDS-DECISION: <question>

**Step 2 — glossary-steward**: Scan spec files for terminology variants and glossary gaps. Report any inconsistencies.
