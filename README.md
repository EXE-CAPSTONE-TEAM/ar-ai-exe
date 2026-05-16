# Shoe Visual Customizer

Prototype MVP for a shoe scanning and visual customization workflow.

The system is intentionally split into three apps:

- `backend/`: Python FastAPI API, local storage, SQLite persistence, reconstruction pipeline.
- `mobile/`: Flutter scanner app. Mobile captures guided shoe video and metadata only.
- `frontend/`: Vite + React web editor. Web loads GLB models and creates visual designs.
- `docs/`: Architecture, API contract, scan guidelines, and demo notes.

Phase 0 currently establishes the backend foundation and repository structure.
