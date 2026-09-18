import 'package:flutter/material.dart';

import '../app/app_theme.dart';

class ScanGuideOverlay extends StatelessWidget {
  const ScanGuideOverlay({
    required this.seconds,
    required this.isRecording,
    required this.passTitle,
    required this.idleInstruction,
    required this.recordingInstruction,
    super.key,
  });

  final int seconds;
  final bool isRecording;
  final String passTitle;
  final String idleInstruction;
  final String recordingInstruction;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: CustomPaint(
        painter: _GuidePainter(isRecording: isRecording, seconds: seconds),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DecoratedBox(
                decoration: BoxDecoration(
                  color: const Color(0xDC0A0A0C),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: AppTheme.darkCardBorderHover),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.orange.withValues(alpha: 0.15),
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
                              color: isRecording ? AppTheme.crimson : AppTheme.statusScanned,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            passTitle.toUpperCase(),
                            style: AppTheme.headingFont(
                              fontSize: 14,
                              fontWeight: FontWeight.w800,
                              color: AppTheme.orange,
                              letterSpacing: 1.2,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        isRecording
                            ? '$recordingInstruction ($seconds giây / khuyến nghị 30-60s)'
                            : '$idleInstruction Khuyến nghị quay: 30-60 giây.',
                        style: AppTheme.bodyFont(
                          fontSize: 13,
                          color: Colors.white,
                        ),
                        textAlign: TextAlign.center,
                      ),
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
  const _GuidePainter({required this.isRecording, required this.seconds});

  final bool isRecording;
  final int seconds;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height * 0.48),
      width: size.width * 0.84,
      height: size.height * 0.46,
    );

    // Bounding Oval for shoe
    final paint = Paint()
      ..color = isRecording ? AppTheme.orange : AppTheme.orange.withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = isRecording ? 2.5 : 1.8;

    canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(24)), paint);

    // Corner targeting HUD brackets
    final bracketPaint = Paint()
      ..color = AppTheme.orange
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
      ..color = AppTheme.orange.withValues(alpha: 0.5)
      ..strokeWidth = 1.2;
    final c = rect.center;
    canvas.drawLine(Offset(c.dx - 12, c.dy), Offset(c.dx + 12, c.dy), chPaint);
    canvas.drawLine(Offset(c.dx, c.dy - 12), Offset(c.dx, c.dy + 12), chPaint);
  }

  @override
  bool shouldRepaint(covariant _GuidePainter oldDelegate) =>
      oldDelegate.isRecording != isRecording || oldDelegate.seconds != seconds;
}
