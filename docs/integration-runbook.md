# Integration runbook — ar-ai-exe ↔ KusShoes

Tài liệu gốc nằm ở repo KusShoes: **`KusShoes/docs/integration-runbook.md`**.
File này chỉ tóm tắt phần liên quan trực tiếp tới repo `ar-ai-exe`.

**Nhánh tích hợp chính:** `codex/kusshoes-production-e2e` (phải checkout ở cả hai repo).

## Repo này đóng vai trò gì

- `backend/` — **compute plane**: nhận `POST /bake` từ KusShoes, xác thực bằng
  `CONTROL_PLANE_SERVICE_TOKEN` (phải trùng `EDITOR_WORKER_SERVICE_TOKEN` bên KusShoes).
  Không giữ credential object store: KusShoes cấp presigned URL trong payload.
  Sau này thêm scan pipeline KIRI cho mobile.
- `frontend/` — **KusStudio editor**. Khi mở từ deep link `kusshoes-editor://launch?ticket=…`
  thì đổi PKCE lấy editor token và làm việc trực tiếp với `/api/v1/editor/*` của KusShoes
  (`src/api/editorLaunch.ts`, `src/api/editorClient.ts`).
- `desktop/` — Tauri shell đăng ký scheme `kusshoes-editor`.
- `mobile/` — **để phase sau**, chưa nối vào control plane.

## Cổng local dev

`docker-compose.dev.yml` map `8010:8000` (backend) và `5174:5173` (editor) để không đụng
KusShoes (BE `:8000`, web `:5173`).

## Biến môi trường phải khớp với KusShoes

| Biến (repo này) | Khớp với |
|---|---|
| `CONTROL_PLANE_SERVICE_TOKEN` | `EDITOR_WORKER_SERVICE_TOKEN` trong `KusShoes/BE/.env` |
| `VITE_KUSSHOES_API_BASE_URL` | origin của KusShoes BE (`http://127.0.0.1:8000` khi dev) |
| `CONTROL_PLANE_API_BASE_URL`, `CONTROL_PLANE_MOBILE_SERVICE_TOKEN` | chỉ dùng cho luồng mobile — **để trống ở phase này** |

## Import model 3D thủ công

Chưa có scan mobile, nên model gốc nạp bằng tay. Trong KusStudio, khi project chưa có model
canonical, editor hiện thẻ *"Import model 3D cho project"*
(`frontend/src/components/ModelImport/SourceModelImportCard.tsx`) → chọn `.glb` → upload
thẳng vào project KusShoes. Chỉ import được lần đầu; model canonical đã có thì không thay
được từ desktop.
