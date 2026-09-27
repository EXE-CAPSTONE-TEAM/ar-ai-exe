# API Contract — Backend **ar-ai-exe** (`ar-ai-exe/backend`)

> **Đây là backend của dự án ar-ai-exe** (compute plane: relay quét KIRI cho mobile + sidecar xử lý 3D
> chạy trên máy desktop). **Không phải** backend KusShoes. Dữ liệu người dùng, project, design, job,
> quota đều nằm ở KusShoes BE — contract của nó ở `KusShoes/docs/api-contract.md`.

| | |
|---|---|
| Code | `backend/app` (FastAPI); chọn router theo `APP_ROLE` trong `app/main.py` |
| Đối chiếu | OpenAPI sinh từ code ngày 2026-09-27, cả hai role |
| Schema chi tiết | `/docs`, `/openapi.json` của process đang chạy; model Pydantic ở `app/schemas/` |

File này thay bản `api-contract.md` cũ (chỉ mô tả luồng standalone COLMAP, đã lỗi thời).
`docs/mobile-backend-contract.md` cũng đã lỗi thời — mobile không còn đăng nhập qua backend này.

---

## 0. Ba chế độ chạy

Cùng một codebase, nhưng mỗi chế độ là **một API khác nhau**:

| Chế độ | Chạy ở đâu | Bật bằng | Ai gọi | Mục |
|---|---|---|---|---|
| **Relay** | VM, container `kiri-relay` (`Dockerfile.relay`), `https://relay.136.85.55.175.sslip.io` | `APP_ROLE=relay` | Mobile app | §2 |
| **Sidecar** | máy Windows của user, do Tauri spawn ở `http://127.0.0.1:<port ngẫu nhiên>` | `APP_ROLE=full` + `CONTROL_PLANE_SERVICE_TOKEN` do Tauri cấp | KusStudio editor, Tauri shell | §3 |
| **Standalone** (legacy) | dev local `:8010` (docker-compose.dev) / demo offline | `APP_ROLE=full` (mặc định) | editor khi chạy không có KusShoes session | §4 |

Route được mount:

| Route | relay | full (sidecar + standalone) |
|---|:-:|:-:|
| `GET /health` | ✓ | ✓ |
| `/api/scan-sessions/*` | ✓ | ✓ |
| `POST /api/control-plane/scan/exchange` | ✓ | ✓ |
| `POST /bake`, `POST /prepare`, `GET /handshake`, `POST /downloads` | — | ✓ |
| `/api/auth/*`, `/api/projects/*`, `/api/models/*`, `/api/design-assets/*`, `/api/designs/*`, `/api/exports/*`, `/api/jobs/*`, `/api/system/*` | — | ✓ |

Ở role relay, `control_plane_service_token` bị ép rỗng nên `/bake`, `/prepare` không thể bật nhầm.

### 0.1 Quy ước

- **Lỗi:** `{"error": {"code": "...", "message": "...", "details": {}}}` (`app/core/errors.py`); code suy từ
  HTTP status: 401 `UNAUTHORIZED`, 403 `FORBIDDEN`, 404 `NOT_FOUND`, 409 `CONFLICT`, 422 `INVALID_REQUEST`,
  429 `QUOTA_EXCEEDED`, 503 `SERVICE_UNAVAILABLE`. *Khác KusShoes BE* (`{"code","message"}` ở top-level).
- **Kiểu chữ:** route `/api/*` dùng camelCase. Route sidecar `/bake` nhận/trả snake_case; `/prepare` nhận
  cả hai (`populate_by_name`), trả snake_case.
- **CORS:** `CORS_ORIGINS` + regex `http://(localhost|127.0.0.1|172.16.1.232):<port>`. Bản đóng gói Tauri
  cần `http://tauri.localhost`, `https://tauri.localhost`, `tauri://localhost` trong `CORS_ORIGINS`.

---

## 1. Tổng quan kết nối

```
Mobile ──user Bearer──► KusShoes BE  POST /api/v1/mobile/scans/bootstrap → {compute_api_url, compute_grant}
   │
   └──► Relay (ar-ai-exe, APP_ROLE=relay)
          POST /api/control-plane/scan/exchange ──X-Service-Token──► KusShoes /internal/mobile/compute-grants/claim
          …upload video (presigned R2) → KIRI → save-project
          ──X-Service-Token──► KusShoes /internal/mobile/scans/output-upload | output-confirm

Web KusShoes ── kusshoes-editor://launch?ticket=… ──► KusStudio (Tauri + ar-ai-exe/frontend)
   KusStudio ──editor Bearer──► KusShoes /api/v1/editor/*     (claim job → nhận payload)
   KusStudio ──X-Service-Token (launch token)──► Sidecar 127.0.0.1  /bake | /prepare | /downloads
   Sidecar ── presigned GET/PUT ──► object storage (không bao giờ gọi KusShoes)
```

---

## 2. Relay: Mobile → ar-ai-exe backend

Base URL = `compute_api_url` nhận từ KusShoes bootstrap (mobile mặc định
`COMPUTE_BASE_URL=https://relay.136.85.55.175.sslip.io`). Client: `mobile/lib/services/backend_api.dart`.

### 2.1 Đổi grant lấy scan token

`POST /api/control-plane/scan/exchange` — không auth

| | |
|---|---|
| Request | `{ "computeGrant": "<32–256 ký tự, từ KusShoes bootstrap>" }` |
| Response 200 | `{ accessToken, tokenType: "bearer", expiresIn, projectId, projectName, webProjectUrl }` |
| Phía sau | relay gọi `POST {CONTROL_PLANE_API_BASE_URL}/api/v1/internal/mobile/compute-grants/claim` với `X-Service-Token: CONTROL_PLANE_MOBILE_SERVICE_TOKEN` |

`accessToken` là **scan token**: chỉ dùng cho `/api/scan-sessions/*`, gắn đúng một project.
Mọi route dưới đây gửi `Authorization: Bearer <scan token>`.

### 2.2 Luồng quét (thứ tự bắt buộc)

| # | Route | Request → Response |
|---|---|---|
| 1 | `POST /api/scan-sessions` | `{ metadata?, projectId? }` → 201 `ScanSession{ id, userId, projectId, status, uploadedPasses[], requiredPasses[], webDesignUrl, … }` |
| 2 | `POST /api/scan-sessions/{id}/video-upload-url` | `{ contentType: "video/mp4", fileSizeBytes? }` → `{ uploadUrl, key, expiresIn }` (TTL 900 s) |
| 3 | `PUT <uploadUrl>` (thẳng tới R2) | body = file video, header `Content-Type: video/mp4`, **không** gửi `Authorization` |
| 4 | `POST /api/scan-sessions/{id}/video-uploaded` | `{ key? }` → `{ scanSession, passType, uploadedPasses, requiredPasses, readyForProcessing, processingStarted, webDesignUrl }`. Object thiếu hoặc > 250 MB (`MAX_UPLOAD_SIZE_MB`) → xoá object, 422 |
| 5 | `POST /api/scan-sessions/{id}/kiri/process` | — → `KiriStatus` |
| 6 | `GET /api/scan-sessions/{id}/kiri/status` (poll) | → `KiriStatus` |
| 7 | `GET /api/scan-sessions/{id}/kiri/preview` | → **307** tới presigned GET của GLB thô. Mobile tắt auto-redirect và đọc header `Location`. Web `<model-viewer>` dùng `?ticket=` (5 phút) thay cho Bearer |
| 8 | `POST /api/scan-sessions/{id}/save-project` | `{ projectName: 1–160 ký tự }` → `KiriStatus`; relay đẩy GLB về KusShoes (`output-upload` → PUT → `output-confirm`), model vào KusShoes với `status="raw"` |

`KiriStatus` = `{ scanSessionId, projectId?, status, providerStatus?, progress 0–100, previewUrl?, cropBox?, modelAssetId?, errorMessage?, updatedAt }`.

`status` (task KIRI, `app/models/entities.py`): `queued → uploading → processing → ready_for_crop → … → ready`,
hoặc `failed` / `expired`. Tên `ready_for_crop`, `crop_configured`, `crop_baking` là tên cũ còn giữ; crop
**không** còn làm trên mobile — `ready_for_crop` nghĩa là "KIRI đã có model, chờ lưu". Field `cropBox` luôn bỏ qua.

Route khác cùng nhóm: `GET /api/scan-sessions/{id}`, `GET /api/scan-sessions/{id}/status` (đọc trạng thái);
`POST /api/scan-sessions/{id}/process` (pipeline COLMAP cũ — relay không có toolchain, không dùng).

### 2.3 Relay gọi ra ngoài

| Đích | Route | Header |
|---|---|---|
| KusShoes | `/api/v1/internal/mobile/compute-grants/claim`, `/scans/output-upload`, `/scans/output-confirm` | `X-Service-Token: CONTROL_PLANE_MOBILE_SERVICE_TOKEN` |
| KusShoes | `/api/v1/internal/api-cost/calls` (báo chi phí KIRI) | cùng token trên — **KusShoes kiểm `SERVICE_TOKEN`**, xem §6 mục 1 |
| KIRI Engine | `KIRI_API_BASE_URL` | `KIRI_API_TOKEN` |
| Object storage | presigned PUT do KusShoes cấp | host phải nằm trong allowlist upload |

---

## 3. Sidecar: KusStudio desktop → ar-ai-exe backend (local)

Tauri (`desktop/src-tauri/src/main.rs`) mỗi lần mở app:
1. chọn một port trống (không bao giờ dùng lại process đang chiếm port),
2. sinh launch token 32 byte, truyền cho sidecar làm `CONTROL_PLANE_SERVICE_TOKEN`,
3. gọi `GET /handshake?nonce=…` và chỉ tin sidecar nếu `proof` đúng,
4. đưa `{ apiBaseUrl: "http://127.0.0.1:<port>", sidecarToken }` cho editor qua Tauri command. Token không ghi xuống đĩa.

Route `/bake`, `/prepare`, `/downloads` cần `X-Service-Token: <launch token>`.
Token sai → 401; sidecar chưa có token → 503. Chỉ chạy **1** job một lúc (`WORKER_MAX_CONCURRENT_BAKES=1`);
đang bận → 503 kèm `Retry-After: 10`.

### 3.1 `GET /handshake?nonce=<32–128 hex thường>`

→ `{ "proof": HMAC-SHA256(launch token, nonce) dạng hex }`. Nonce sai định dạng → 422.

### 3.2 `POST /bake`

Body = **nguyên `payload`** nhận từ KusShoes `POST /api/v1/editor/jobs/{id}/claim` (job `type=bake`):

| Field | Kiểu |
|---|---|
| `job_id`, `project_id` | uuid |
| `design_config` | object (snapshot design) |
| `formats` | `["glb" \| "obj"]` |
| `source_model` | `{ asset_id, download_url, file_size_bytes, mime_type: "model/gltf-binary" }` (≤ 500 MB) |
| `asset_downloads?` | `[{ asset_id, download_url, file_size_bytes, mime_type: image/png\|jpeg\|webp }]` (≤ 5 MB/file) |
| `outputs` | `[{ format, file_path, upload_url, content_type }]` (≤ 2 GiB/file) |
| `watermark?` | `{ required, text?, opacity_percent? }` — nhận nhưng **chưa áp dụng** (Ticket-04 đã bỏ) |

Mọi URL phải có origin nằm trong `WORKER_ALLOWED_STORAGE_ORIGINS` (lấy từ build config desktop, không lấy từ payload).
Field lạ → 422 (`extra="forbid"`).

Response 200: `{ "exports": [{ "format", "file_path", "file_size_bytes" }] }`.

### 3.3 `POST /prepare`

Body = `payload` của job `type=prepare`: `{ job_id|jobId, project_id|projectId, crop_box|cropBox, source_model|sourceModel, outputs }`.
`cropBox` = `{ center{x,y,z}, size{x,y,z}, rotation?{x,y,z}, coordinateSpace: "normalized" }`.
Sidecar tải GLB thô → crop → `MeshCleanupService` → kiểm magic `glTF` → PUT lên `outputs[0].upload_url`.

Response 200: `{ "outputs": [{ "format": "glb", "file_path", "file_size_bytes" }], "cleanup_report": {…} }`
(OpenAPI ghi `cleanupReport`, nhưng route trả `by_alias=False` nên thực tế là `cleanup_report`; editor đọc được cả hai).

Editor sau đó gọi KusShoes `POST /api/v1/editor/jobs/{id}/complete` với
`outputs[].{format, filePath, fileSizeBytes}` (đổi sang camelCase) và `X-Claim-Token`.
Sidecar lỗi → editor gọi `…/fail` với `code`: `SIDECAR_UNAVAILABLE`, `WORKER_BUSY` (503),
`SIDECAR_BAKE_FAILED` / `SIDECAR_PREPARE_FAILED`, `SIDECAR_INVALID_RESPONSE`, `SIDECAR_OUTPUT_MISSING`.

### 3.4 `POST /downloads`

`{ url: presigned GET (origin trong allowlist), filename }` → `{ path, file_size_bytes }`.
Stream file export thẳng vào thư mục Downloads, để file 2 GiB không phải đi qua webview.

### 3.5 `GET /health`

→ `{ status: "ok", service, environment }`. Tauri dùng để chờ sidecar khởi động; **không** dùng để xác thực (dùng `/handshake`).

---

## 4. Standalone (legacy): editor chạy không cần KusShoes

Chỉ dùng khi editor mở **không** có editor session của KusShoes (dev, demo offline, luồng import GLB cũ).
Editor chọn nhánh này qua `editorRoute(...)` trong `frontend/src/api/editorClient.ts`. Không phát triển
tính năng mới trên nhóm này; dữ liệu nằm trong DB riêng của ar-ai-exe, không đồng bộ với KusShoes.

| Nhóm | Route |
|---|---|
| Auth | `POST /api/auth/register`, `/login`, `/demo-login`, `/logout`; `GET /api/auth/me`, `/token` |
| Projects | `GET/POST /api/projects`, `GET /api/projects/{id}/editor-context`, `GET …/asset-manifest`, `GET …/asset-versions/{vid}/files/{type}`, `POST …/designs`, `GET …/exports` |
| Models | `POST /api/models/import`, `GET /api/models/{id}`, `GET /api/models/{id}/download/{glb\|obj\|mtl\|texture\|metadata\|obj-package}`, `GET …/quality-report` |
| Designs | `POST /api/design-assets`, `GET /api/design-assets/{id}/download`, `POST /api/designs`, `GET/PUT /api/designs/{id}`, `GET …/preview/glb`, `POST …/bake`, `POST …/export` |
| Khác | `GET /api/exports/{id}`, `GET …/download`, `GET /api/jobs/{id}`, `GET /api/system/reconstruction-readiness`, `GET /api/system/editor-readiness` |

---

## 5. Biến môi trường phải khớp với KusShoes

| `ar-ai-exe` | Phải khớp với |
|---|---|
| `CONTROL_PLANE_API_BASE_URL` (relay) | origin public của KusShoes BE |
| `CONTROL_PLANE_MOBILE_SERVICE_TOKEN` (relay) | `MOBILE_COMPUTE_SERVICE_TOKEN` của KusShoes |
| URL public của relay | `MOBILE_COMPUTE_URL` của KusShoes |
| `WORKER_ALLOWED_STORAGE_ORIGINS` (sidecar, từ build desktop) | origin mà KusShoes dùng ký presigned (`STORAGE_ENDPOINT` / R2) |
| `VITE_KUSSHOES_API_BASE_URL` (editor) | origin public của KusShoes BE |
| deep-link scheme trong `tauri.conf.json` | `EDITOR_DESKTOP_URL_SCHEME` của KusShoes |
| `CONTROL_PLANE_SERVICE_TOKEN` | **không** chia sẻ với KusShoes nữa: Tauri sinh mới mỗi lần mở app. `docs/integration-runbook.md` còn ghi phải trùng `EDITOR_WORKER_SERVICE_TOKEN` — biến đó đã bị xoá khỏi KusShoes |

---

## 6. Lệch contract đã phát hiện (2026-09-27)

1. **Báo chi phí KIRI dùng sai token.** `app/services/api_cost_reporter.py:96` gửi
   `CONTROL_PLANE_MOBILE_SERVICE_TOKEN` tới `/api/v1/internal/api-cost/calls`, trong khi KusShoes kiểm
   `SERVICE_TOKEN` (`KusShoes/BE/app/routers/api_cost.py:21`). Nếu hai token khác nhau (trong
   `KusShoes/BE/.env.production` chúng khác nhau) thì mọi báo cáo nhận 401 và chỉ bị log warning.
   Sửa ở một trong hai phía: relay dùng token riêng khớp `SERVICE_TOKEN`, hoặc KusShoes cho route này nhận mobile compute token.
2. **Mobile còn hàm gọi `/api/system/reconstruction-readiness` trên relay**
   (`getReconstructionReadiness`), route này không mount ở role relay → 404. Hiện không màn hình nào gọi; nên xoá.
3. **Link "Mở trên Desktop" của mobile** dùng `webProjectUrl` = `{PUBLIC_WEB_URL}/projects/{id}` do
   KusShoes trả về, nhưng web không có route này (chỉ có `/project-details?id=`). Chi tiết ở contract KusShoes §6.
4. `docs/mobile-backend-contract.md` và `docs/integration-runbook.md` mô tả luồng cũ (mobile đăng nhập ở
   backend này; KusShoes gọi `POST /bake` bằng `EDITOR_WORKER_SERVICE_TOKEN`). Cả hai đã không còn đúng.
