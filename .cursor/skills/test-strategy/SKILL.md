---
name: test-strategy
description: Design and verify unit tests, integration tests, and UI/E2E tests for this repository. Use when adding features, changing behavior, touching database/API models, or preparing release/handoff verification.
---

# Test Strategy

Use this skill to keep coverage proportional to risk.

## Test Layers

- **Unit tests**: Verify small deterministic logic without database connections or external services (e.g., using pytest fixtures and mocks).
- **Integration tests**: Verify FastAPI routing, middleware, authentication flows, database persistence, and API responses.
- **UI/E2E tests**: Verify browser-visible frontend flows and mobile integration paths when critical workflows are introduced.

## Rules

- Keep backend and frontend tests completely isolated.
- Use isolated test databases (e.g. SQLite in-memory or a dedicated PostgreSQL test DB) for integration tests.
- Prefer deterministic mock data and unique emails/usernames.
- Do not rely on test execution order.

## Verification

Run backend tests using `pytest` inside the `backend` directory. Run frontend tests using `npm run test` or Vitest commands inside the `frontend` directory.
