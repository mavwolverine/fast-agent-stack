---
managed-by: wolverine-kit
description: "Propagate a manual spec edit across the doc set. Usage: /fas-propagate <doc>"
---

Propagate a change from a spec document across fast-agent-stack.

## Trigger document

$ARGUMENTS

## Steps

**Step 1 — change-propagator**: Read the trigger document, identify what changed, fan the change across all downstream spec files, agents, commands, and CLAUDE.md.

**Step 2 — verify**: Re-read modified files and confirm internal consistency. If contradictions exist, report them.

**Step 3 — gatekeeper**: Run a quick gate check on the propagated changes to confirm no invariant or ADR violations were introduced.
