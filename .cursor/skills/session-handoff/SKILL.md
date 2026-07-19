---
name: session-handoff
description: Prepare compact context for a new AI session, push readiness, or team handoff. Use after non-trivial code changes, before pushing code, or when the next agent needs to understand project state quickly.
---

# Session Handoff

Use this skill to make the next session productive without re-discovering work.

## Handoff Format

Include:

- Goal and current status.
- Files and subsystems changed.
- Key decisions and trade-offs.
- Database, migration, and configuration changes (e.g., Alembic migrations).
- Tests added or changed.
- Commands run and results.
- Security/privacy review result.
- Known risks, skipped checks, and next actions.

## Rules

- Be concise but specific enough for a new agent to resume.
- Do not include secrets, tokens, PII, or raw production connection strings.
- Mention exact blockers for commands that could not run.
