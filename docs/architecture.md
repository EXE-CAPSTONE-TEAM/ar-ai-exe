# Shoe Visual Customizer Architecture

## Product Flow

```text
Flutter Mobile Scanner
-> Python FastAPI Backend
-> Reconstruction Pipeline
-> GLB/OBJ Model Output
-> Vite + React Web Editor
-> Visual Design Package Export
```

## MVP Boundaries

Mobile is capture-only. It records a guided shoe scan video, collects metadata, and uploads both to the backend. Mobile does not run real-time 3D reconstruction.

The backend owns scan sessions, local storage, SQLite persistence, reconstruction jobs, model outputs, design drafts, and export packages.

The web app owns model viewing and visual decoration. GLB is the runtime format. OBJ, MTL, and PNG texture files are generated for export packages.

## Current Phase

Phase 0 creates the project structure and FastAPI foundation:

```text
backend/
mobile/
frontend/
docs/
```

## Backend Storage Layout

```text
backend/storage/raw-scans/
backend/storage/frames/
backend/storage/models/
backend/storage/designs/
backend/storage/exports/
```

## Security Direction

The MVP should include authentication and authorization foundations even while local demo mode allows a temporary skip-login path. The backend should still model users and roles in later phases so demo shortcuts can be removed without changing the core architecture.

## Reconstruction Direction

Development starts with mock reconstruction mode:

```text
video upload
-> frame extraction
-> sample or placeholder shoe_base.glb
-> generated OBJ/MTL/texture placeholders
-> completed scan session
```

The service boundary must remain compatible with future COLMAP/OpenMVS/Blender command execution.
