---
name: production-sdlc
description: Apply production-grade SDLC, architecture, security, testing, and handoff rules for ar-ai-exe work in this repository. Use when planning, implementing, reviewing, or handing off changes that affect backend, frontend, mobile, or public web behavior.
---

# Production SDLC

Use this skill to keep the repository aligned with production-grade engineering while preserving boundaries.

## Workflow

1. Inspect the current code before proposing changes (use `project-structure` skill).
2. Clarify only blocking product or architectural requirements.
3. State the implementation flow and a concise trade-off table using `request-planning` skill, and **STOP** to wait for user approval before proceeding.
4. Implement a small vertical change with clear boundaries (backend, frontend, or mobile).
5. Add or update tests according to `test-strategy` skill.
6. Run feasible verification commands (e.g. pytest, build commands).
7. Perform a security and privacy review using `secure-review` skill before handoff.
8. Summarize decisions, changed files, verification, risks, and next actions using `session-handoff` skill.

## Quality Gates

- Follow SOLID, KISS, and DRY pragmatically.
- Do not add abstractions that only hide two simple examples.
- Keep production secrets out of source.
- Verify with build and relevant tests. If a command cannot run, record the exact blocker.
