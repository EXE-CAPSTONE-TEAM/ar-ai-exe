# Runbook Windows — KusStudio Desktop + mobile (T05, T12, T14)

Nhánh: **`main`** của `ar-ai-exe` (client-side 3D đã merge qua PR #32). Trên máy Windows chỉ cần
clone `ar-ai-exe`; KusShoes chạy sẵn trên server, không cần clone. Server đã chạy sẵn:

| Thành phần | URL |
|---|---|
| KusShoes API | `https://136.85.55.175.sslip.io` |
| KIRI relay (mobile scan) | `https://relay.136.85.55.175.sslip.io` |
| Web | `https://kusshoes.vercel.app` |
| R2 endpoint (sidecar tải/upload) | `https://1d92645e04fc345cde21bc7c7260e073.r2.cloudflarestorage.com` |

Server **không** xử lý 3D. Cắt mesh + bake chạy trên máy Windows trong sidecar local + Blender.

Thứ tự: **Bước 0 → 1 → 2 (T05) → 3 (bản cài) → 4 (T12) → 5 (T14) → 6 (ghi kết quả)**.

## Ba ticket này kiểm chứng gì

| Ticket | Mục tiêu | Xong khi |
|---|---|---|
| **T05** — Sidecar trust | App desktop chỉ tin sidecar do chính nó vừa sinh ra: cổng ngẫu nhiên, token 32 byte mỗi lần mở, handshake HMAC, CORS cho `tauri.localhost`, `/downloads` chỉ ghi vào thư mục Downloads | Mọi ô ở Bước 2 được tick |
| **T12** — Mobile scan không crop | Mobile quay → upload video qua URL ký sẵn → xem preview model raw → "Lưu project" / "Mở trên Desktop" | Mọi ô ở Bước 4 và dòng 2–3 của Bước 5 được tick |
| **T14** — End-to-end trên Windows | Chuỗi thật scan → prepare (crop) → bake → export chạy trên máy Windows với server thật | Mọi dòng ở Bước 5 được tick |

Mỗi ô `[ ]` là một điều kiện đạt/không đạt. Ô nào không đạt: dừng, làm theo mục "Khi lỗi" ở cuối
file, ghi số ô đó vào kết quả.

---

## Bước 0 — Cài công cụ (một lần)

PowerShell (Admin):

```powershell
winget install --id Git.Git -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Rustlang.Rustup -e
winget install --id astral-sh.uv -e
winget install --id Microsoft.EdgeWebView2Runtime -e
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

Mở PowerShell **mới** rồi kiểm tra: `git --version; node -v; cargo -V; uv -V`.

Blender 4.5.1: tự tải `blender-4.5.1-windows-x64.zip` từ trang release chính thức của Blender
(Blender4.5) về máy, ví dụ `C:\artifacts\blender-4.5.1-windows-x64.zip`. Không cần giải nén.
`download.blender.org` có thể trả 403 cho `curl`/script; khi đó tải từ mirror chính thức (vd.
`https://mirrors.ocf.berkeley.edu/blender/release/Blender4.5/`). SHA-256 đúng:
`ae2eadb2656d710ffd6ca74a899519fccb800c7a18e6c05b6f39627e48d17aed` (399 708 581 byte).

## Bước 1 — Lấy code

```powershell
cd C:\src
git clone https://github.com/EXE-CAPSTONE-TEAM/ar-ai-exe.git
cd ar-ai-exe
git checkout main
git pull
git log --oneline -1   # ghi lại commit này vào kết quả (Bước 6)
```

Đã clone rồi thì chỉ cần `git fetch; git checkout main; git pull`.

Biến môi trường dùng cho mọi bước sau (chạy trong cùng cửa sổ PowerShell):

```powershell
$env:KUSSHOES_BLENDER_ARTIFACT_PATH = "C:\artifacts\blender-4.5.1-windows-x64.zip"
$env:KUSSHOES_BLENDER_SHA256 = (Get-FileHash $env:KUSSHOES_BLENDER_ARTIFACT_PATH -Algorithm SHA256).Hash.ToLower()
$env:KUSSHOES_STORAGE_ORIGINS = "https://1d92645e04fc345cde21bc7c7260e073.r2.cloudflarestorage.com"
```

`KUSSHOES_STORAGE_ORIGINS` được nhúng vào bản build lúc compile; thiếu nó thì sidecar từ chối tải model từ R2.

Tạo `frontend\.env.desktop` (Vite đọc file này khi chạy `--mode desktop`):

```powershell
@"
VITE_KUSSHOES_API_BASE_URL=https://136.85.55.175.sslip.io
VITE_API_BASE_URL=http://127.0.0.1:8010
VITE_MARKETING_LOGIN_URL=https://kusshoes.vercel.app/login
VITE_DESKTOP_SHELL=true
VITE_DESKTOP_DEMO_PROJECT_ID=proj_desktop_demo
"@ | Set-Content -Encoding utf8 frontend\.env.desktop
```

`VITE_API_BASE_URL` chỉ là giá trị dự phòng; khi chạy trong Tauri, cổng sidecar do hệ điều hành cấp và app tự lấy.

Cài dependency:

```powershell
cd backend; uv sync; uv pip install pyinstaller; cd ..
cd frontend; npm install; cd ..
cd desktop; npm install; npm run prepare:blender; cd ..
```

## Bước 2 — T05: build + chạy thử bản dev

```powershell
cd desktop\sidecar-auth; cargo test; cd ..\..
cd desktop\src-tauri; cargo build; cd ..\..
cd desktop; npm run dev
```

**Checklist T05 — tick từng ô:**

- [ ] **05.1** `cargo test` trong `desktop\sidecar-auth` → `6 passed; 0 failed`. Sáu test đó là:
  `a_health_responder_that_was_not_spawned_here_is_never_adopted`,
  `generated_secrets_have_the_documented_entropy_and_differ`, `handshake_response_parsing`,
  `proof_matches_rfc4231_hmac_sha256`, `storage_origins_render_as_a_json_list_of_https_origins`,
  `verify_accepts_only_the_proof_for_this_token_and_nonce`.
- [ ] **05.2** Test phía sidecar chạy trên Windows:
  `cd backend; uv run pytest tests/test_sidecar_trust.py -q; cd ..` → toàn bộ passed.
- [ ] **05.3** `cargo build` trong `desktop\src-tauri` không lỗi.
- [ ] **05.4** `npm run dev` → app mở, màn Diagnostics hiện **Ready at http://127.0.0.1:&lt;cổng&gt;**
  (handshake Tauri ↔ sidecar đã qua). Ghi lại số cổng.
- [ ] **05.5** Đóng app, mở lại → số cổng **khác** lần trước (cổng ngẫu nhiên mỗi lần mở).
- [ ] **05.6** Test âm — app không nhận sidecar lạ. Bản cũ tự "nhận" bất kỳ thứ gì trả
  `{"status":"ok"}` ở `http://127.0.0.1:8000/health`; bản mới phải bỏ qua nó. Đóng app, rồi trong
  một cửa sổ PowerShell khác dựng một `/health` giả trên cổng 8000:

  ```powershell
  @"
  from http.server import BaseHTTPRequestHandler, HTTPServer
  class H(BaseHTTPRequestHandler):
      def do_GET(self):
          self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
          self.wfile.write(b'{"status":"ok"}')
  HTTPServer(("127.0.0.1", 8000), H).serve_forever()
  "@ | Set-Content -Encoding utf8 $env:TEMP\fake_health.py
  cd backend; uv run python $env:TEMP\fake_health.py
  ```

  Mở app → Diagnostics vẫn **Ready** nhưng ở cổng **khác 8000**, và Bake preview ở 05.7 vẫn chạy.
  Nhấn `Ctrl+C` để tắt server giả khi xong.
- [ ] **05.7** Mở demo project → Bake preview chạy xong, preview hiện đúng (Blender trong sidecar hoạt động).

Bản dev **không** đăng ký deep link `kusshoes-editor://`, nên nút "Open in KusStudio Desktop"
trên web chưa mở được app ở bước này — cần Bước 3.

## Bước 3 — Bản cài (cần cho T14)

Vẫn trong cửa sổ PowerShell đã đặt biến ở Bước 1:

```powershell
cd desktop
npm run build:production
```

Script này: chuẩn bị Blender → đóng gói backend thành `kusshoes-backend.exe` (PyInstaller) → `tauri build`.
Chạy từ PowerShell 7 (`pwsh`) mà báo `Get-FileHash ... is not recognized`: script con chạy bằng
Windows PowerShell 5.1 và thừa hưởng `PSModulePath` của pwsh 7 — chạy `Remove-Item Env:PSModulePath`
trong cửa sổ đó rồi chạy lại.
Bộ cài nằm ở `desktop\src-tauri\target\release\bundle\` (`nsis\*.exe` hoặc `msi\*.msi`). Cài bản đó;
bộ cài đăng ký scheme `kusshoes-editor://` với Windows.

- [ ] **03.1** `npm run build:production` chạy hết không lỗi và có file bộ cài trong `bundle\`.
- [ ] **03.2** Cài xong, mở app từ Start menu → Diagnostics **Ready** (bản đóng gói tự chạy
  `kusshoes-backend.exe` + Blender đi kèm, không cần Python/Blender cài ngoài).

## Bước 4 — T12: app mobile

Cần Flutter SDK + Android SDK (Android Studio).

```powershell
cd mobile
flutter pub get
flutter analyze
flutter test
flutter build apk --release `
  --dart-define=KUSSHOES_BASE_URL=https://136.85.55.175.sslip.io `
  --dart-define=COMPUTE_BASE_URL=https://relay.136.85.55.175.sslip.io `
  --dart-define=KUSSHOES_WEB_URL=https://kusshoes.vercel.app
```

Ba `--dart-define` trên trùng với giá trị mặc định trong `mobile/lib/config/app_config.dart`; chỉ cần truyền khi trỏ sang server khác.
APK: `mobile\build\app\outputs\flutter-apk\app-release.apk` → cài lên điện thoại.

**Checklist T12:**

- [ ] **12.1** `flutter analyze` → `No issues found!` (CI cũng chặn cả mức `info`).
- [ ] **12.2** `flutter test` → `All tests passed!`.
- [ ] **12.3** `flutter build apk --release` tạo được `app-release.apk`, cài lên điện thoại được.
- [ ] **12.4** Luồng quay → upload → preview → "Lưu project" chạy trên điện thoại thật: làm ở dòng 2–3 của Bước 5.
  Màn quay **không còn** bước crop (crop giờ làm trên desktop).

## Bước 5 — T14: test end-to-end

### Tiền đề

- [ ] **14.0a** Vercel Production đã redeploy với `VITE_API_BASE_URL=https://136.85.55.175.sslip.io`
  (bỏ tick build cache); email test nằm trong "Test users" của Google OAuth.
- [ ] **14.0b** Dùng bản **đã cài** ở Bước 3 (bản dev không nhận deep link).
- [ ] **14.0c** Tài khoản test đang ở gói **Pro**. Lý do (theo bảng `plans` và BR-99):

  | Gói | Export/tháng | Định dạng |
  |---|---|---|
  | Free | **0** → không bake/export được | GLB |
  | Basic | 100 | GLB |
  | Pro | 300 | **GLB + OBJ** |

  Chỉ Pro mới kiểm được cả GLB lẫn OBJ. Cấp gói: đăng nhập admin ở
  `https://kusshoes.vercel.app/admin` → Users → chọn user → **Grant plan** → Pro.
  (Admin có thể đã sửa bảng `plans`; kiểm tra lại trong Admin → Plans nếu kết quả khác bảng trên.)

### Chạy thử — tick từng dòng

| # | Thao tác | Kỳ vọng (đạt khi) | ✓ |
|---|---|---|---|
| 1 | Đăng nhập Google trên kusshoes.vercel.app | Vào được dashboard | [ ] |
| 2 | Mobile: đăng nhập → quay video → upload | Thanh tiến trình chạy, KIRI xử lý xong, không có bước crop trên mobile | [ ] |
| 3 | Mobile: xem preview → "Lưu project" | Lưu thành công, có nút "Mở trên Desktop" | [ ] |
| 4 | Web: mở project đó | Có model, trạng thái `raw` | [ ] |
| 5 | "Open in KusStudio Desktop" | Trình duyệt hỏi mở app → app đã cài mở **đúng project** | [ ] |
| 6 | Kéo crop box → "Cắt & làm sạch" | Phần giữ lại đúng hướng lên/xuống, trước/sau, kể cả khi xoay box; model chuyển sang `ready` | [ ] |
| 7 | Thêm sticker + text → Bake | Preview hiện đúng vị trí sticker/text | [ ] |
| 8 | Export GLB và OBJ | Cả hai file nằm trong thư mục **Downloads**; mở `.glb` bằng 3D Viewer (hoặc kéo vào https://gltf-viewer.donmccurdy.com) thấy model có sticker/text | [ ] |
| 9 | Web → trang project → danh sách export | Hiện đúng các bản vừa export | [ ] |
| 10 | Bake lại, **tắt app bằng Task Manager** khi đang bake → mở lại → Bake ngay | Bị từ chối với lỗi đang bake (`PROJ_BAKE_IN_PROGRESS`), vì job cũ vẫn giữ lease | [ ] |
| 11 | Chờ **60 phút** (`CLAIM_LEASE_SECONDS = 3600`) kể từ lúc bắt đầu bake ở dòng 10 → Bake lại | Job cũ tự huỷ, bake mới chạy xong | [ ] |
| 12 | Crop lại lần nữa (project đã có thiết kế) | App **hỏi xác nhận**; đồng ý → crop chạy, thiết kế cũ bị reset | [ ] |
| 13 | Đổi tài khoản test về **Free** (Admin → Grant plan) → Bake | Bị chặn vì hết hạn mức export (`QUOTA_EXPORT_EXCEEDED`), không tạo file | [ ] |

Dòng 13 thay cho tiêu chí cũ "bản export Free có watermark": Ticket-04 (watermark 3D) đã bỏ
ngày 2026-09-24 vì gói Free có 0 lượt export nên không bao giờ tới được bước bake.

## Bước 6 — Ghi kết quả

Tạo một GitHub issue trong `EXE-CAPSTONE-TEAM/ar-ai-exe`, tiêu đề
`Windows smoke T05/T12/T14 — <ngày>`, dán mẫu dưới rồi điền:

```markdown
- Commit ar-ai-exe: <git log --oneline -1>
- Máy: Windows <phiên bản>, CPU/RAM, GPU
- Tài khoản test: <email> — gói lúc test: Pro / Free

T05: 05.1 [ ] 05.2 [ ] 05.3 [ ] 05.4 [ ] (cổng: ___) 05.5 [ ] (cổng: ___) 05.6 [ ] 05.7 [ ]
Bản cài: 03.1 [ ] 03.2 [ ]
T12: 12.1 [ ] 12.2 [ ] 12.3 [ ] 12.4 [ ]
T14: 14.0a [ ] 14.0b [ ] 14.0c [ ]
     1 [ ] 2 [ ] 3 [ ] 4 [ ] 5 [ ] 6 [ ] 7 [ ] 8 [ ] 9 [ ] 10 [ ] 11 [ ] 12 [ ] 13 [ ]

Ô không đạt: <số ô> — <mô tả + ảnh + log theo mục "Khi lỗi">
```

Ticket chỉ được đánh dấu xong khi **mọi ô** của nó đạt.

## Khi lỗi — gửi gì cho team

- Output lệnh bị lỗi (copy nguyên văn).
- Log app: `%APPDATA%\com.kusshoes.editor\runtime\logs\` (`backend.log`, `backend.err.log`; hoặc nút "Open logs"/"Copy diagnostics" trong app).
- Thời điểm lỗi (giờ VN) để đối chiếu log server.
- Với T14: số thứ tự bước + ảnh chụp màn hình.
