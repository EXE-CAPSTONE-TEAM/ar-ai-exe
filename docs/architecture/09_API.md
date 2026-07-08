# HTTP API

## Conventions

Base prefix is `/api`; `/health` is outside it. Pydantic responses use camelCase. Protected routes accept bearer JWT or auth cookie; cookie mutations require the CSRF cookie echoed in the configured header. Binary routes return bytes. Authoritative sources are `backend/app/api/*.py` and `backend/app/schemas/*.py`.

## System and auth

| Method/path | Auth | Request | Response |
|---|---:|---|---|
| `GET /health` | No | — | status, service, environment |
| `GET /api/system/reconstruction-readiness` | No | — | tools/resources/settings/blockers |
| `GET /api/system/editor-readiness` | No | — | preview-renderer capability |
| `POST /api/auth/register` | No | `{name,email,password}` | token/user + cookies |
| `POST /api/auth/login` | No | `{email,password}` | token/user + cookies |
| `POST /api/auth/demo-login` | No | — | demo token/user; 404 when disabled |
| `GET /api/auth/me` | Yes | — | current user |
| `POST /api/auth/logout` | No | — | message; clears cookies |

Registration password is 8–128 characters. User response includes ID, role, name, email and timestamps.

## Projects

| Method/path | Request | Response |
|---|---|---|
| `POST /api/projects` | `{name,sourceType?,templateId?}` | Project; `templateId` is not consumed by current service |
| `GET /api/projects` | — | owner project summaries |
| `GET /api/projects/{id}/editor-context` | — | project, latest model/design, permissions |
| `POST /api/projects/{id}/designs` | `{designConfig,name?}` | created Design using latest ready model |
| `GET /api/projects/{id}/exports` | — | project export packages |
| `GET /api/projects/{id}/asset-manifest` | — | stable project/model/design/preview/exports manifest |
| `GET /api/projects/{id}/asset-versions/{versionId}/files/{fileType}` | — | owner-authorized immutable file bytes |

The manifest always includes `project`, `model`, `design`, `preview`, and `exports`. Sprint 1
populates the latest `model/primary` version; unavailable design revision, preview, and export
values are returned as null or empty arrays. Latest resolution uses the highest published/ready
`versionNumber` within `(projectId, assetType, logicalKey)`.

## Scan sessions

| Method/path | Request | Response/behavior |
|---|---|---|
| `POST /api/scan-sessions` | optional `{metadata?,projectId?}` | creates session/project as needed |
| `POST /api/scan-sessions/{id}/upload-video` | multipart `metadata`,`video` | legacy upload treated as side orbit |
| `POST /api/scan-sessions/{id}/videos/{passType}` | multipart `video`, optional `metadata` | pass/upload readiness and editor URL |
| `GET /api/scan-sessions/{id}` | — | session plus uploaded/required passes/model ID |
| `GET /api/scan-sessions/{id}/status` | — | status/readiness/error/model/editor URL |
| `POST /api/scan-sessions/{id}/process` | — | requires both passes; starts background processing |

Metadata includes shoe (`sizeSystem`, size, side, type, material, condition), measurements (`lengthCm`, `widthCm`), scan setup and non-empty customization goals.

## Models

| Method/path | Request | Response |
|---|---|---|
| `GET /api/models/{id}` | — | canonical URLs, source/status, quality data |
| `POST /api/models/import` | multipart name, format, metadata, optional model/mtl/texture/package/projectId | scan session + model asset |
| `GET /api/models/{id}/download/{type}` | type=`glb|obj|mtl|texture|metadata|quality-report|obj-package` | attachment bytes |
| `GET /api/models/{id}/quality-report` | — | report JSON |

GLB and OBJ forms are validated and normalized through Blender.

## Design assets

| Method/path | Request | Response |
|---|---|---|
| `POST /api/design-assets` | multipart file + `sourceType` (`upload|canvas|text-render`) | asset metadata/download URL |
| `GET /api/design-assets/{id}/download` | — | owner-authorized PNG/JPEG |

Maximum is 5 MB with file-signature validation.

## Designs, jobs and exports

| Method/path | Request | Response |
|---|---|---|
| `POST /api/designs` | `{modelAssetId,name?,config?}` | legacy/direct Design |
| `GET /api/designs/{id}` | — | Design/config/preview state |
| `PUT /api/designs/{id}` | `{name?,config?}` | updated Design |
| `GET /api/designs/{id}/preview/glb` | — | baked GLB |
| `POST /api/designs/{id}/bake` | — | Job |
| `POST /api/designs/{id}/export` | route has no body | synchronously created ExportPackage |
| `GET /api/jobs/{id}` | — | type/status/progress/error/links/timestamps |
| `GET /api/exports/{id}` | — | export metadata and file list |
| `GET /api/exports/{id}/download` | — | ZIP attachment |

`DesignConfig` contains model ID, fixed base material, sticker/text arrays, camera and metadata. Detailed decal validation lives in backend modules rather than typed Pydantic layer schemas. The frontend polls jobs; no WebSocket/SSE interface exists. Export is synchronous despite export status values.

## Error and ownership behavior

`app/core/errors.py` wraps HTTP/validation errors into code/message/details payloads. Owner-scoped modules normally use 404 for missing or foreign resources. Upload/toolchain/queue errors may return 400/409/413/422/503 depending on source.
