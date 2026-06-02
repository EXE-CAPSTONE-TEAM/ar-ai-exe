# ar-ai-exe Agent Instructions

This repository contains the `ar-ai-exe` codebase. All AI agents working on this repository must read this file to ensure proper alignment.

## Global Context
Before performing any task, read [CONTEXT.md](file:///F:/_FPT/_EXE101/ar-ai-exe/CONTEXT.md) to understand project boundaries and core architecture.

## Operating Rules
- Respect the boundaries of backend (FastAPI/Python), frontend (React/Vite/TS), and mobile.
- Do not assume file paths; use the structural skills to discover directories.

## Known Agent Pitfalls
- In the backend Blender decal bake flow, never clear or replace base shoe mesh material slots just to enforce `baseColor` or roughness. Imported GLB/OBJ shoes can rely on existing material slots, texture maps, and polygon material indices; clearing them makes saved draft previews lose the original shoe appearance. Preserve existing materials/textures, adjust only safe PBR factors such as roughness/metallic/base color when the base color input is not texture-linked, and create a new white material only for meshes that have no material.

## Agent Skills
See `.agents/skills/` for active skill workflows.

### Project Structure
Deterministically inspect code layout before modifications. See [.agents/skills/project-structure/SKILL.md](file:///F:/_FPT/_EXE101/ar-ai-exe/.agents/skills/project-structure/SKILL.md).

### Tech Stack Rules
SDLC, coding standards, and security rules. See [.agents/skills/tech-stack-rules/SKILL.md](file:///F:/_FPT/_EXE101/ar-ai-exe/.agents/skills/tech-stack-rules/SKILL.md).

### Request Planning
Clarify user intent and produce implementation-ready plans before coding. See [.agents/skills/request-planning/SKILL.md](file:///F:/_FPT/_EXE101/ar-ai-exe/.agents/skills/request-planning/SKILL.md).

### Secure Review
Review FastAPI and React changes for security, privacy, and secret leaks. See [.agents/skills/secure-review/SKILL.md](file:///F:/_FPT/_EXE101/ar-ai-exe/.agents/skills/secure-review/SKILL.md).

### Session Handoff
Prepare context for new sessions and team handoffs. See [.agents/skills/session-handoff/SKILL.md](file:///F:/_FPT/_EXE101/ar-ai-exe/.agents/skills/session-handoff/SKILL.md).

### Test Strategy
Design and execute Pytest and Vitest testing layers. See [.agents/skills/test-strategy/SKILL.md](file:///F:/_FPT/_EXE101/ar-ai-exe/.agents/skills/test-strategy/SKILL.md).

### Production SDLC
Enforce the end-to-end production workflow. See [.agents/skills/production-sdlc/SKILL.md](file:///F:/_FPT/_EXE101/ar-ai-exe/.agents/skills/production-sdlc/SKILL.md).

### Issue Tracker
GitHub Issues workflow. See [docs/agents/issue-tracker.md](file:///F:/_FPT/_EXE101/ar-ai-exe/docs/agents/issue-tracker.md).

### Triage Labels
Default triage roles. See [docs/agents/triage-labels.md](file:///F:/_FPT/_EXE101/ar-ai-exe/docs/agents/triage-labels.md).

### Domain Docs
Multi-context layout. See [docs/agents/domain.md](file:///F:/_FPT/_EXE101/ar-ai-exe/docs/agents/domain.md).
