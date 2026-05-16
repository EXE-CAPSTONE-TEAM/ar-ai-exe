# API Contract

Base URL for local development:

```text
http://127.0.0.1:8000
```

## Phase 0

### GET /health

Checks that the API process is running.

Request:

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "service": "Shoe Visual Customizer API",
  "environment": "local"
}
```

## Planned Phase 1 Scan Endpoints

```text
POST /api/scan-sessions
POST /api/scan-sessions/{scan_session_id}/upload-video
GET  /api/scan-sessions/{scan_session_id}
GET  /api/scan-sessions/{scan_session_id}/status
```

After video upload, processing should start automatically and status must remain visible through the status endpoint.

## Planned Authentication Direction

The API should support real authentication and authorization. For local demo UX, the frontend may expose a skip-login button that signs into a fixed demo user, but backend authorization should still treat that user as an explicit identity.
