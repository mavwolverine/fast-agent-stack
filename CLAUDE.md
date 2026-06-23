# fast-agent-stack — Claude Code Guide

## Specification

The `spec/` directory is the authoritative source of truth.

| File | Content |
|------|---------|
| `spec/VISION.md` | Vision, design principles, non-goals |
| `spec/INVARIANTS.md` | Non-negotiable rules — gatekeeper BLOCKs any violation |
| `spec/DECISIONS.md` | Binding ADRs — one per tech choice |
| `spec/ARCHITECTURE.md` | Modules, boundaries, pluggable seams |
| `spec/DX.md` | Public-facing surface — the contract with consumers |
| `spec/NFR.md` | Performance, security, compatibility floors |
| `spec/ROADMAP.md` | Phase checklist |
| `spec/SCENARIOS.md` | Use cases that validate the design |
| `spec/GLOSSARY.md` | Canonical terminology |
| `spec/OVERRIDES.md` | Suppressed findings — agents must not re-raise these |

## Agents

Agents live in `.claude/agents/`:

**Stewardship** (defend the spec):
- `fas-gatekeeper` — PASS/BLOCK/NEEDS-DECISION veto gate (opus)
- `fas-drift-detector` — catches spec↔code drift (auto)
- `fas-phase-tracker` — roadmap + spec completeness burn-down (auto)
- `fas-glossary-steward` — terminology consistency (auto)
- `fas-dependency-auditor` — audits deps for upgrades and compatibility (auto)

**Delivery** (turn spec into code):
- `fas-spec-synthesizer` — produces implementation briefs (auto)
- `fas-test-author` — generates test specs from briefs (sonnet)

**Authoring** (evolve the spec):
- `fas-architect-reviewer` — holistic spec quality review (auto)
- `fas-decision-author` — drafts ADRs + propagates (opus)
- `fas-change-propagator` — fans manual edits across docs (opus)

**Python Library Pack**:
- `fas-py-protocol-validator` — validates Protocol/ABC implementations (auto)


## Commands

| Command | When | Does |
|---------|------|------|
| /fas-check | Start of session / before changes | Gatekeeper gate + glossary audit |
| /fas-status | Start of session | Spec completeness + roadmap burn-down |
| /fas-review-spec | Before phase kickoff | Architect review of spec quality |
| /fas-impl-brief <module> | Before implementing | Gatekeeper gate + implementation brief |
| /fas-impl <module> | When ready to build | Full chain: gate → brief → tests → implement |
| /fas-drift | After spec/ changes | Scan for spec↔code drift |
| /fas-decision <topic> | When a tech choice is made | Draft ADR + propagate through docs |
| /fas-propagate <doc> | After manual spec edit | Fan change across all downstream docs |
| /fas-deps | When checking dependency health | Audit deps for available upgrades |
| /fas-help | Any time | List all /fas- commands with descriptions |

## Recommended Workflow

```
# Start of session
/fas-check
/fas-status

# Before starting a new phase
/fas-review-spec

# Making a decision
/fas-decision <topic>

# Implementing a module
/fas-impl-brief <module>   # read the brief; resolve DRAFT blockers first
/fas-impl <module>   # gate + test spec + handoff

# After manual spec edits
/fas-propagate <doc>
/fas-drift
```

## Project Structure

- Source: `fast_agent_stack/`
- Tests: `tests/`
- Stack: Python
