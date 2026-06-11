---
managed-by: wolverine-kit
description: "Record a new architectural decision interactively. Usage: /fas-decision <title>"
---

Record a new decision for fast-agent-stack.

## Title

$ARGUMENTS

## Steps

**Step 1 — Gather context**: Ask the user:

> What's the context and detail for this decision?
> (Include rationale, alternatives considered, and consequences. Send your response when done.)

Wait for the user's reply before proceeding.

**Step 2 — decision-author**: Using the title from the arguments and the detail from the user's reply, draft the ADR, number it sequentially, add to `spec/DECISIONS.md`.

**Step 3 — propagate**: Thread the decision through all affected spec files (INVARIANTS, ARCHITECTURE, NFR, DX.md, GLOSSARY, CLAUDE.md). Report what was updated and what was checked but unaffected.

**Step 4 — verify**: Re-read the modified files and confirm internal consistency. If the new decision contradicts an existing one, flag it.
