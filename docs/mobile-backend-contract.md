# Mobile ↔ Backend Configuration Specification

**Document Version:** 1.0
**Created:** July 8, 2026
**Status:** Active
**Last Updated:** July 8, 2026

---

## 1. Overview

Tài liệu này định nghĩa contract giữa **Mobile App (Flutter)** và **Backend API (FastAPI)**. Mọi thay đổi phải được update ở đây trước khi implement.

### 1.1 Architecture Flow

```
┌─────────────┐         HTTPS/REST          ┌─────────────┐
│   Mobile    │ ───────────────────────────▶│   Backend   │
│  (Flutter)  │◀─────────────────────────── │  (FastAPI)  │
│             │    JSON Response/Errors      │             │
└─────────────┘                             └─────────────┘
       │                                          │
       │  Base URL from env var                   │ PostgreSQL
       │  BACKEND_BASE_URL                       │ Redis Queue
       └─────────────────────────────────────────│ S3 Storage
                                                 └─────────────┘
```

---

## 2. Environment Configuration

### 2.1 Mobile Configuration

**File:** `mobile/lib/services/backend_api.dart`

```dart
// PRODUCTION - Set khi build
// flutter build apk --dart-define=BACKEND_BASE_URL=https://api.kusshoes.vn
// flutter build ios --dart-define=BACKEND_BASE_URL=https://api.kusshoes.vn

// STAGING - Set khi development
// flutter run --dart-define=BACKEND_BASE_URL=https://staging-api.kusshoes.vn

// LOCAL DEV - Khi develop offline
// flutter run --dart-define=BACKEND_BASE_URL=http://localhost:8000
```

**Environment Variables:**

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `BACKEND_BASE_URL` | String | Yes | - | Base URL của backend API |

### 2.2 Backend CORS Configuration

**File:** `backend/app/main.py`

Backend phải whitelist các mobile origins sau:

```python
ALLOWED_ORIGINS = [
    # Production mobile apps
    "https://kusshoes.vn",
    "https://www.kusshoes.vn",

    # Staging
    "https://staging.kusshoes.vn",

    # Local development (chỉ dev)
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

---

## 3. API Endpoints Contract

### 3.1 Authentication Endpoints

#### POST `/api/auth/register`
**Purpose:** Đăng ký user mới

**Request:**
```json
{
  "name": "Nguyen Van A",
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (201):**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user_abc123",
    "name": "Nguyen Van A",
    "email": "user@example.com"
  }
}
```

**Error (400 - Email exists):**
```json
{
  "detail": "Email already registered"
}
```

---

#### POST `/api/auth/login`
**Purpose:** Đăng nhập

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user_abc123",
    "name": "Nguyen Van A",
    "email": "user@example.com"
  }
}
```

**Error (401 - Invalid credentials):**
```json
{
  "detail": "Invalid email or password"
}
```

---

#### POST `/api/auth/demo-login`
**Purpose:** Đăng nhập nhanh không cần tài khoản (cho demo/testing)

**Request:** Empty body

**Response (200):**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "demo_user_xyz789",
    "name": "Demo User",
    "email": "demo@kusshoes.vn"
  }
}
```

**Rate Limit:** 10 requests/minute/IP

---

### 3.2 Scan Session Endpoints

#### POST `/api/scan-sessions`
**Purpose:** Tạo một scan session mới

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

**Request Body (optional):**
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
    "customizationGoal": ["change_color", "add_sticker"]
  }
}
```

**Response (201):**
```json
{
  "id": "scan_abc123xyz",
  "userId": "user_abc123",
  "projectId": "proj_def456",
  "status": "created",
  "sourceType": "scan",
  "uploadedPasses": [],
  "requiredPasses": ["side_orbit", "top_orbit"],
  "webDesignUrl": "https://kusshoes.vn/design?scanId=scan_abc123xyz",
  "createdAt": "2026-07-08T10:30:00Z",
  "updatedAt": "2026-07-08T10:30:00Z"
}
```

**Business Logic:**
- Tự động tạo Project mới với tên "Untitled shoe scan"
- Project có `sourceType = "scan"`
- Trả về `webDesignUrl` để user mở web editor sau khi upload xong

---

#### POST `/api/scan-sessions/{scan_session_id}/videos/{pass_type}`
**Purpose:** Upload video cho một pass (side-orbit hoặc top-orbit)

**Headers:**
```
Authorization: Bearer {accessToken}
Content-Type: multipart/form-data
```

**Path Parameters:**
| Parameter | Type | Allowed Values |
|-----------|------|----------------|
| `scan_session_id` | String | Scan session ID từ step trước |
| `pass_type` | String | `side-orbit` hoặc `top-orbit` |

**Form Data:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video` | File (MP4) | Yes | Video file, max 100MB |
| `metadata` | String (JSON) | No | Video metadata (optional) |

**Response (200):**
```json
{
  "scanSession": {
    "id": "scan_abc123xyz",
    "status": "uploaded",
    "uploadedPasses": ["side_orbit", "top_orbit"],
    "requiredPasses": ["side_orbit", "top_orbit"],
    "webDesignUrl": "https://kusshoes.vn/design?scanId=scan_abc123xyz"
  },
  "passType": "top_orbit",
  "uploadedPasses": ["side_orbit", "top_orbit"],
  "requiredPasses": ["side_orbit", "top_orbit"],
  "readyForProcessing": true,
  "processingStarted": false,
  "webDesignUrl": "https://kusshoes.vn/design?scanId=scan_abc123xyz"
}
```

**Error (400 - Missing video):**
```json
{
  "detail": "No video file provided"
}
```

**Error (413 - File too large):**
```json
{
  "detail": "Uploaded video exceeds 100 MB"
}
```

---

#### POST `/api/scan-sessions/{scan_session_id}/process`
**Purpose:** Bắt đầu reconstruction process

**Headers:**
```
Authorization: Bearer {accessToken}
```

**Response (200):**
```json
{
  "id": "scan_abc123xyz",
  "projectId": "proj_def456",
  "status": "queued",
  "processingStarted": true,
  "readyForProcessing": true,
  "webDesignUrl": "https://kusshoes.vn/design?scanId=scan_abc123xyz",
  "updatedAt": "2026-07-08T10:35:00Z"
}
```

**Response (400 - Videos not uploaded):**
```json
{
  "detail": "Upload both required shoe videos before starting processing"
}
```

**Response (503 - Toolchain unavailable):**
```json
{
  "id": "scan_abc123xyz",
  "status": "toolchain_unavailable",
  "processingStarted": false,
  "errorMessage": "Reconstruction service is currently unavailable"
}
```

---

#### GET `/api/scan-sessions/{scan_session_id}/status`
**Purpose:** Kiểm tra status của scan session

**Headers:**
```
Authorization: Bearer {accessToken}
```

**Response (200):**
```json
{
  "id": "scan_abc123xyz",
  "projectId": "proj_def456",
  "status": "reconstructing",
  "errorMessage": null,
  "sourceType": "scan",
  "modelAssetId": null,
  "uploadedPasses": ["side_orbit", "top_orbit"],
  "requiredPasses": ["side_orbit", "top_orbit"],
  "readyForProcessing": true,
  "processingStarted": true,
  "webDesignUrl": "https://kusshoes.vn/design?scanId=scan_abc123xyz",
  "updatedAt": "2026-07-08T10:36:00Z"
}
```

**Status Values:**
| Status | Description | Next Action |
|--------|-------------|-------------|
| `created` | Session mới tạo | Upload video |
| `waiting_for_uploads` | Đang chờ upload đủ video | Upload video còn thiếu |
| `uploaded` | Upload đủ video | Gọi process |
| `queued` | Đang trong queue | Chờ xử lý |
| `extracting_frames` | Đang trích xuất frames | Chờ |
| `filtering_frames` | Đang lọc frames | Chờ |
| `preparing_reconstruction` | Đang chuẩn bị reconstruction | Chờ |
| `reconstructing` | Đang tái tạo 3D | Chờ |
| `cleaning_mesh` | Đang làm sạch mesh | Chờ |
| `uv_unwrapping` | Đang unwrap UV | Chờ |
| `texture_baking` | Đang bake texture | Chờ |
| `exporting` | Đang export | Chờ |
| `completed` | Hoàn thành | Mở web editor |
| `failed` | Thất bại | Xem errorMessage |
| `toolchain_unavailable` | Service không khả dụng | Thử lại sau |

---

#### GET `/api/scan-sessions/{scan_session_id}`
**Purpose:** Lấy full scan session details

**Headers:**
```
Authorization: Bearer {accessToken}
```

**Response (200):**
```json
{
  "id": "scan_abc123xyz",
  "userId": "user_abc123",
  "projectId": "proj_def456",
  "status": "completed",
  "sourceType": "scan",
  "modelAssetId": "model_ghi789",
  "webDesignUrl": "https://kusshoes.vn/editor/proj_def456",
  "uploadedPasses": ["side_orbit", "top_orbit"],
  "requiredPasses": ["side_orbit", "top_orbit"],
  "createdAt": "2026-07-08T10:30:00Z",
  "updatedAt": "2026-07-08T10:45:00Z"
}
```

---

### 3.3 System Endpoints

#### GET `/api/system/reconstruction-readiness`
**Purpose:** Kiểm tra backend reconstruction toolchain có sẵn sàng không

**Response (200):**
```json
{
  "ready": true,
  "message": "All reconstruction services are operational",
  "services": {
    "ffmpeg": true,
    "colmap": true,
    "openmvs": true,
    "blender": true
  }
}
```

**Response (200 - Not Ready):**
```json
{
  "ready": false,
  "message": "COLMAP service is not available",
  "services": {
    "ffmpeg": true,
    "colmap": false,
    "openmvs": true,
    "blender": true
  }
}
```

---

#### GET `/api/system/health`
**Purpose:** Health check endpoint

**Response (200):**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 4. Authentication & Authorization

### 4.1 Token Format

**JWT Structure:**
```json
{
  "sub": "user_abc123",
  "email": "user@example.com",
  "role": "user",
  "exp": 1752000000,
  "iat": 1751996400
}
```

**Token Lifetime:** 24 hours

### 4.2 Mobile Token Storage

**Requirements:**
- Access token được lưu trong `FlutterSecureStorage` (Keychain/Keystore)
- **KHÔNG** lưu trong localStorage hoặc shared preferences dạng plain text
- Token key: `shoe_customizer_access_token`

### 4.3 Required Headers

Tất cả endpoints trừ `/auth/*` và `/system/*` đều yêu cầu:

```
Authorization: Bearer {accessToken}
Content-Type: application/json
```

---

## 5. Error Handling

### 5.1 HTTP Status Codes

| Code | Meaning | Mobile Action |
|------|---------|---------------|
| 200 | Success | Process response |
| 201 | Created | Navigate to next step |
| 400 | Bad Request | Show error message |
| 401 | Unauthorized | Redirect to login |
| 403 | Forbidden | Show permission error |
| 404 | Not Found | Show "not found" message |
| 413 | Payload Too Large | Show "file too large" message |
| 422 | Validation Error | Show field-specific errors |
| 429 | Too Many Requests | Show rate limit message, retry later |
| 500 | Server Error | Show generic error, log to crash reporting |
| 503 | Service Unavailable | Show "service down" message |

### 5.2 Error Response Format

```json
{
  "detail": "Human readable error message"
}
```

Hoặc validation errors:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

### 5.3 Mobile Retry Strategy

| Error Type | Retry | Max Attempts | Backoff |
|------------|-------|--------------|---------|
| Network timeout | Yes | 3 | 1s → 2s → 4s |
| Connection timeout | Yes | 3 | 1s → 2s → 4s |
| 503 Service Unavailable | Yes | 3 | 1s → 2s → 4s |
| 429 Rate Limited | Yes | 3 | 1s → 2s → 4s |
| Connection error | Yes | 3 | 1s → 2s → 4s |
| 500 Server Error | No | - | Manual retry |
| 401 Unauthorized | No | - | Re-authenticate |
| 400 Bad Request | No | - | Fix request |

**Implementation:** Xem `mobile/lib/services/backend_api.dart`
```dart
class RetryConfig {
  static const int maxRetries = 3;
  static const Duration initialBackoff = Duration(seconds: 1);
  // Exponential backoff: 1s, 2s, 4s
}
```

---

## 6. File Upload Requirements

### 6.1 Video Specifications

| Field | Requirement |
|-------|-------------|
| Format | MP4 (video/mp4) |
| Max Size | 100 MB |
| Codec | H.264 preferred |
| Resolution | 720p minimum, 1080p recommended |
| Duration | 10-60 seconds |

### 6.2 Upload Progress

Mobile phải hiển thị progress bar và gọi `onProgress` callback:

```dart
await _api.uploadScanPass(
  scanSessionId: scanSessionId,
  passType: 'side-orbit',
  videoFile: videoFile,
  onProgress: (sent, total) {
    final progress = sent / total;
    // Update UI
  },
);
```

---

## 7. Database Schema Reference

### 7.1 Tables Created During Scan

```
users
├── id (PK)
├── email
├── name
└── created_at

projects
├── id (PK)
├── user_id (FK → users)
├── name
├── status (draft/processing/ready/failed)
├── source_type (scan/uploaded_glb/template)
└── created_at

scan_sessions
├── id (PK)
├── user_id (FK → users)
├── project_id (FK → projects)
├── status (created/uploaded/queued/processing/completed/failed)
├── side_video_path (S3 key)
├── top_video_path (S3 key)
├── web_design_url
└── created_at

model_assets (created after processing)
├── id (PK)
├── scan_session_id (FK → scan_sessions)
├── glb_path (S3 key)
├── status (uploaded/processing/ready/failed)
└── created_at
```

---

## 8. Deployment Checklist

### 8.1 Backend Deployment

- [ ] Set `WEB_APP_BASE_URL` environment variable
- [ ] Configure CORS whitelist (xem section 2.2)
- [ ] Setup PostgreSQL database
- [ ] Setup Redis for job queue
- [ ] Setup S3-compatible storage
- [ ] Verify all endpoints (xem Postman collection)
- [ ] Setup monitoring/alerting

### 8.2 Mobile Deployment

- [ ] Set `BACKEND_BASE_URL` khi build (xem section 2.1)
- [ ] Production URL: `https://api.kusshoes.vn`
- [ ] Staging URL: `https://staging-api.kusshoes.vn`
- [ ] Test demo-login flow
- [ ] Test full scan → upload → process flow
- [ ] Verify error handling for all scenarios

---

## 9. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-08 | Initial specification |

---

## 10. Contact

- **Mobile Team:** Mobile development lead
- **Backend Team:** API development lead
- **DevOps:** Infrastructure team

---

*Document maintained by: Backend Team*
*Last review: July 8, 2026*
