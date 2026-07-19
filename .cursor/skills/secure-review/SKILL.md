---
name: secure-review
description: Review FastAPI backend and React/Vite/TS frontend changes for security, privacy, and secret-handling issues. Use before handoff or when touching database models, authentication, authorization, ORM queries, forms, logging, configuration, or user data.
---

# Secure Review

Use this skill as a gate before handoff for any security-relevant change.

## Checklist

- Confirm no production secrets, tokens, passwords, API keys, or privileged connection strings are stored in source.
- Confirm no PII (Personally Identifiable Information) is added to logs, test data, screenshots, or docs.
- Confirm authentication dependencies are invoked before authorization policies are executed.
- Confirm protected routes and FastAPI endpoints require authentication scopes or JWT token verification.
- Confirm front-end inputs are server-side validated using Pydantic models.
- Confirm database queries use SQLAlchemy ORM methods or parameterized queries, avoiding string-concatenated SQL.
- Confirm redirects or third-party webhooks validate domains explicitly.
- Confirm errors expose no traceback details or sensitive internals in production environments.

## Output

Report findings first, ordered by severity. Include file references, risk, and concrete remediation. If no issues are found, say so and list residual test gaps.
