# Việc cần làm phía server (làm sau)

Cập nhật: 2026-09-26. Liên quan: `docs/windows-kusstudio-runbook.md` (T05/T12/T14) và
`KusShoes/docs/mobile-google-login-deploy.md` (chi tiết deploy đăng nhập Google mobile).

Server hiện tại **chưa** có code mới: `POST /api/v1/auth/google/mobile/exchange` chưa tồn tại và
`GET /api/v1/auth/google?client=mobile` (thiếu PKCE) trả `307` thay vì `422`.

## Thứ tự làm

| # | Việc | Bắt buộc? | Chặn gì |
|---|---|---|---|
| 1 | Deploy KusShoes API lên VM | **Có** | Đăng nhập Google trên mobile, T14 |
| 2 | Kiểm tra GitHub Actions trên `main` | **Có** | Biết image `:latest` có được đẩy lên registry không |
| 3 | Vercel redeploy với đúng `VITE_API_BASE_URL` | **Có** | T14 bước 1, 4, 5 |
| 4 | Google OAuth: Test users | **Có** | Mọi đăng nhập Google (web + mobile) |
| 5 | KIRI relay | Không | — |
| 6 | Dọn DB test local | Không (máy dev) | — |

---

## 1. Deploy KusShoes API lên VM (136.85.55.175)

Code cần deploy: nhánh `feature/client-side-3d` @ `20d38c3`, **cùng nội dung** với `main` @ `4f994ee`.
Gồm:

- `497f7d4` — đăng nhập Google cho mobile (luồng web + mã dùng một lần + PKCE).
- PR #8 (qua `20d38c3`) — analytics admin (`credit_revenue_vnd`, reconciliation) + FE admin/landing.

Không có migration mới (head vẫn `028`); không cần sửa `.env` (các biến mới đều có default).

```bash
ssh <user>@136.85.55.175
cd <repo KusShoes trên VM>
git fetch
git checkout feature/client-side-3d        # hoặc main — hai nhánh cùng cây code
git pull
git log --oneline -1                       # phải là 20d38c3 (hoặc 4f994ee nếu dùng main)

cd BE
docker compose -f docker-compose.prod.yml -f docker-compose.vm.yml up -d --build api
docker compose -f docker-compose.prod.yml -f docker-compose.vm.yml ps api   # đợi healthy, ~1–3 phút
docker compose -f docker-compose.prod.yml -f docker-compose.vm.yml logs --tail 50 api
```

`entrypoint.sh` tự chạy `alembic upgrade head` khi khởi động — log phải có `Migrations complete`.

**Kiểm tra sau deploy** (chạy ở máy bất kỳ):

```bash
API=https://136.85.55.175.sslip.io
curl -s $API/openapi.json | grep -o '/api/v1/auth/google/mobile/exchange'           # có kết quả
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/v1/auth/google?client=mobile"    # 422
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/v1/auth/google"                  # 307 (web không đổi)
```

Rồi trên điện thoại (APK hiện đã cài là bản mới, không cần cài lại): **Tiếp tục với Google / Gmail**
→ chọn tài khoản → tab tự đóng → app vào màn chính. Nếu tab vẫn dừng ở trang web KusShoes nghĩa là
API chưa lên bản mới.

**Rollback:** trước khi `git pull`, ghi lại commit đang chạy (`git log --oneline -1`; nhiều khả năng
là `7035018`), rồi `git checkout <commit đó>` và chạy lại lệnh `up -d --build api`.
Không có migration nên rollback không cần downgrade DB.

## 2. GitHub Actions trên `main` (@ `4f994ee`)

Push lên `main` kích hoạt `Backend CI` và `Frontend CI`. Việc cần làm:

- Mở tab **Actions** của `EXE-CAPSTONE-TEAM/KusShoes`, xác nhận cả hai workflow xanh
  (local đã chạy tương đương: BE 334 + CI subset 89 + unit 29 passed, FE lint/test/build OK).
- `Backend CI` có bước **Push production image** (`$REGISTRY_IMAGE:latest`) khi secret
  `BACKEND_REGISTRY_IMAGE` được đặt. Kiểm tra có môi trường nào đang kéo `:latest` tự động không —
  nếu có, bản mới đã lên đó.

## 3. Vercel (web `kusshoes.vercel.app`)

Tiền đề của T14 trong runbook:

- Project Settings → Environment Variables (Production): `VITE_API_BASE_URL=https://136.85.55.175.sslip.io`.
- Redeploy Production **bỏ tick "Use existing build cache"**.
- Kiểm tra Vercel build từ nhánh nào (Settings → Git → Production Branch). `main` giờ có thêm
  UI admin/landing của PR #8 và đăng nhập Google mobile — đó là bản sẽ lên nếu Vercel build từ `main`.

## 4. Google OAuth (Google Cloud Console)

- **Không cần** thêm redirect URI hay Android client: mobile dùng lại
  `https://136.85.55.175.sslip.io/api/v1/auth/google/callback` như web.
- OAuth consent screen đang ở chế độ Testing → mọi email dùng để test (web + mobile) phải nằm trong
  **Test users**, nếu không Google báo `access_denied`.
- Khi phát hành thật: chuyển consent screen sang **In production** (có thể cần Google xác minh app).

## 5. KIRI relay (`relay.136.85.55.175.sslip.io`) — không bắt buộc

Relay build từ `ar-ai-exe/backend` (`APP_ROLE=relay`). Thay đổi mới ở ar-ai-exe (`9af70c4`,
`BAKE_QUEUE_ENABLED`) mặc định `true` nên **không đổi hành vi** relay — không cần redeploy. Nếu muốn
relay cùng phiên bản với nhánh: cập nhật `../relay` từ `ar-ai-exe` `feature/client-side-3d` rồi
`docker compose -f docker-compose.prod.yml -f docker-compose.vm.yml up -d --build kiri-relay`.

## 6. Dọn DB test local (máy dev, không phải server) — không bắt buộc

DB `kusshoes_test` trong docker local ghi `alembic_version = 029` — số cũ của migration
`client_executed_jobs` trước khi bị đổi thành `028` (commit `05719f9`). Test vẫn chạy được, nhưng
`alembic upgrade` trên DB đó báo `Can't locate revision '029'`. Schema đã đúng nên chỉ cần đánh dấu lại:

```bash
docker exec kusshoes_api sh -c \
  "DATABASE_URL=postgresql+asyncpg://kusshoes:kusshoes@db:5432/kusshoes_test alembic stamp --purge 028"
```

## Sau khi xong 1–4

Chạy checklist T14 trong `docs/windows-kusstudio-runbook.md` (Bước 5). Khi lỗi gửi: số bước, ảnh
chụp, giờ VN, và log `%APPDATA%\com.kusshoes.editor\runtime\logs\` (desktop) hoặc
`docker compose ... logs api` (server).
