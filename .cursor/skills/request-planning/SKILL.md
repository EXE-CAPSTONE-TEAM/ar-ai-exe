---
name: request-planning
description: Clarify user intent and produce an implementation-ready plan before coding. Use when a request changes architecture, authentication, database schema, tests, public UI, security posture, or when the user proposes an implementation method that needs trade-off analysis.
---

# Request Planning

Use this skill before implementation when the request has meaningful ambiguity or engineering trade-offs.

## Steps

1. Inspect relevant files and current behavior first.
2. Identify what is known, unknown, and risky.
3. Ask concise blocking questions only when repository context cannot answer them.
4. Explain the proposed implementation flow.
5. Include a trade-off table covering scalability, maintainability, security, performance, and user experience.
6. Use Mermaid for flows that are easier to reason about visually.
7. End with concrete acceptance criteria and verification commands.
8. **Present the implementation plan to the user and STOP to wait for explicit approval.** Do NOT write any source code modifications or run destructive commands until approval is received.

## Defaults

- Prefer production-safe, maintainable choices over minimal demos.
- Keep `backend/` (FastAPI/Python), `frontend/` (React/Vite/TS), and `mobile/` isolated and modular.
- Choose framework-native patterns (FastAPI Depends, SQLAlchemy ORM, Pydantic validation) unless the codebase proves otherwise.
