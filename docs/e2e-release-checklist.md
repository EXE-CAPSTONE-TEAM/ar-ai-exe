# Checklist kiểm thử E2E như người dùng thật + chuẩn bị đăng APKPure

Mục đích: đi hết luồng **quét giày trên điện thoại → xem dự án trên web → cài và mở KusStudio Desktop
trên Windows**, đúng như một người dùng mới, **chỉ dùng những gì người dùng có**: trang web, file tải
về, không terminal, không repo, không quyền Administrator. Sau đó điền phần APKPure (mục 6–7).

Phiên bản đang phát hành (kiểm tra lại trước khi test):

| Thành phần | Bản | Nguồn tải |
|---|---|---|
| App Android | `mobile-v0.1.0` (versionCode 100, Android 7.0+) | https://kusshoes.vercel.app/products → **Tải file APK** |
| KusShoes Editor (Windows) | `desktop-v0.1.0` | Dashboard → **Get Desktop App**, hoặc Products → **Tải trình cài đặt Desktop** |
| Web | `main` trên Vercel | https://kusshoes.vercel.app |
| API | `api.kusshoes.kietta.me`, relay `relay.kusshoes.kietta.me` | — |

## Cách ghi kết quả

- Mỗi bước: đánh `[x]` nếu đạt, hoặc ghi **❌ + giờ (HH:MM, giờ Việt Nam) + ảnh chụp** nếu lỗi.
  Giờ chính xác giúp đối chiếu log server (API, relay, worker) theo từng phút.
- **Chụp màn hình điện thoại ở các bước có dấu 📸**: dùng luôn cho mục ảnh chụp của APKPure (mục 6).
- Lỗi trên desktop: bấm nút **Logs** trong app (mở `%APPDATA%\com.kusshoes.editor\runtime\logs`),
  nén cả thư mục gửi kèm. Các file đáng chú ý: `dependency-install.err.log` (tải bộ dựng hình 3D),
  `update-check.err.log` (kiểm tra cập nhật), log của backend cục bộ.
- Đừng sửa gì giữa chừng. Gặp lỗi thì ghi lại, rồi đi tiếp nếu còn đi được.

---

## 0. Chuẩn bị

- [ ] Điện thoại Android **7.0 trở lên**, có camera, pin > 50%, đang có mạng.
- [ ] Máy Windows 10/11 64-bit **chưa từng cài** KusShoes Editor, Blender, Python hay Node. Nếu máy đã
      từng cài: gỡ KusShoes Editor, xoá `%APPDATA%\com.kusshoes.editor`.
- [ ] Đăng nhập Windows bằng **tài khoản thường, không phải Administrator** (người dùng thật thường
      không có quyền admin).
- [ ] Trình duyệt chưa đăng nhập KusShoes (dùng cửa sổ ẩn danh hoặc profile mới).
- [ ] Còn trống trên ổ C: ≥ 3 GB (app sau khi cài khoảng 60 MB, bộ dựng hình 3D khoảng 900 MB sau khi giải nén, cộng file tạm 400 MB lúc tải).
- [ ] Chọn tài khoản test:
  - Google: phải nằm trong **Test users** của OAuth consent screen, vì app Google đang ở chế độ
    *Testing*; tài khoản ngoài danh sách sẽ bị Google chặn (xem mục 6, dòng "Google OAuth").
  - Email + mật khẩu: một email chưa đăng ký, để thử cả luồng đăng ký và OTP.
- [ ] Một đôi giày thật, đặt trên nền trơn, đủ sáng, có chỗ đi vòng quanh 360°.

## 1. Mobile: tải, cài, đăng nhập, quét

### 1.1 Tải và cài APK (trên điện thoại)

- [ ] Mở https://kusshoes.vercel.app/products trên điện thoại. Tab **Android** đang được chọn, dòng mô
      tả ghi "Android 7.0 trở lên", nút ghi **Tải file APK v0.1.0**.
- [ ] Bấm tải. File tên `KusShoes-Android.apk`, khoảng 55 MB.
- [ ] Mở file. Android hỏi cho phép cài từ trình duyệt → cho phép. Ghi lại **nguyên văn** mọi cảnh
      báo (Play Protect "ứng dụng không xác định"…) để viết hướng dẫn cho người dùng.
- [ ] Cài xong, icon trên màn hình chính là **logo KusShoes**, tên app **KusShoes**.

### 1.2 Tài khoản

- [ ] 📸 Màn hình đăng nhập.
- [ ] Đăng ký bằng email: nhận được mã OTP qua email, nhập mã, vào được app.
- [ ] Đăng xuất, rồi **Đăng nhập với Google**: trình duyệt mở trang Google, chọn tài khoản, quay lại app
      đã đăng nhập.
- [ ] Đóng hẳn app, mở lại: vẫn còn đăng nhập.

### 1.3 Quét giày

- [ ] Vào màn hình quét. Android hỏi quyền **Camera** → cho phép. Ghi lại nếu app còn hỏi quyền
      **Micro** hoặc **Bộ nhớ** (app quay video không tiếng; hai quyền này do plugin camera khai báo, xem
      mục 6).
- [ ] 📸 Màn hình quay có hướng dẫn.
- [ ] Quay theo hướng dẫn trên màn hình ("Xoay 2 tầng quanh đôi giày trong 45 giây") rồi dừng.
- [ ] Màn hình tải lên: phần trăm tăng dần tới xong, không kẹt.
- [ ] 📸 Màn hình "Đang dựng lưới 3D": phần trăm tăng dần. KIRI Engine thường mất vài phút; ghi lại
      thời gian thực tế từ lúc tải xong tới lúc dựng xong.
- [ ] Khi dựng xong: hiện **100%** (không dừng ở 75%), huy hiệu **SẴN SÀNG**, hiện bản xem trước 3D
      xoay được.
- [ ] 📸 Màn hình xem trước mô hình 3D.
- [ ] Đổi tên dự án (ví dụ "E2E <ngày>"), bấm **Lưu project**: nút xoay cho tới khi lưu xong, rồi hiện
      "Dự án của bạn đã được lưu thành công!" và nút chuyển thành **Đã lưu project**.
- [ ] Thử luồng lỗi: bật chế độ máy bay giữa lúc tải video lên → app báo lỗi rõ ràng và có nút thử lại;
      tắt chế độ máy bay → thử lại được.

## 2. Web: dự án xuất hiện

- [ ] Trên máy Windows, mở https://kusshoes.vercel.app, đăng nhập **cùng tài khoản** với điện thoại (thử
      cả nút Google).
- [ ] Trang **Projects** có dự án "E2E <ngày>", ở nhóm *Designing*.
- [ ] Thẻ dự án hiện **ảnh mô hình vừa quét** (thumbnail chụp từ điện thoại), không phải ảnh giày mặc định.
- [ ] Bấm vào dự án: trang chi tiết mở được, tải lại trang (F5) vẫn đúng dự án.
- [ ] Trang **Products**: nội dung khớp tính năng thật (không còn LiDAR, TestFlight, FBX/USDZ, "cổng 8421"),
      nút iOS ghi "sắp ra mắt".

## 3. Desktop: tải, cài, lần mở đầu tiên

### 3.1 Tải và cài

- [ ] Dashboard → **Get Desktop App**: tiêu đề "KusShoes Editor v0.1.0", có 3 bước hướng dẫn. Bấm
      **Download for Windows** → tải `KusShoesEditor-Setup-x64.exe` (khoảng 50 MB).
- [ ] Mở file. Nếu SmartScreen hiện "Windows protected your PC": **More info → Run anyway** (bản cài
      chưa được ký số). Chụp màn hình cảnh báo.
- [ ] Trình cài đặt **không hỏi quyền Administrator** (không có hộp thoại UAC), bấm Next/Install là xong.
- [ ] Nếu máy chưa có WebView2, trình cài tự cài. Ghi lại nếu có bước này.
- [ ] Có shortcut **KusShoes Editor** trong Start menu; icon là logo KusShoes, không phải logo Flutter.

### 3.2 Lần mở đầu tiên

- [ ] Mở app: cửa sổ KusShoes Editor hiện ra trong vài giây.
- [ ] Đầu trang có banner **"Đang chuẩn bị KusShoes Editor (chỉ lần đầu)"** kèm thanh tiến trình: đang
      tải bộ dựng hình 3D khoảng 400 MB, sau đó "Đang cài đặt…". Ghi lại thời gian tải và giải nén.
- [ ] Trong lúc tải vẫn bấm và xem được các màn hình khác (app không bị treo).
- [ ] Xong: banner "KusShoes Editor đã sẵn sàng" rồi tự ẩn. Ở Diagnostics, **Preview renderer** là
      *installed*.
- [ ] Thử luồng lỗi (nếu có thời gian): gỡ app, xoá `%APPDATA%\com.kusshoes.editor`, cài lại, rút mạng giữa
      lúc tải bộ dựng hình → banner báo lỗi và có nút **Thử lại**; cắm mạng, bấm Thử lại → tải xong.
- [ ] Đóng app, mở lại: **không** tải lại bộ dựng hình và **không** hiện lại banner.

## 4. Web → Desktop: mở dự án đã quét

- [ ] Trên web, mở dự án "E2E <ngày>" → **Open in KusStudio Desktop**. Trình duyệt hỏi mở
      "KusShoes Editor" → cho phép (có thể tick "luôn cho phép").
- [ ] App desktop nhận yêu cầu và mở **đúng dự án đó**, không bắt đăng nhập lại.
- [ ] Mô hình quét thô hiện ra ở bước crop. Chỉnh khung crop rồi chạy prepare: xong, mô hình chuyển sang
      trạng thái sẵn sàng chỉnh sửa.
- [ ] Thêm 1 sticker và 1 dòng chữ, bấm **Save**. Tải lại web: dự án vẫn còn thay đổi (xem thời gian sửa).
- [ ] **Bake preview** chạy xong, xem được ảnh hoặc mô hình preview.
- [ ] **Export** GLB và OBJ: file tải được và mở được (ví dụ GLB mở bằng https://gltf-viewer.donmccurdy.com).
- [ ] Luồng chưa cài app: trên một trình duyệt hoặc máy **chưa cài** KusShoes Editor, bấm Open in KusStudio
      Desktop → sau khoảng 3 giây hiện gợi ý "KusStudio didn't open? Download KusShoes Editor for Windows".

## 5. Cập nhật (làm khi có bản mới)

Làm khi có bản `desktop-v0.1.1` / `mobile-v0.1.1` trở lên.

- [ ] Desktop: mở bản cũ đang cài → banner **"Có phiên bản mới 0.1.x"** → **Cập nhật ngay** → thanh tiến
      trình → app tự khởi động lại ở bản mới, dữ liệu và dự án còn nguyên, không tải lại bộ dựng hình.
- [ ] Android: cài APK mới đè lên bản cũ **không cần gỡ**, và vẫn còn đăng nhập (nếu phải gỡ trước thì
      bản mới ký sai khoá; báo ngay).

## 6. APKPure: thông tin và tài nguyên cần có

APKPure không cho truy cập tự động các trang hướng dẫn chính thức (`403`), nên các yêu cầu dưới đây lấy
từ hướng dẫn của bên thứ ba (xem Nguồn). **Đối chiếu lại trong Developer Console lúc nộp** và sửa bảng
này nếu khác.

| Mục | Yêu cầu | Trạng thái |
|---|---|---|
| Tài khoản developer | Miễn phí. Username, email, mật khẩu, tên developer, giới thiệu, website, icon 512×512, banner hồ sơ 4096×2304 | ☐ Chưa tạo |
| File app | APK đã ký bằng khoá release | ✅ `KusShoes-Android.apk` trong release `mobile-v0.1.0`, ký bằng chứng chỉ `6cd7bf77…3dfd` |
| Tên gói | Cố định mãi mãi | ✅ `vn.kusshoes.mobile` |
| Tên app | — | ✅ `KusShoes` |
| Icon | 512×512 | ✅ `docs/store/apkpure/icon-512.png` (logo KusShoes; `mobile/web/icons/Icon-512.png` vẫn là logo Flutter, **đừng dùng**) |
| Banner / feature graphic | 1024×500 | ✅ `docs/store/apkpure/banner-1024x500.png` |
| Ảnh chụp màn hình | Tối thiểu 480×800, lấy từ các bước 📸 ở mục 1 | ☐ Chụp khi test |
| Mô tả ngắn và dài, *What's new* | — | ✅ Bản nháp ở mục 7 |
| Thể loại, content rating | Chọn trong console | ☐ Gợi ý: *Nghệ thuật & Thiết kế* (Art & Design); nội dung cho mọi lứa tuổi |
| **Chính sách bảo mật (URL)** | Bắt buộc | ❌ **Chưa có.** Footer web đang hiện "sắp có"; app ẩn link vì `KUSSHOES_PRIVACY_URL` trống. Cần trang nêu: dữ liệu thu thập (email, tên, video quét, mô hình 3D), gửi cho bên xử lý (KIRI Engine để dựng 3D, Cloudflare R2 để lưu trữ, Google nếu đăng nhập bằng Google), thời gian lưu, cách xoá tài khoản, email liên hệ |
| **Google OAuth** | Người dùng thật phải đăng nhập Google được | ❌ Consent screen đang ở chế độ **Testing**: chỉ Test users vào được. Trước khi mở cho công chúng phải bấm **Publish app** (có thể cần Google xác minh vì app xin email/profile) |
| Quyền Micro và Bộ nhớ | Người dùng thấy trong trang cài | ⚠️ APK khai báo `RECORD_AUDIO` và `WRITE_EXTERNAL_STORAGE`, dù app quay video không tiếng (`enableAudio: false`). Nên gỡ bằng `tools:node="remove"` trong `AndroidManifest.xml`, rồi phát hành `mobile-v0.1.1` trước khi nộp, để bớt quyền đáng ngờ |
| Liên hệ hỗ trợ | Email hỗ trợ | ☐ Chọn email chính thức (ví dụ `kusshoes@gmail.com`) |

Sau khi nộp: APKPure duyệt (theo nguồn bên thứ ba khoảng 24–48 giờ) và báo qua email.

## 7. Bản nháp nội dung trang APKPure

**Tên:** KusShoes: Quét giày 3D

**Mô tả ngắn (vi):** Quay video 360° đôi giày của bạn, nhận mô hình 3D để thiết kế trên KusStudio.

**Mô tả ngắn (en):** Record a 360° video of your sneaker and get a 3D model to design in KusStudio.

**Mô tả dài (vi):**

> KusShoes biến đôi giày thật của bạn thành mô hình 3D.
>
> • Quay một video 360° quanh đôi giày ngay trong app, có hướng dẫn từng bước.
> • Video được tải lên đám mây, KIRI Engine dựng mô hình 3D cho bạn.
> • Xem trước mô hình 3D ngay trên điện thoại rồi lưu thành dự án.
> • Dự án hiện trên web KusShoes; mở tiếp trong KusStudio Desktop (Windows) để thêm sticker, chữ và xuất
>   file GLB/OBJ.
>
> Cần tài khoản KusShoes (đăng ký bằng email hoặc Google) và kết nối Internet.

**Mô tả dài (en):**

> KusShoes turns your real sneakers into 3D models.
>
> • Record a guided 360° video around the shoe right in the app.
> • The video uploads to the cloud and KIRI Engine reconstructs the 3D model.
> • Preview the 3D model on your phone and save it as a project.
> • Your project appears on the KusShoes web app; continue in KusStudio Desktop (Windows) to add stickers
>   and text and export GLB/OBJ.
>
> Requires a KusShoes account (email or Google sign-in) and an Internet connection.

**What's new (0.1.0):** Bản phát hành đầu tiên: quét giày bằng video 360°, dựng 3D bằng KIRI Engine, lưu
dự án kèm ảnh đại diện, đăng nhập bằng email hoặc Google.

## 8. Khoá ký: bắt buộc trước khi phát hành công khai

- [ ] Đã chép **ra ngoài máy build** (trình quản lý mật khẩu + USB, cất ở hai nơi khác nhau):
  - `key/kusshoes-android-release.jks` và `key/kusshoes-android-release.properties` (mất khoá này thì
    APKPure không nhận bản cập nhật; người dùng phải gỡ app rồi cài lại).
  - `key/kusshoes-editor.key` và `key/kusshoes-editor.key.password` (mất khoá này thì app desktop đã cài
    không nhận được bản cập nhật).
- [ ] Đã mở thử bản sao lưu và thấy đúng nội dung.

## Nguồn

- Yêu cầu nộp app APKPure (icon 512×512, ảnh chụp 480×800, banner 1024×500, privacy policy URL, content
  rating): [thepssaini.com — How to publish app on APKPure](https://thepssaini.com/how-to-publish-app-on-apkpure-app-store/)
- Tạo tài khoản developer APKPure (miễn phí, các trường hồ sơ): [thepssaini.com — APKPure developer console account](https://thepssaini.com/apkpure-developer-console-account/)
- Kết quả tìm kiếm tổng hợp (icon 512×512, privacy policy, duyệt 24–48 giờ): [APKPure — How to create developer console account](https://apkpure.com/howto/how-to-create-apkpure-developer-console-account-for-free)
- Phiên bản, chữ ký và minSdk của APK: kiểm tra trực tiếp trên release `mobile-v0.1.0` (apksigner / androguard).
- Thư mục dữ liệu desktop: Tauri `app_data_dir()` = `dirs::data_dir()` + identifier `com.kusshoes.editor`.
