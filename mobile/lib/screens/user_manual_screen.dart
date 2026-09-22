import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../app/app_theme.dart';
import '../config/app_config.dart';

class UserManualScreen extends StatefulWidget {
  const UserManualScreen({super.key});

  @override
  State<UserManualScreen> createState() => _UserManualScreenState();
}

class _UserManualScreenState extends State<UserManualScreen> {
  int _selectedTab = 0; // 0: 3 Bước Làm, 1: Mẹo Quay Đẹp, 2: Gửi Thợ Vẽ

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).padding.bottom;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: ListView(
            padding: EdgeInsets.fromLTRB(18, 14, 18, 112 + bottomInset),
            children: [
              // Friendly Header Tag
              Row(
                children: [
                  Flexible(
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppTheme.orange.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: AppTheme.orange.withValues(alpha: 0.35)),
                      ),
                      child: Text(
                        'DỄ HIỂU TRONG 1 PHÚT',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTheme.monoFont(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.orange,
                          letterSpacing: 0.8,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Icon(Icons.favorite_rounded, color: AppTheme.orange, size: 18),
                ],
              ),
              const SizedBox(height: 12),

              // Friendly Display Title
              Text(
                'Tự Tạo Giày Riêng',
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                      fontWeight: FontWeight.w900,
                      height: 1.05,
                      letterSpacing: -0.8,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                'Chỉ 3 bước đơn giản từ đôi giày của bạn thành bản vẽ tay ngoài đời.',
                style: AppTheme.bodyFont(
                  fontSize: 14,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.68),
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 18),

              // Segmented Pill Filter
              _buildSegmentedFilter(isDark),
              const SizedBox(height: 20),

              // Animated Tab Content
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                transitionBuilder: (child, animation) {
                  return FadeTransition(
                    opacity: animation,
                    child: SlideTransition(
                      position: Tween<Offset>(
                        begin: const Offset(0, 0.03),
                        end: Offset.zero,
                      ).animate(animation),
                      child: child,
                    ),
                  );
                },
                child: _buildCurrentTab(isDark),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSegmentedFilter(bool isDark) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: isDark ? AppTheme.darkSurface : AppTheme.lightSurface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
        ),
      ),
      child: Row(
        children: [
          _filterPill(0, '3 Bước Làm', Icons.play_circle_outline),
          _filterPill(1, 'Mẹo Quay Đẹp', Icons.light_mode_outlined),
          _filterPill(2, 'Gửi Thợ Vẽ', Icons.brush_outlined),
        ],
      ),
    );
  }

  Widget _filterPill(int index, String label, IconData icon) {
    final active = _selectedTab == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedTab = index),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: active ? AppTheme.orange : Colors.transparent,
            borderRadius: BorderRadius.circular(999),
            boxShadow: active
                ? [
                    BoxShadow(
                      color: AppTheme.orange.withValues(alpha: 0.35),
                      blurRadius: 10,
                      offset: const Offset(0, 2),
                    ),
                  ]
                : null,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 14,
                color: active ? Colors.white : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
              ),
              const SizedBox(width: 5),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTheme.headingFont(
                    fontSize: 12,
                    fontWeight: active ? FontWeight.w800 : FontWeight.w600,
                    color: active ? Colors.white : Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCurrentTab(bool isDark) {
    switch (_selectedTab) {
      case 0:
        return const _WorkflowJourneyTab(key: ValueKey(0));
      case 1:
        return const _ScanRulesTab(key: ValueKey(1));
      case 2:
      default:
        return const _ArtisanHandoverTab(key: ValueKey(2));
    }
  }
}

// =============================================================================
// TAB 0: 3 BƯỚC LÀM (FRIENDLY 3-STEP JOURNEY)
// =============================================================================

class _WorkflowJourneyTab extends StatelessWidget {
  const _WorkflowJourneyTab({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      children: [
        // BƯỚC 1: QUAY VIDEO
        _DoubleBezelCard(
          isDark: isDark,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildStepHeader(
                number: '1',
                title: 'Cầm Điện Thoại Quay 1 Vòng',
                subtitle: 'Đi vòng quanh đôi giày',
                color: AppTheme.orange,
              ),
              const SizedBox(height: 12),
              const _WalkAroundVisualizer(),
              const SizedBox(height: 14),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  _visualChip('⏱️ Quay chừng 45 giây', AppTheme.orange),
                  _visualChip('📏 Cách giày 1 sải tay (~50cm)', AppTheme.statusCompleted),
                  _visualChip('🔄 Đi chậm 1 vòng tròn', AppTheme.statusScanned),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                'Đặt đôi giày ở chỗ sáng sủa. Bạn chỉ cần cầm điện thoại ngang tầm giày và bước chầm chậm quanh giày 1 vòng.',
                style: AppTheme.bodyFont(
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.75),
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // BƯỚC 2: TRANG TRÍ MÁY TÍNH
        _DoubleBezelCard(
          isDark: isDark,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildStepHeader(
                number: '2',
                title: 'Dán Hình Trang Trí Trên Web',
                subtitle: 'Thêm sticker, chữ ký & màu sắc',
                color: AppTheme.statusCompleted,
              ),
              const SizedBox(height: 12),
              const _DecorateVisualizer(),
              const SizedBox(height: 14),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  _visualChip('💻 Mở trên máy tính cho rộng', AppTheme.statusCompleted),
                  _visualChip('⭐ Dán sticker & chữ ký', AppTheme.orange),
                  _visualChip('✨ Hình ôm sát vào giày ngay', AppTheme.statusScanned),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                'Mở trang web trên máy tính để dán những hình bạn thích, viết tên bạn lên gót giày, kéo to nhỏ tuỳ ý rất dễ dàng.',
                style: AppTheme.bodyFont(
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.75),
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // BƯỚC 3: GỬI CHO THỢ VẼ
        _DoubleBezelCard(
          isDark: isDark,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildStepHeader(
                number: '3',
                title: 'Gửi Cho Thợ Vẽ Lên Giày Thật',
                subtitle: 'Thợ nhìn mẫu xoay 360° vẽ ngoài đời',
                color: AppTheme.statusScanned,
              ),
              const SizedBox(height: 12),
              const _ArtisanPaintingVisualizer(),
              const SizedBox(height: 14),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  _visualChip('🔗 Thợ mở xem không cần tải app', AppTheme.statusScanned),
                  _visualChip('📐 Đúng vị trí từng centimet', AppTheme.orange),
                  _visualChip('🎨 Chuẩn màu bạn đã chọn', AppTheme.statusCompleted),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                'Gửi link xem mẫu cho thợ gia công. Thợ chỉ việc mở link trên điện thoại là xoay xem được mọi góc để vẽ y hệt ngoài đời.',
                style: AppTheme.bodyFont(
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.75),
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStepHeader({
    required String number,
    required String title,
    required String subtitle,
    required Color color,
  }) {
    return Row(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            shape: BoxShape.circle,
            border: Border.all(color: color.withValues(alpha: 0.4)),
          ),
          alignment: Alignment.center,
          child: Text(
            number,
            style: AppTheme.headingFont(
              fontSize: 15,
              fontWeight: FontWeight.w900,
              color: color,
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: AppTheme.headingFont(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.2,
                ),
              ),
              Text(
                subtitle,
                style: AppTheme.bodyFont(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _visualChip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Text(
        text,
        style: AppTheme.bodyFont(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}

// =============================================================================
// TAB 1: MẸO QUAY ĐẸP (DO'S & DON'TS CHO NGƯỜI DÙNG PHỔ THÔNG)
// =============================================================================

class _ScanRulesTab extends StatelessWidget {
  const _ScanRulesTab({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // MẸO NÊN LÀM
        _DoubleBezelCard(
          isDark: isDark,
          borderColor: AppTheme.statusScanned.withValues(alpha: 0.3),
          shellColor: AppTheme.statusScanned.withValues(alpha: 0.05),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppTheme.statusScanned.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.thumb_up_alt_outlined, color: AppTheme.statusScanned, size: 18),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'MẸO ĐỂ CÓ MẪU GIÀY ĐẸP',
                      style: AppTheme.headingFont(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.statusScanned,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _ruleRow(
                icon: Icons.wb_sunny_rounded,
                title: 'Nơi sáng sủa, thoáng đãng',
                detail: 'Quay vào ban ngày ở hiên nhà hoặc trong phòng bật đèn sáng đều.',
                color: AppTheme.statusScanned,
              ),
              const SizedBox(height: 10),
              _ruleRow(
                icon: Icons.directions_walk_rounded,
                title: 'Bước đi chầm chậm',
                detail: 'Cầm điện thoại thật chắc tay, đi từ tốn quanh giày 1 vòng trọn vẹn.',
                color: AppTheme.statusScanned,
              ),
              const SizedBox(height: 10),
              _ruleRow(
                icon: Icons.contrast_rounded,
                title: 'Đặt trên nền sàn sạch, dễ nhìn',
                detail: 'Giày trắng nên để trên sàn gỗ hoặc thảm tối màu để thấy rõ mép giày.',
                color: AppTheme.statusScanned,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // MẸO NÊN TRÁNH
        _DoubleBezelCard(
          isDark: isDark,
          borderColor: AppTheme.crimson.withValues(alpha: 0.3),
          shellColor: AppTheme.crimson.withValues(alpha: 0.05),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppTheme.crimson.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.warning_amber_rounded, color: AppTheme.crimson, size: 18),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'NHỮNG ĐIỀU NÊN TRÁNH',
                      style: AppTheme.headingFont(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.crimson,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _ruleRow(
                icon: Icons.flash_off_rounded,
                title: 'Không bật đèn flash chói mắt',
                detail: 'Đèn flash rọi 1 điểm làm chói lóa và mất hết đường nét mũi giày.',
                color: AppTheme.crimson,
              ),
              const SizedBox(height: 10),
              _ruleRow(
                icon: Icons.speed_rounded,
                title: 'Không đi quá nhanh làm rung máy',
                detail: 'Nếu bạn lia máy vội vàng, video sẽ bị mờ nhòe không rõ chi tiết.',
                color: AppTheme.crimson,
              ),
              const SizedBox(height: 10),
              _ruleRow(
                icon: Icons.auto_fix_high_rounded,
                title: 'Hạn chế giày quá bóng gương',
                detail: 'Chất liệu da bóng loáng phản chiếu ánh sáng sẽ làm mờ hình ảnh.',
                color: AppTheme.crimson,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _ruleRow({
    required IconData icon,
    required String title,
    required String detail,
    required Color color,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: AppTheme.headingFont(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                detail,
                style: AppTheme.bodyFont(
                  fontSize: 12,
                  color: Colors.grey.shade400,
                  height: 1.3,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// =============================================================================
// TAB 2: GỬI THỢ VẼ (KẾT NỐI VỚI NGHỆ NHÂN NGOÀI ĐỜI)
// =============================================================================

class _ArtisanHandoverTab extends StatelessWidget {
  const _ArtisanHandoverTab({super.key});

  Future<void> _openWebStudio(BuildContext context) async {
    const url = AppConfig.webAppUrl;
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    final messenger = ScaffoldMessenger.of(context);
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Không thể mở $url')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Column(
      children: [
        _DoubleBezelCard(
          isDark: isDark,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.orange.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(Icons.handshake_rounded, color: AppTheme.orange, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'ĐƯA THIẾT KẾ RA GIÀY THẬT',
                          style: AppTheme.headingFont(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.5,
                          ),
                        ),
                        Text(
                          'Biến ý tưởng trên màn hình thành đôi giày thực tế',
                          style: AppTheme.bodyFont(
                            fontSize: 12,
                            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.65),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              _flowStepItem(
                step: '1',
                title: 'Bấm Lấy Link Mẫu Giày',
                desc: 'Sau khi trang trí xong, bạn bấm tạo link chia sẻ ngay trong dự án của mình.',
                icon: Icons.link_rounded,
              ),
              const SizedBox(height: 12),
              _flowStepItem(
                step: '2',
                title: 'Gửi Cho Tiệm Vẽ Hoặc Thợ Bạn Chọn',
                desc: 'Gửi link qua Zalo hoặc Messenger. Thợ bấm vào là xem được ngay trên điện thoại.',
                icon: Icons.send_rounded,
              ),
              const SizedBox(height: 12),
              _flowStepItem(
                step: '3',
                title: 'Thợ Xoay 360° Để Vẽ Y Hệt',
                desc: 'Thợ có thể phóng to, xoay tròn xem màu sắc và vị trí để vẽ tay lên giày thật của bạn.',
                icon: Icons.palette_rounded,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // CTA Card
        _DoubleBezelCard(
          isDark: isDark,
          borderColor: AppTheme.orange.withValues(alpha: 0.35),
          shellColor: AppTheme.orange.withValues(alpha: 0.06),
          child: Column(
            children: [
              Text(
                'BẮT ĐẦU TRANG TRÍ GIÀY',
                style: AppTheme.headingFont(
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.orange,
                  letterSpacing: 0.8,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Bạn muốn thử dán sticker lên giày ngay bây giờ? Mở Kus Studio trên máy tính để bắt đầu sáng tạo!',
                textAlign: TextAlign.center,
                style: AppTheme.bodyFont(
                  fontSize: 13,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.75),
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => _openWebStudio(context),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.orange,
                    foregroundColor: Colors.white,
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                    shape: RoundedRectangleAppPill(),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Flexible(
                        child: Text(
                          'Thử Trang Trí Giày Ngay',
                          overflow: TextOverflow.ellipsis,
                          style: AppTheme.headingFont(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        width: 26,
                        height: 26,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.22),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.arrow_outward_rounded, size: 14, color: Colors.white),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _flowStepItem({
    required String step,
    required String title,
    required String desc,
    required IconData icon,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
            color: AppTheme.orange.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppTheme.orange.withValues(alpha: 0.3)),
          ),
          alignment: Alignment.center,
          child: Text(
            step,
            style: AppTheme.headingFont(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: AppTheme.orange,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, size: 15, color: AppTheme.orange),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      title,
                      style: AppTheme.headingFont(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 2),
              Text(
                desc,
                style: AppTheme.bodyFont(
                  fontSize: 12,
                  color: Colors.grey.shade400,
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// =============================================================================
// REUSABLE DOUBLE-BEZEL CONTAINER
// =============================================================================

class _DoubleBezelCard extends StatelessWidget {
  const _DoubleBezelCard({
    required this.child,
    required this.isDark,
    this.borderColor,
    this.shellColor,
  });

  final Widget child;
  final bool isDark;
  final Color? borderColor;
  final Color? shellColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: shellColor ??
            (isDark ? Colors.white.withValues(alpha: 0.04) : Colors.black.withValues(alpha: 0.03)),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: borderColor ??
              (isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06)),
        ),
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isDark ? AppTheme.darkCard : Colors.white,
          borderRadius: BorderRadius.circular(18),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: isDark ? 0.35 : 0.04),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: child,
      ),
    );
  }
}

class RoundedRectangleAppPill extends RoundedRectangleBorder {
  RoundedRectangleAppPill() : super(borderRadius: BorderRadius.circular(999));
}

// =============================================================================
// HÌNH ẢNH 1: QUAY TRÒN QUANH GIÀY (CỰC KỲ DỄ HIỂU)
// =============================================================================

class _WalkAroundVisualizer extends StatelessWidget {
  const _WalkAroundVisualizer();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 120,
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFF0D0D11),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: const Size(double.infinity, 120),
            painter: _WalkAroundPainter(),
          ),
          // Giày ở giữa
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.orange.withValues(alpha: 0.15),
              shape: BoxShape.circle,
              border: Border.all(color: AppTheme.orange.withValues(alpha: 0.4)),
            ),
            child: const Icon(Icons.roller_skating_outlined, color: AppTheme.orange, size: 28),
          ),
          // Tag hướng dẫn dễ hiểu
          Positioned(
            top: 8,
            left: 12,
            child: _diagramBadge('BƯỚC ĐI VÒNG QUANH GIÀY', AppTheme.orange),
          ),
          Positioned(
            bottom: 8,
            right: 12,
            child: _diagramBadge('KHOẢNG CÁCH: 1 SẢI TAY', AppTheme.statusCompleted),
          ),
        ],
      ),
    );
  }

  Widget _diagramBadge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.65),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        label,
        style: AppTheme.bodyFont(
          fontSize: 9,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}

class _WalkAroundPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width / 2 - 28, 42.0);

    // Đường đi vòng tròn
    final trackPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.15)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8;

    canvas.drawOval(
      Rect.fromCenter(center: center, width: radius * 3.2, height: radius * 1.9),
      trackPaint,
    );

    // Vị trí điện thoại đang quay ở góc 35 độ
    const angle = 0.6; // radians
    final phoneX = center.dx + (radius * 1.6) * math.cos(angle);
    final phoneY = center.dy + (radius * 0.95) * math.sin(angle);

    // Vẽ biểu tượng điện thoại nhỏ
    final phoneBg = Paint()..color = AppTheme.orange;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(phoneX, phoneY), width: 14, height: 20),
        const Radius.circular(3),
      ),
      phoneBg,
    );

    // Tia nhìn từ camera hướng về phía chiếc giày
    final rayPaint = Paint()
      ..color = AppTheme.orange.withValues(alpha: 0.45)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    canvas.drawLine(Offset(phoneX, phoneY), center, rayPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// =============================================================================
// HÌNH ẢNH 2: TRANG TRÍ MÁY TÍNH (DÁN STICKER & CHỮ KÝ)
// =============================================================================

class _DecorateVisualizer extends StatelessWidget {
  const _DecorateVisualizer();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 110,
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFF0D0D11),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Màn hình Studio & Giày ở giữa
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: AppTheme.statusCompleted.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.statusCompleted.withValues(alpha: 0.4)),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.laptop_mac_rounded, color: AppTheme.statusCompleted, size: 24),
                SizedBox(width: 8),
                Icon(Icons.roller_skating_outlined, color: Colors.white, size: 22),
              ],
            ),
          ),
          // Sticker bay quanh
          Positioned(
            top: 10,
            right: 18,
            child: _floatingSticker('⭐ Sao', AppTheme.orange),
          ),
          Positioned(
            bottom: 10,
            left: 18,
            child: _floatingSticker('✍️ Tên bạn', AppTheme.crimson),
          ),
          Positioned(
            top: 8,
            left: 12,
            child: _diagramBadge('KÉO THẢ STICKER', AppTheme.statusCompleted),
          ),
          Positioned(
            bottom: 8,
            right: 12,
            child: _diagramBadge('CHỌN MÀU TÙY Ý', AppTheme.orange),
          ),
        ],
      ),
    );
  }

  Widget _floatingSticker(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(
        text,
        style: AppTheme.bodyFont(
          fontSize: 9,
          fontWeight: FontWeight.w800,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _diagramBadge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        label,
        style: AppTheme.bodyFont(
          fontSize: 8.5,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}

// =============================================================================
// HÌNH ẢNH 3: GIAO THỢ VẼ (XEM 3D TRÊN ĐIỆN THOẠI & VẼ GIÀY THẬT)
// =============================================================================

class _ArtisanPaintingVisualizer extends StatelessWidget {
  const _ArtisanPaintingVisualizer();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 110,
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFF0D0D11),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Center flow: Phone (3D) -> Arrow -> Brush (Giày thật)
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Phone with 3D model
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.statusScanned.withValues(alpha: 0.4)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.smartphone_rounded, color: AppTheme.statusScanned, size: 20),
                    const SizedBox(width: 4),
                    Text(
                      '3D',
                      style: AppTheme.bodyFont(
                        fontSize: 10,
                        fontWeight: FontWeight.w900,
                        color: AppTheme.statusScanned,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 14),
              const Icon(Icons.arrow_forward_rounded, color: Colors.grey, size: 18),
              const SizedBox(width: 14),
              // Paintbrush + Real Shoe
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: AppTheme.orange.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.orange.withValues(alpha: 0.4)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.brush_rounded, color: AppTheme.orange, size: 20),
                    const SizedBox(width: 6),
                    Text(
                      'VẼ THẬT',
                      style: AppTheme.bodyFont(
                        fontSize: 10,
                        fontWeight: FontWeight.w900,
                        color: AppTheme.orange,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          Positioned(
            top: 8,
            left: 12,
            child: _diagramBadge('GỬI LINK QUA ZALO/MESSENGER', AppTheme.statusScanned),
          ),
          Positioned(
            bottom: 8,
            right: 12,
            child: _diagramBadge('XOAY 360° ĐỂ VẼ CHUẨN', AppTheme.orange),
          ),
        ],
      ),
    );
  }

  Widget _diagramBadge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        label,
        style: AppTheme.bodyFont(
          fontSize: 8.5,
          fontWeight: FontWeight.w700,
          color: color,
        ),
      ),
    );
  }
}
