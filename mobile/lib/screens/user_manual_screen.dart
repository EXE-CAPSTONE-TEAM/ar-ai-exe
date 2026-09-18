import 'package:flutter/material.dart';

import '../app/app_theme.dart';

class UserManualScreen extends StatelessWidget {
  const UserManualScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(18, 20, 18, 120),
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.orange.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.orange.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      'SC-24 · CẨM NANG',
                      style: AppTheme.monoFont(
                        fontSize: 11,
                        color: AppTheme.orange,
                        letterSpacing: 1.0,
                      ),
                    ),
                  ),
                  const Spacer(),
                  const Icon(Icons.menu_book_outlined, color: AppTheme.orange),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                'Hướng Dẫn & Nghệ Nhân',
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                      fontWeight: FontWeight.w900,
                      height: 1.08,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                'Quy chuẩn quét mô hình 3D và cẩm nang kết nối nghệ nhân gia công giày cá nhân hóa ngoài thực tế.',
                style: AppTheme.bodyFont(
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.72),
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 24),
              const _WorkflowGuideSection(),
              const SizedBox(height: 28),
              const _PostExportFaqSection(),
              const SizedBox(height: 28),
              const _ArtisanDirectorySection(),
            ],
          ),
        ),
      ),
    );
  }
}

class _WorkflowGuideSection extends StatelessWidget {
  const _WorkflowGuideSection();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'QUY TRÌNH 3 BƯỚC CHUẨN',
          style: AppTheme.monoFont(
            fontSize: 12,
            letterSpacing: 1.5,
            color: AppTheme.orange,
          ),
        ),
        const SizedBox(height: 12),
        const _StepCard(
          step: '01',
          title: 'Quét Giày Bằng AI (360°)',
          description:
              'Đặt đôi giày ở nơi đủ sáng (tránh bóng râm gắt), giữ camera ngang thân giày và đi vòng quanh 360° trong 30-60 giây.',
          icon: Icons.center_focus_strong,
        ),
        const SizedBox(height: 10),
        const _StepCard(
          step: '02',
          title: 'Tùy Biến Trên Kus Studio',
          description:
              'Mở dự án trên Web/Desktop: thêm sticker decal, ký tên, vẽ artwork vector và nướng decal (Bake) ôm khít bề mặt lưới 3D.',
          icon: Icons.palette_outlined,
        ),
        const SizedBox(height: 10),
        const _StepCard(
          step: '03',
          title: 'Xuất File & Giao Nghệ Nhân',
          description:
              'Tải file GLB/OBJ kèm Gói tham khảo màu sắc hoặc tạo Link Nghệ nhân (SC-34) để thợ gia công vẽ tay ngoài thực tế.',
          icon: Icons.brush_outlined,
        ),
      ],
    );
  }
}

class _StepCard extends StatelessWidget {
  const _StepCard({
    required this.step,
    required this.title,
    required this.description,
    required this.icon,
  });

  final String step;
  final String title;
  final String description;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Card(
      color: isDark ? AppTheme.darkCard : Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: AppTheme.orange.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.orange.withValues(alpha: 0.35)),
              ),
              alignment: Alignment.center,
              child: Text(
                step,
                style: AppTheme.monoFont(
                  fontSize: 14,
                  fontWeight: FontWeight.w900,
                  color: AppTheme.orange,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: AppTheme.headingFont(
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: AppTheme.bodyFont(
                      fontSize: 13,
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PostExportFaqSection extends StatelessWidget {
  const _PostExportFaqSection();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.orange.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.orange.withValues(alpha: 0.25)),
      ),
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.help_outline, color: AppTheme.orange, size: 22),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'XUẤT FILE 3D RỒI LÀM GÌ?',
                  style: AppTheme.headingFont(
                    fontSize: 14,
                    fontWeight: FontWeight.w900,
                    color: AppTheme.orange,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'KusShoes là nền tảng thiết kế & số hóa 3D (không trực tiếp sản xuất giày vật lý). Để hiện thực hóa thiết kế lên đôi giày thật của bạn:',
            style: AppTheme.bodyFont(
              fontSize: 13.5,
              height: 1.45,
            ),
          ),
          const SizedBox(height: 12),
          _bulletPoint('1. Mở tính năng "Tạo Link Nghệ Nhân" trong dự án đã hoàn tất.'),
          _bulletPoint('2. Gửi đường link độc lập (SC-34) cho xưởng hoặc nghệ nhân vẽ giày.'),
          _bulletPoint('3. Nghệ nhân mở link trên trình duyệt xoay 360°, xem chuẩn mã màu Pantone/Hex và tỷ lệ decal để vẽ tay chính xác 100%.'),
        ],
      ),
    );
  }

  Widget _bulletPoint(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('• ', style: TextStyle(color: AppTheme.orange, fontWeight: FontWeight.bold)),
          Expanded(
            child: Text(text, style: const TextStyle(fontSize: 13, height: 1.35)),
          ),
        ],
      ),
    );
  }
}

class _ArtisanDirectorySection extends StatelessWidget {
  const _ArtisanDirectorySection();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'DANH BẠ NGHỆ NHÂN THAM KHẢO (BR-102)',
                style: AppTheme.monoFont(
                  fontSize: 12,
                  letterSpacing: 1.2,
                  color: AppTheme.orange,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                'Việt Nam',
                style: AppTheme.monoFont(fontSize: 10, color: Colors.white70),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        const _ArtisanTile(
          name: 'Kus Custom Studio HCMC',
          specialty: 'Vẽ tay tả thực, Decal Heat-Transfer, Angelus Paint',
          location: 'Quận 1, TP. Hồ Chí Minh',
          phone: '09xx xxx 567',
          instagram: '@kus_custom_vn',
          rating: '4.9 ★ (120+ đôi)',
        ),
        const SizedBox(height: 10),
        const _ArtisanTile(
          name: 'Hanoi Sneaker Atelier',
          specialty: 'Repaint cổ điển, nhuộm đế vintage, vẽ anime graffiti',
          location: 'Đống Đa, Hà Nội',
          phone: '09xx xxx 432',
          instagram: '@hn_sneaker_art',
          rating: '4.8 ★ (85+ đôi)',
        ),
        const SizedBox(height: 10),
        const _ArtisanTile(
          name: 'Danang Street Art Shoes',
          specialty: 'Airbrush shading, chống nước nano cao cấp',
          location: 'Hải Châu, Đà Nẵng',
          phone: '09xx xxx 233',
          instagram: '@danang_customizer',
          rating: '4.9 ★ (60+ đôi)',
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.04),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: Text(
            '⚠️ Tuyên bố miễn trừ (BR-101): KusShoes cung cấp danh bạ tham khảo độc lập nhằm hỗ trợ kết nối khách hàng và nghệ nhân tự do. KusShoes không thu phí hoa hồng và không chịu trách nhiệm chất lượng gia công vật lý bên ngoài.',
            style: AppTheme.bodyFont(
              fontSize: 11.5,
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.55),
              height: 1.35,
            ),
          ),
        ),
      ],
    );
  }
}

class _ArtisanTile extends StatelessWidget {
  const _ArtisanTile({
    required this.name,
    required this.specialty,
    required this.location,
    required this.phone,
    required this.instagram,
    required this.rating,
  });

  final String name;
  final String specialty;
  final String location;
  final String phone;
  final String instagram;
  final String rating;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Card(
      color: isDark ? AppTheme.darkCard : Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: AppTheme.headingFont(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppTheme.statusScanned.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    rating,
                    style: AppTheme.monoFont(
                      fontSize: 11,
                      color: AppTheme.statusScanned,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              specialty,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.orange.withValues(alpha: 0.9),
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.location_on_outlined, size: 15, color: Colors.grey),
                const SizedBox(width: 4),
                Text(location, style: const TextStyle(fontSize: 12, color: Colors.grey)),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                OutlinedButton.icon(
                  onPressed: () {},
                  icon: const Icon(Icons.phone, size: 14),
                  label: Text(phone),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(0, 34),
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    textStyle: AppTheme.monoFont(fontSize: 11),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton.icon(
                  onPressed: () {},
                  icon: const Icon(Icons.camera_alt_outlined, size: 14),
                  label: Text(instagram),
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.orange,
                    textStyle: AppTheme.monoFont(fontSize: 11),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
