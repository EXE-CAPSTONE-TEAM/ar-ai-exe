# 1. Deprecate Artisan Links (Loại bỏ tính năng Kết nối Nghệ nhân Ngoài đời)

Date: 2026-09-21
Status: Accepted

## Context (Bối cảnh)

Trong tài liệu đặc tả ban đầu (SRS v2.1/v2.2) và BR-101, hệ thống dự kiến cung cấp tính năng **Artisan Share Links**: cho phép người dùng sinh một liên kết xem 3D độc lập (kèm token truy cập bảo mật và thời hạn sử dụng) để gửi qua Zalo / Messenger cho thợ vẽ hoặc nghệ nhân gia công ngoài đời thực.

Tuy nhiên, trong quá trình phát triển và định hình lại ranh giới sản phẩm:
1. Trọng tâm cốt lõi của KusShoes là **Chụp/Quét 3D giày bằng AI (Mobile)** và **Bàn làm việc tùy biến sticker/vẽ tay (Kus Studio Web/Desktop)** với khả năng xuất file chuẩn công nghiệp (`.glb`, `.obj`, `.mtl`).
2. Việc duy trì nghiệp vụ liên kết thợ vẽ ngoài đời (quản lý token chia sẻ, phân quyền xem read-only của bên thứ ba không có tài khoản, gia hạn/thu hồi link) làm tăng độ phức tạp không cần thiết cho cả tầng Control Plane và giao diện người dùng Mobile.
3. Người dùng chuyên nghiệp có thể tải trực tiếp gói file xuất 3D hoàn chỉnh (`Export Package`) hoặc gửi URL dự án Kus Studio khi cần trao đổi với đối tác gia công.

## Decision (Quyết định)

1. **Loại bỏ hoàn toàn phân hệ Artisan Share Links khỏi phạm vi phát triển**:
   - Phía Mobile không tích hợp các API chia sẻ thợ vẽ (`POST /projects/{id}/artisan-links`, `GET /projects/{id}/artisan-links`, `revoke`, `renew`).
   - Màn hình Cẩm nang (`user_manual_screen.dart` / Tab 3) được điều chỉnh thành **Cẩm nang hướng dẫn quét 3D**, không còn nhắc đến việc chia sẻ cho nghệ nhân.
2. **Tập trung nguồn lực vào trải nghiệm cốt lõi**:
   - Khép kín luồng Quét 3D -> Xem mô hình -> Bàn giao sang Kus Studio Web.
   - Cung cấp đầy đủ tính năng tự phục vụ (Self-service): Quản lý dự án, Thùng rác, Nâng cấp gói cước trực tuyến và Quản trị tài khoản tuân thủ Store.

## Consequences (Hệ quả)

- **Tích cực**:
  - Tinh giản giao diện Mobile, giảm bớt các nút bấm và bước thao tác rườm rà.
  - Loại bỏ các rủi ro bảo mật liên quan đến token chia sẻ công khai không cần đăng nhập.
  - Tập trung tối đa vào độ mượt mà của luồng quét và bàn giao Web Studio.
- **Tiêu cực**:
  - Không còn luồng chia sẻ mô hình 3D riêng biệt cho người không có tài khoản KusShoes. Đối tác gia công cần xem mô hình qua file GLB được xuất ra hoặc qua tài khoản đăng nhập trên Web.
