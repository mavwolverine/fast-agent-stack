---
managed-by: wolverine-kit
description: "Scan for spec↔code drift after changes to spec/. Usage: /fas-drift"
---

Run the drift-detector on fast-agent-stack.

## Steps

**Step 1 — drift-detector**: Check `git diff` on `spec/`, identify what changed, scan implementation for contradictions.

Output the SPEC CHANGE SUMMARY with BREAKS / NEEDS UPDATE / NO ACTION NEEDED.
