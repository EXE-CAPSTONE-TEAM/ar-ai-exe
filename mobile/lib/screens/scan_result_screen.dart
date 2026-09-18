import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../app/app_theme.dart';

class ScanResultScreen extends StatelessWidget {
  const ScanResultScreen({
    required this.scanSessionId,
    required this.status,
    required this.processingStarted,
    required this.webDesignUrl,
    this.isGuest = false,
    super.key,
  });

  final String scanSessionId;
  final String status;
  final bool processingStarted;
  final String webDesignUrl;
  final bool isGuest;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isDone = status == 'completed' || status == 'ready' || processingStarted;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'AFTERSACN · DỰNG LƯỚI 3D',
          style: AppTheme.monoFont(
            fontSize: 14,
            letterSpacing: 1.2,
            color: AppTheme.orange,
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Checklist Progress Section (SRS v2.2 SC-23)
                    Container(
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: isDark ? AppTheme.darkCard : Colors.white,
                        borderRadius: BorderRadius.circular(22),
                        border: Border.all(
                          color: isDark ? AppTheme.darkCardBorder : const Color(0x18000000),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                'CHECKLIST TIẾN TRÌNH AI (SC-23)',
                                style: AppTheme.monoFont(
                                  fontSize: 11,
                                  color: AppTheme.orange,
                                  letterSpacing: 1.2,
                                ),
                              ),
                              const Spacer(),
                              _StatusBadge(status: status, isProcessing: processingStarted),
                            ],
                          ),
                          const SizedBox(height: 16),
                          _ChecklistRow(
                            title: '1. Đã tải lên video/ảnh 360°',
                            done: true,
                            isDark: isDark,
                          ),
                          const SizedBox(height: 10),
                          _ChecklistRow(
                            title: '2. AI tái tạo điểm & tạo lưới 3D',
                            done: isDone,
                            isDark: isDark,
                          ),
                          const SizedBox(height: 10),
                          _ChecklistRow(
                            title: '3. Nén GLB & chuẩn hóa phôi Kus Studio',
                            done: isDone,
                            isDark: isDark,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),

                    // 3D Model Preview Card
                    AspectRatio(
                      aspectRatio: 1.35,
                      child: Container(
                        decoration: BoxDecoration(
                          color: isDark ? const Color(0xFF101014) : const Color(0xFFF3F1EC),
                          borderRadius: BorderRadius.circular(22),
                          border: Border.all(
                            color: AppTheme.orange.withValues(alpha: 0.35),
                          ),
                        ),
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.view_in_ar,
                                  size: 54,
                                  color: AppTheme.orange.withValues(alpha: 0.85),
                                ),
                                const SizedBox(height: 10),
                                Text(
                                  'MÔ HÌNH 3D ĐÃ SẴN SÀNG',
                                  style: AppTheme.headingFont(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Định dạng GLB chuẩn · Tương thích Web & Mobile',
                                  style: AppTheme.bodyFont(
                                    fontSize: 12,
                                    color: Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                            Positioned(
                              top: 12,
                              left: 14,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: AppTheme.statusScanned.withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  'PREVIEW READY',
                                  style: AppTheme.monoFont(
                                    fontSize: 10,
                                    color: AppTheme.statusScanned,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // Session Info
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: isDark ? AppTheme.darkSurface : Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.white12),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'MÃ PHIÊN QUÉT (SCAN ID)',
                                  style: AppTheme.monoFont(fontSize: 10, color: Colors.grey),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  scanSessionId,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: AppTheme.monoFont(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            onPressed: () => _copyScanId(context),
                            icon: const Icon(Icons.copy, size: 18, color: AppTheme.orange),
                            tooltip: 'Copy ID',
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),

                    // Guest conversion notice (BR-41)
                    if (isGuest) ...[
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppTheme.orange.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: AppTheme.orange.withValues(alpha: 0.35)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.info_outline, color: AppTheme.orange, size: 20),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                'Bạn đang ở Chế độ Khách. Đăng ký tài khoản để lưu mô hình này vĩnh viễn vào dự án của bạn (BR-41).',
                                style: AppTheme.bodyFont(fontSize: 12.5),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                    ],

                    // Action Buttons
                    FilledButton.icon(
                      onPressed: () => _openDesignUrl(context),
                      icon: const Icon(Icons.open_in_browser),
                      label: const Text('MỞ TRÊN KUS STUDIO (WEB / DESKTOP)'),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: () => _showExportSheet(context),
                      icon: const Icon(Icons.download_for_offline_outlined),
                      label: const Text('XUẤT FILE SCAN GỐC (GLB - BR-42)'),
                    ),
                    const SizedBox(height: 8),
                    Center(
                      child: TextButton.icon(
                        onPressed: () => _copyDesignUrl(context),
                        icon: const Icon(Icons.link, size: 16),
                        label: const Text('Sao chép liên kết dự án Web'),
                        style: TextButton.styleFrom(
                          foregroundColor: Colors.grey,
                          textStyle: AppTheme.monoFont(fontSize: 11),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
              child: SizedBox(
                width: double.infinity,
                child: TextButton.icon(
                  onPressed: () =>
                      Navigator.of(context).popUntil((route) => route.isFirst),
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: const Text('QUÉT ĐÔI GIÀY KHÁC'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.orange,
                    textStyle: AppTheme.headingFont(fontSize: 14, fontWeight: FontWeight.w800),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showExportSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkCard,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.check_circle, color: AppTheme.statusScanned),
                const SizedBox(width: 10),
                Text(
                  'XUẤT FILE SCAN GỐC (GLB)',
                  style: AppTheme.headingFont(fontSize: 16, fontWeight: FontWeight.w800),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Theo BR-42 (SRS v2.2), gói Basic trở lên được quyền xuất trực tiếp file scan gốc GLB sạch (đã qua MeshCleanupService) để lưu trữ hoặc nạp vào phần mềm 3D khác.',
              style: AppTheme.bodyFont(fontSize: 13, color: Colors.white70, height: 1.4),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: () {
                Navigator.of(ctx).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Đang chuẩn bị tải xuống file GLB...')),
                );
              },
              icon: const Icon(Icons.file_download),
              label: const Text('TẢI FILE SHOE_PREVIEW.GLB'),
            ),
            const SizedBox(height: 10),
            OutlinedButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('ĐÓNG'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openDesignUrl(BuildContext context) async {
    final uri = Uri.parse(webDesignUrl);
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Không thể mở liên kết trình duyệt.')),
      );
    }
  }

  Future<void> _copyDesignUrl(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: webDesignUrl));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã sao chép liên kết thiết kế.')),
      );
    }
  }

  Future<void> _copyScanId(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: scanSessionId));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã sao chép mã phiên quét.')),
      );
    }
  }
}

class _ChecklistRow extends StatelessWidget {
  const _ChecklistRow({
    required this.title,
    required this.done,
    required this.isDark,
  });

  final String title;
  final bool done;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: done ? AppTheme.statusScanned : Colors.grey.withValues(alpha: 0.3),
          ),
          child: Icon(
            done ? Icons.check : Icons.hourglass_empty,
            size: 14,
            color: done ? Colors.black : Colors.white,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            style: AppTheme.bodyFont(
              fontSize: 13.5,
              fontWeight: done ? FontWeight.w600 : FontWeight.w400,
              color: done
                  ? (isDark ? Colors.white : Colors.black)
                  : Colors.grey,
            ),
          ),
        ),
      ],
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status, required this.isProcessing});

  final String status;
  final bool isProcessing;

  @override
  Widget build(BuildContext context) {
    final color = isProcessing ? AppTheme.statusProcessing : AppTheme.statusScanned;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        isProcessing ? 'ĐANG DỰNG LƯỚI' : 'SẴN SÀNG',
        style: AppTheme.monoFont(
          fontSize: 10,
          color: color,
        ),
      ),
    );
  }
}
