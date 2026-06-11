---
managed-by: wolverine-kit
description: "List all /fas- commands with descriptions. Usage: /fas-help"
---

List all available `/fas-` commands by reading the YAML frontmatter from each file in `.claude/commands/`.

## Steps

1. List all `.md` files in `.claude/commands/` that start with `fas-`.
2. For each file, extract the `description` field from the YAML frontmatter (between the `---` delimiters).
3. Print a table:

| Command | Description |
|---------|-------------|
| `/fas-<name>` | <description from frontmatter> |

Sort alphabetically by command name.
