---
name: project-structure
description: Safely extract and map the source code structure of the project without guessing. Use this whenever an agent is asked to analyze the project architecture, find existing components, or before writing code in an unfamiliar boundary.
---

# Project Structure Extraction

When tasked with understanding the project architecture or locating existing code, do not assume or hallucinate paths. Follow these explicit steps:

## Steps

1. **Read `CONTEXT.md`**: First, read `CONTEXT.md` at the project root to understand the high-level directories (e.g., `backend`, `frontend`, `mobile`).
2. **List Directories Deterministically**: Use your `list_dir` tool (or equivalent workspace reading tool) on the specific subdirectories to see the actual structure.
   - Example: list `backend/app` or `frontend/src` before attempting to edit files.
3. **Avoid Blind Grep**: Do not run recursive global searches (`grep -r` or similar) without first narrowing down the target directory using `list_dir`.
4. **Identify Dependencies**: Check `pyproject.toml` or `requirements.txt` in the `backend/`, and `package.json` in the `frontend/` to understand the tech stack before writing code.
5. **Summarize**: Present the discovered structure to the user or use it internally to formulate your implementation plan.

## Defaults

- Always respect the boundaries defined in `CONTEXT.md`.
- Treat `backend` (FastAPI/Python), `frontend` (React/Vite/TS), and `mobile` as isolated spaces with their own dependencies.
