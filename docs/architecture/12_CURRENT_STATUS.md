# Current Status

## Integration status with the companion portal

The adjacent KusShoes repository presents portal, billing, project, and desktop-connection screens, but those screens currently use hard-coded/in-memory state, `setTimeout`, and generated log messages. Its port-8421 desktop daemon/WebSocket text is not backed by `WebSocket`, HTTP, or custom-protocol calls. The implemented desktop integration in this monorepo is instead Tauri -> shared React editor -> loopback FastAPI sidecar on a dynamically selected port in `8765..8795` (or an existing backend on `8000`). These are distinct implementations and should not be reported as one completed bridge.

Status is derived from repository code and configuration, not product copy.

## Completed MVP capabilities

| Area | Implemented |
|---|---|
| Identity | register/login/demo JWT, Argon2, bearer/cookie auth, CSRF for cookie mutations |
| Projects | owner-scoped create/list/editor context, designs and export listing |
| Mobile scan | metadata, side/top camera passes, upload progress and process trigger |
| Import | GLB/OBJ/package intake converging on canonical cleanup |
| Reconstruction | FFmpeg/COLMAP/OpenMVS/Blender orchestration and readiness checks |
| Model assets | canonical GLB/OBJ/MTL/texture/metadata/quality/package interface |
| Editor | model load, raycast snapping, sticker/text layers, canvas artwork |
| Preview | persisted design, RQ/inline bake, polling, cache-busted GLB |
| Export | final model files, notes, previews and ZIP |
| Desktop beta | shared editor, local sidecar/SQLite/storage, demo, Blender manager, diagnostics |
| Deployment | dev and production Compose, Caddy, CI and Sonar automation |
| Cloud asset foundation | project-owned immutable versions, legacy links, stable project manifest |

## In progress or constrained

| Capability | Constraint |
|---|---|
| Real reconstruction | code exists but depends on correctly provisioned heavy native tools/resources |
| S3 storage | adapter exists, but local-path processing prevents full pipeline use |
| Desktop distribution | checksum placeholder blocks Blender installer; Windows-first |
| Neon production | templates/migrations exist; runtime deployment state is external to repository |
| Project-centered editor | implemented alongside legacy scan/direct-design paths |
| Queue architecture | bake uses RQ; reconstruction and export do not |

## Missing

- Cloud synchronization between web and desktop.
- Immutable asset versions, design revisions and conflict handling.
- Resumable/direct cloud upload and large-file streaming.
- Durable reconstruction/export job orchestration and retries.
- Frontend integration/unit tests and meaningful mobile flow tests.
- Desktop automated tests, signed/reproducible release workflow and auto-update.
- Refresh tokens, revocation, password reset/verification, SSO, ACL/project sharing.
- Observability, quotas, retention, deletion/privacy workflows and disaster recovery.
- CI-driven deployment and end-to-end staging smoke tests.

## Technical debt and correctness risks

| Priority | Finding | Evidence |
|---|---|---|
| High | unsafe local auth/debug defaults need production startup guard | `core/config.py` |
| High | reconstruction is process-local background work | `api/scan_sessions.py` |
| High | S3 cannot supply local tool input paths | `storage.py`, `reconstruction.py` |
| High | frontend orchestration concentrated in 1,716-line `App.tsx` | `frontend/src/App.tsx` |
| Medium | duplicated HTTP clients/auth/error plumbing | `client.ts`, `editorClient.ts` |
| Medium | export blocks request; no export job | `api/designs.py`, `export_packages.py` |
| Medium | `latest_design` OR predicate may violate intended aggregate selection | `services/projects.py` |
| Medium | complete uploads buffered in mobile/backend memory | mobile/backend upload code |
| Medium | no optimistic concurrency or asset versions | ORM entities |
| Medium | desktop local/cloud identity split has no explicit mode model | Tauri/sidecar/frontend |
| Low | architecture report contains stale Tailwind claim/encoding/path drift | `docs/project-architecture-review.md` |

## Test and verification status

- Backend contains 37 tests focused on decal validation/scripts, cleanup, import security, design assets, editor context/job integration and readiness.
- Frontend has build/typecheck only and no test suite.
- Mobile has a shallow widget test plus analyze/test CI.
- Desktop has no Rust/UI integration tests.
- Blender tests mostly inspect/generated scripts or use fakes; real toolchain end-to-end coverage is environment-dependent.

During this documentation pass, runtime verification could not run locally because `backend/.venv` and frontend installed dependencies were absent. This is an environment limitation, not evidence of failing tests.
