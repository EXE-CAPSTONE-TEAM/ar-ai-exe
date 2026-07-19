---
name: tech-stack-rules
description: SDLC, architecture, and coding conventions for the ar-ai-exe project. Use when proposing architecture changes, adding new features, or writing code to ensure alignment with project standards.
---

# Tech Stack Rules

Follow these guidelines for every meaningful change in the `ar-ai-exe` repository.

## SDLC Workflow

1. Clarify the requirement and acceptance criteria.
2. Inspect the current implementation (using `project-structure` skill).
3. Brainstorm the plan, alternatives, and trade-offs.
4. Implement a small vertical change in either `backend`, `frontend`, or `mobile` exclusively.
5. Add or update tests according to the stack.
6. Verify locally before handoff.

## Backend Rules (Python / FastAPI)

- Use FastAPI best practices with type hints (`Pydantic` models).
- Use `SQLAlchemy` for ORM and `alembic` for migrations. Do not bypass the ORM for standard CRUD.
- Ensure dependency injection (`Depends`) is used for database sessions and authentication.
- Keep routes thin; delegate business logic to service layers.

## Frontend Rules (React / Vite / TS)

- Use strictly typed TypeScript. Enable and respect strict mode.
- Use functional components and hooks.
- Keep components small and focused.
- Manage state locally where possible, and use established global state patterns only when necessary.

## Security Rules

- Never hardcode credentials, secrets, or API keys. Use `.env` variables.
- Ensure all API endpoints are properly authenticated/authorized.
- Validate all incoming data at the boundary (Pydantic for backend).
