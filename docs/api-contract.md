# API Contract

Base URL for local development:

```text
http://127.0.0.1:8000
```

All scan, model, design, and export endpoints require:

```http
Authorization: Bearer local-demo-token-change-me
```

## Auth

### POST /api/auth/demo-login

Creates or reuses the local demo user and returns a bearer token.

```json
{
  "accessToken": "local-demo-token-change-me",
  "tokenType": "bearer",
  "user": {
    "id": "user_abc",
    "role": "demo_user",
    "name": "Demo User",
    "email": "demo@shoe-customizer.local"
  }
}
```

## System

### GET /api/system/reconstruction-readiness

Returns whether the backend can run real shoe reconstruction right now. This endpoint is used by web and mobile before users spend time uploading videos.

```json
{
  "ready": false,
  "message": "Reconstruction is not ready: Missing required tools: colmap, InterfaceCOLMAP, blender.",
  "tools": [
    {
      "name": "ffmpeg",
      "required": true,
      "available": true,
      "path": "/usr/bin/ffmpeg",
      "configuredValue": "ffmpeg",
      "hint": "Install ffmpeg or set FFMPEG_BIN."
    }
  ],
  "resources": [
    {
      "name": "available_memory",
      "ok": true,
      "available": 15.2,
      "required": 4.0,
      "unit": "GiB",
      "message": "available_memory OK: 15.2 GiB available."
    }
  ],
  "settings": {
    "enabled": true,
    "frameFps": 2.0,
    "maxFramesPerPass": 90,
    "maxThreads": 4,
    "minAvailableMemoryGb": 4.0,
    "minFreeStorageGb": 8.0
  },
  "missingTools": ["colmap", "InterfaceCOLMAP", "blender"],
  "blockingReasons": ["Missing required tools: colmap, InterfaceCOLMAP, blender."]
}
```

## Scan Sessions

### POST /api/scan-sessions

Creates a shoe-only scan session. Metadata may be supplied before video upload.

```json
{
  "metadata": {
    "shoe": {
      "sizeSystem": "EU",
      "size": "42",
      "side": "left",
      "type": "sneaker",
      "material": "canvas",
      "condition": "used"
    },
    "measurements": {
      "lengthCm": 27.0,
      "widthCm": 9.5
    },
    "scanSetup": {
      "calibrationReference": "A4 paper",
      "lighting": "bright",
      "background": "plain"
    },
    "customizationGoal": ["change_color", "add_sticker", "add_text"]
  }
}
```

Response:

```json
{
  "id": "scan_abc",
  "userId": "user_abc",
  "status": "created",
  "errorMessage": null,
  "modelAssetId": null,
  "webDesignUrl": "http://localhost:5173/design?scanId=scan_abc",
  "uploadedPasses": [],
  "requiredPasses": ["side_orbit", "top_orbit"],
  "createdAt": "2026-05-19T01:00:00",
  "updatedAt": "2026-05-19T01:00:00"
}
```

### POST /api/scan-sessions/{scan_session_id}/videos/{pass_type}

Uploads one required shoe video pass.

Valid `pass_type` values:

```text
side-orbit
top-orbit
```

Form fields:

```text
video: side-orbit.mp4 or top-orbit.mp4
metadata: optional JSON string
```

Response:

```json
{
  "scanSession": {
    "id": "scan_abc",
    "status": "waiting_for_uploads",
    "uploadedPasses": ["side_orbit"],
    "requiredPasses": ["side_orbit", "top_orbit"]
  },
  "passType": "side_orbit",
  "uploadedPasses": ["side_orbit"],
  "requiredPasses": ["side_orbit", "top_orbit"],
  "readyForProcessing": false,
  "processingStarted": false,
  "webDesignUrl": "http://localhost:5173/design?scanId=scan_abc"
}
```

### POST /api/scan-sessions/{scan_session_id}/process

Starts asynchronous backend reconstruction. Both `side_orbit` and `top_orbit` must already be uploaded. If the container toolchain is not ready, the scan remains stored and the status becomes `toolchain_unavailable` instead of losing the upload.

Response:

```json
{
  "id": "scan_abc",
  "status": "queued",
  "errorMessage": null,
  "modelAssetId": null,
  "updatedAt": "2026-05-19T01:01:00"
}
```

### GET /api/scan-sessions/{scan_session_id}/status

Returns the current processing state.

Possible states include:

```text
created
waiting_for_uploads
uploaded
queued
toolchain_unavailable
extracting_frames
filtering_frames
preparing_reconstruction
reconstructing
cleaning_mesh
exporting
completed
failed
```

## Model Assets

### GET /api/models/{model_asset_id}

Response after processing completes:

```json
{
  "id": "model_abc",
  "scanSessionId": "scan_abc",
  "glbUrl": "/api/models/model_abc/download/glb",
  "objUrl": "/api/models/model_abc/download/obj",
  "mtlUrl": "/api/models/model_abc/download/mtl",
  "textureUrl": "/api/models/model_abc/download/texture",
  "metadataUrl": "/api/models/model_abc/download/metadata",
  "qualityReportUrl": "/api/models/model_abc/quality-report",
  "objPackageZipUrl": "/api/models/model_abc/download/obj-package",
  "qualityReport": {
    "overallScore": 78,
    "status": "completed",
    "framesSelected": {
      "side_orbit": 55,
      "top_orbit": 48
    }
  },
  "createdAt": "2026-05-19T01:05:00"
}
```

### Download endpoints

```text
GET /api/models/{model_asset_id}/download/glb
GET /api/models/{model_asset_id}/download/obj
GET /api/models/{model_asset_id}/download/mtl
GET /api/models/{model_asset_id}/download/texture
GET /api/models/{model_asset_id}/download/metadata
GET /api/models/{model_asset_id}/download/obj-package
GET /api/models/{model_asset_id}/quality-report
```

Filenames:

```text
shoe_preview.glb
shoe.obj
shoe.mtl
shoe_texture.png
metadata.json
shoe_obj_package.zip
quality_report.json
```

## Legacy Compatibility

`POST /api/scan-sessions/{scan_session_id}/upload-video` still accepts the old single-video form and stores it as `side_orbit`, but the real reconstruction worker will not process until `top_orbit` is also uploaded.
# Project Asset Manifest (Sprint 1)

`GET /api/projects/{projectId}/asset-manifest` returns an owner-scoped, stable document with
`project`, `model`, `design`, `preview`, and `exports` sections. Missing values are null or empty.
The model section resolves the highest ready/published version number for
`(projectId, assetType=model, logicalKey=primary)`.

`GET /api/projects/{projectId}/asset-versions/{versionId}/files/{fileType}` returns immutable
version file bytes after project ownership validation. Existing model APIs remain supported.
