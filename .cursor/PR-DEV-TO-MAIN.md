# Security Hardening — Dev → Main

## Summary

4 commits cherry-picked from `codex/source-security-fixes` + 3 new security hardening commits resolve **14 open SonarCloud security findings** (4 BLOCKER, 1 CRITICAL, 9 HIGH).

## Commits

```
6bd4615 fix: harden source path and url handling
5c2b999 fix(security): pin GitHub Actions by SHA and enable Android release obfuscation
4713d34 fix(security): sanitize validation error inputs before serializing
4d47dee docs(agents): link skill config to docs/agents
```

## What changed

### Backend — Path Safety (`backend/app/core/path_safety.py`)
New reusable path-safety primitives:
- `ensure_path_within(path, root)` — resolve + assert path stays inside root directory
- `safe_child_path(root, name)` — build a safe child path, reject traversal names
- `resolve_existing_file(path, allowed_suffixes)` — validate file exists, check suffix allowlist

### Backend — Seed Script (`backend/app/scripts/seed_desktop_demo_project.py`)
- CLI model path validated through `resolve_existing_file` with `{'.glb', '.gltf'}` allowlist + strict file check
- `validate_demo_model_path()` added; `sourceModel` in metadata now stores only filename (not full path)
- Resolves SonarCloud S2083 (path traversal) and S8707 (LLM path escape)

### Backend — Export Packages (`backend/app/services/export_packages.py`)
- All file/folder paths built through `safe_child_path` / `ensure_path_within`
- `_export_file(export_dir, name)` helper enforces name is a direct child
- `_export_folder(export_id)` uses `safe_child_path` on resolved storage root
- Legacy zip path read guarded by `ensure_path_within`
- Resolves SonarCloud S2083 (path traversal)

### Backend — Mesh Cleanup (`backend/app/services/mesh_cleanup.py`)
- MTL writer now confined to the service-managed output directory
- Combined with new path safety helpers, user-controlled paths cannot escape work directory
- Resolves SonarCloud S2083 (path traversal)

### Backend — Validation Error Handler (`backend/app/core/errors.py`)
- `_safe_input()` coercion: non-JSON-serializable values (e.g. UploadFile, custom objects) are converted to `repr()` string before being placed in the 422 JSON envelope
- Handler always returns a serializable response — no more 500 crashes leaking internal types
- Resolves potential information disclosure

### Backend — Test Fix (`backend/tests/test_mesh_cleanup.py`)
- Assertion rewritten from `runner.command[:3] == [...]` (potential IndexError) to explicit `runner.command[0]/[1]/[2]` equality checks guarded by `len(runner.command) >= 3`
- Resolves SonarCloud S6466 (CRITICAL IndexError)

### Frontend — API URL Validation (`frontend/src/api/runtimeConfig.ts`)
- `apiUrl()` now: rejects control characters, requires `http(s):`, rejects embedded credentials, enforces configured origin, rejects `/api` path traversal (`..`)
- `normalizeApiBaseUrl()` sanitizes base URL before storage
- Resolves SonarCloud S8476 (tainted URL construction) — 3 findings (#19, #21, #22)

### Frontend — Token Storage (`frontend/src/api/authStorage.ts`)
New file: validates access tokens against `^[A-Za-z0-9._~+/=-]+$`, length 16–4096, before writing to localStorage. All token read/write routed through this module.
- Resolves SonarCloud S8475 (tainted data to browser storage) — finding #20

### Frontend — App.tsx Security (`frontend/src/App.tsx`)
- `projectIdFromEditorPath` wrapped in try/catch for decodeURIComponent safety
- `editorProjectIdFromLocation` pipes path result through `sanitizeProjectId`
- `openDesktopProjectId` validates projectId before constructing URL; abandons redirect if invalid
- `loginRedirectUrl` passes only pathname+search+hash to the redirect param (no full URL with origin)
- Resolves SonarCloud S6105 (client-side redirection)

### GitHub Actions — Pin by SHA
| Workflow | Action | Before | After |
|---|---|---|---|
| `sonarcloud.yml` | `SonarSource/sonarqube-scan-action` | `@v8.2.0` | `@713881670b6b3676cda39549040e2d88c70d582e` |
| `mobile-ci.yml` | `subosito/flutter-action` | `@v2` | `@1a449444c387b1966244ae4d4f8c696479add0b2` |
| `backend-ci.yml` | `astral-sh/setup-uv` | `@v5` | `@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86` |

Resolves SonarCloud S7637 (HIGH) — 3 findings (#15, #16, #17)

### Mobile — Android Release Obfuscation (`mobile/android/app/build.gradle.kts`)
- `release` buildType now sets `isMinifyEnabled = true`, `isShrinkResources = true`
- `proguard-rules.pro` added with Flutter runtime/engine keep rules
Resolves SonarCloud S7204 (HIGH) — finding #23

## Test plan

- [x] `cd backend; python -m pytest` → 84 passed
- [x] `cd backend; python -m ruff check .` → all checks passed
- [x] `cd frontend; npm run build` → built in 7.12s
- [x] `cd mobile; flutter analyze && flutter test` → all passed
- [x] Husky pre-push hook → all CI checks passed

## Issues resolved (close after merge)

| # | Severity | Rule | Title |
|---|---|---|---|
| #10 | BLOCKER | S2083 | backend/app/scripts/seed_desktop_demo_project.py:210 |
| #11 | BLOCKER | S2083 | backend/app/services/export_packages.py:268 |
| #12 | BLOCKER | S2083 | backend/app/services/mesh_cleanup.py:171 |
| #13 | BLOCKER | S6105 | frontend/src/App.tsx:1638 |
| #14 | CRITICAL | S6466 | backend/tests/test_mesh_cleanup.py:64 |
| #15 | HIGH | S7637 | .github/workflows/backend-ci.yml:50 |
| #16 | HIGH | S7637 | .github/workflows/mobile-ci.yml:35 |
| #17 | HIGH | S7637 | .github/workflows/sonarcloud.yml:72 |
| #18 | HIGH | S8707 | backend/app/scripts/seed_desktop_demo_project.py:219 |
| #19 | HIGH | S8476 | frontend/src/api/client.ts:31 |
| #20 | HIGH | S8475 | frontend/src/api/client.ts:79 |
| #21 | HIGH | S8476 | frontend/src/api/client.ts:220 |
| #22 | HIGH | S8476 | frontend/src/api/client.ts:235 |
| #23 | HIGH | S7204 | mobile/android/app/build.gradle.kts:34 |
