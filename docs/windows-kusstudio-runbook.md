# Runbook Windows — KusStudio Desktop + mobile (T05, T12, T14)

Nhánh: `feature/client-side-3d` (cả `ar-ai-exe` và `KusShoes`). Server đã chạy sẵn:

| Thành phần | URL |
|---|---|
| KusShoes API | `https://136.85.55.175.sslip.io` |
| KIRI relay (mobile scan) | `https://relay.136.85.55.175.sslip.io` |
| Web | `https://kusshoes.vercel.app` |
| R2 endpoint (sidecar tải/upload) | `https://1d92645e04fc345cde21bc7c7260e073.r2.cloudflarestorage.com` |

Server **không** xử lý 3D. Cắt mesh + bake chạy trên máy Windows trong sidecar local + Blender.

Thứ tự: **Bước 0 → 1 → 2 (T05) → 3 (bản cài) → 4 (T12) → 5 (T14)**.

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
git checkout feature/client-side-3d
git pull
```

Đã clone rồi thì chỉ cần `git fetch; git checkout feature/client-side-3d; git pull`.

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

**Đạt khi:**
- `cargo test` → 6 passed; `cargo build` không lỗi.
- App mở, màn Diagnostics hiện backend **ready** (handshake token giữa Tauri và sidecar đã qua).
- Mở demo project → Bake preview chạy được (xác nhận Blender hoạt động).

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

Thiếu `--dart-define` thì app gọi domain mặc định cũ (`api.kusshoes.vn`, `compute.kusshoes.vn`) — không tồn tại.
APK: `mobile\build\app\outputs\flutter-apk\app-release.apk` → cài lên điện thoại.

## Bước 5 — T14: test end-to-end

Tiền đề: Vercel Production đã redeploy với `VITE_API_BASE_URL=https://136.85.55.175.sslip.io`
(bỏ tick build cache); email test nằm trong "Test users" của Google OAuth.

| # | Thao tác | Kỳ vọng |
|---|---|---|
| 1 | Đăng nhập Google trên kusshoes.vercel.app | Vào được dashboard |
| 2 | Mobile: đăng nhập → quay video → upload | Tiến trình chạy, KIRI xử lý xong |
| 3 | Mobile: xem preview → "Lưu project" | Lưu thành công |
| 4 | Web: mở project | Có model, trạng thái `raw` |
| 5 | "Open in KusStudio Desktop" | App đã cài mở đúng project |
| 6 | Kéo crop box → "Cắt & làm sạch" | Phần giữ lại đúng hướng lên/xuống, trước/sau, kể cả khi xoay box |
| 7 | Thêm sticker + text → Bake | Preview hiện đúng |
| 8 | Export | File nằm trong thư mục Downloads |
| 9 | Tắt app giữa lúc bake → mở lại | Job chạy lại được (lease 3600 s) |
| 10 | Crop lại lần nữa | Hỏi xác nhận, thiết kế cũ bị reset |

## Khi lỗi — gửi gì cho team

- Output lệnh bị lỗi (copy nguyên văn).
- Log app: `%APPDATA%\com.kusshoes.editor\runtime\logs\` (`backend.log`, `backend.err.log`; hoặc nút "Open logs"/"Copy diagnostics" trong app).
- Thời điểm lỗi (giờ VN) để đối chiếu log server.
- Với T14: số thứ tự bước + ảnh chụp màn hình.
