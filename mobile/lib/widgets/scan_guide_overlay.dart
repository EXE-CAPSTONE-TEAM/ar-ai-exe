import 'package:flutter/material.dart';

import '../app/app_theme.dart';

class ScanGuideOverlay extends StatelessWidget {
  const ScanGuideOverlay({
    required this.seconds,
    required this.isRecording,
    this.passTitle = 'Quét 360° liên tục',
    this.idleInstruction = 'Xoay 2 tầng quanh đôi giày trong 45 giây.',
    this.recordingInstruction = 'Đi chậm quanh thân giày, giữ giày trong khung.',
    this.tierSwitchSeconds = 20,
    super.key,
  });

  final int seconds;
  final bool isRecording;
  final String passTitle;
  final String idleInstruction;
  final String recordingInstruction;
  final int tierSwitchSeconds;

  bool get isTier2 => isRecording && seconds >= tierSwitchSeconds;

  @override
  Widget build(BuildContext context) {
    final activeTitle = isRecording
        ? (isTier2 ? 'TẦNG 2: NGHIÊNG 45° TRÊN XUỐNG' : 'TẦNG 1: NGANG THÂN GIÀY')
        : passTitle.toUpperCase();

    final activeInstruction = isRecording
        ? (isTier2
            ? 'Nâng máy góc nghiêng 45° từ trên xuống, quay tiếp mũi & dây giày ($seconds / 45s)'
            : 'Giữ máy ngang tầm thân giày, bước chậm 1 vòng 360° ($seconds / ${tierSwitchSeconds}s)')
        : '$idleInstruction\n• 0-20s: Ngang thân giày\n• 20-45s: Nghiêng 45° từ trên xuống (Máy sẽ rung khi chuyển tầng)';

    return IgnorePointer(
      child: CustomPaint(
        painter: _GuidePainter(
          isRecording: isRecording,
          seconds: seconds,
          isTier2: isTier2,
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DecoratedBox(
                decoration: BoxDecoration(
                  color: const Color(0xDC0A0A0C),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: isTier2 ? const Color(0xFF38BDF8) : AppTheme.darkCardBorderHover,
                    width: isTier2 ? 1.5 : 1.0,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: (isTier2 ? const Color(0xFF38BDF8) : AppTheme.orange).withValues(alpha: 0.2),
                      blurRadius: 18,
                    ),
                  ],
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: isRecording
                                  ? (isTier2 ? const Color(0xFF38BDF8) : AppTheme.crimson)
                                  : AppTheme.statusScanned,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            activeTitle,
                            style: AppTheme.headingFont(
                              fontSize: 13,
                              fontWeight: FontWeight.w800,
                              color: isTier2 ? const Color(0xFF38BDF8) : AppTheme.orange,
                              letterSpacing: 1.1,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        activeInstruction,
                        style: AppTheme.bodyFont(
                          fontSize: 12.5,
                          color: Colors.white,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      if (isRecording) ...[
                        const SizedBox(height: 10),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: (seconds / 45.0).clamp(0.0, 1.0),
                            backgroundColor: Colors.white12,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              isTier2 ? const Color(0xFF38BDF8) : AppTheme.orange,
                            ),
                            minHeight: 4,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
    );
  }
}

class _GuidePainter extends CustomPainter {
  const _GuidePainter({
    required this.isRecording,
    required this.seconds,
    this.isTier2 = false,
  });

  final bool isRecording;
  final int seconds;
  final bool isTier2;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height * (isTier2 ? 0.44 : 0.48)),
      width: size.width * 0.84,
      height: size.height * (isTier2 ? 0.40 : 0.46),
    );

    final activeColor = isTier2 ? const Color(0xFF38BDF8) : AppTheme.orange;

    // Bounding Oval for shoe
    final paint = Paint()
      ..color = isRecording ? activeColor : activeColor.withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = isRecording ? 2.5 : 1.8;

    canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(24)), paint);

    // Corner targeting HUD brackets
    final bracketPaint = Paint()
      ..color = activeColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.5
      ..strokeCap = StrokeCap.square;

    const bLen = 22.0;
    // Top-Left
    canvas.drawLine(Offset(rect.left, rect.top + bLen), Offset(rect.left, rect.top), bracketPaint);
    canvas.drawLine(Offset(rect.left, rect.top), Offset(rect.left + bLen, rect.top), bracketPaint);
    // Top-Right
    canvas.drawLine(Offset(rect.right - bLen, rect.top), Offset(rect.right, rect.top), bracketPaint);
    canvas.drawLine(Offset(rect.right, rect.top), Offset(rect.right, rect.top + bLen), bracketPaint);
    // Bottom-Left
    canvas.drawLine(Offset(rect.left, rect.bottom - bLen), Offset(rect.left, rect.bottom), bracketPaint);
    canvas.drawLine(Offset(rect.left, rect.bottom), Offset(rect.left + bLen, rect.bottom), bracketPaint);
    // Bottom-Right
    canvas.drawLine(Offset(rect.right - bLen, rect.bottom), Offset(rect.right, rect.bottom), bracketPaint);
    canvas.drawLine(Offset(rect.right, rect.bottom), Offset(rect.right, rect.bottom - bLen), bracketPaint);

    // Center crosshair
    final chPaint = Paint()
      ..color = activeColor.withValues(alpha: 0.5)
      ..strokeWidth = 1.2;
    final c = rect.center;
    canvas.drawLine(Offset(c.dx - 12, c.dy), Offset(c.dx + 12, c.dy), chPaint);
    canvas.drawLine(Offset(c.dx, c.dy - 12), Offset(c.dx, c.dy + 12), chPaint);

    // If Tier 2, draw 45-degree angle guide arrow or marker
    if (isTier2) {
      final angleGuidePaint = Paint()
        ..color = const Color(0xFF38BDF8).withValues(alpha: 0.7)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5;
      // Draw top-down angle guide indicator lines
      canvas.drawLine(
        Offset(rect.left + 24, rect.top - 12),
        Offset(rect.left + 48, rect.top + 12),
        angleGuidePaint,
      );
      canvas.drawLine(
        Offset(rect.right - 24, rect.top - 12),
        Offset(rect.right - 48, rect.top + 12),
        angleGuidePaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _GuidePainter oldDelegate) =>
      oldDelegate.isRecording != isRecording ||
      oldDelegate.seconds != seconds ||
      oldDelegate.isTier2 != isTier2;
}
