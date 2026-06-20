import 'package:flutter/material.dart';

import '../app/app_theme.dart';

class ScanHeroCard extends StatelessWidget {
  const ScanHeroCard({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return AspectRatio(
      aspectRatio: 0.76,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF101010) : const Color(0xFFFFF4ED),
          borderRadius: BorderRadius.circular(26),
          border: Border.all(
            color: isDark ? const Color(0xFF2A2A2A) : const Color(0xFFFFC5AC),
            width: 1.4,
          ),
        ),
        child: Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(painter: _ScanFramePainter(isDark: isDark)),
            ),
            Align(
              alignment: const Alignment(0, -0.82),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xE60C0C0C) : Colors.white,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: isDark
                        ? const Color(0xFF444444)
                        : const Color(0xFFFFC5AC),
                    width: 1.6,
                  ),
                ),
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
                  child: Text(
                    'Align your shoe inside the frame\nand rotate 360°',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          height: 1.35,
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
              ),
            ),
            Positioned(
              left: 20,
              right: 20,
              bottom: 20,
              child: Row(
                children: [
                  const CircleAvatar(
                      radius: 6, backgroundColor: AppTheme.orange),
                  const SizedBox(width: 9),
                  Text(
                    'LIVE · DEPTH ON',
                    style: TextStyle(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withValues(alpha: 0.64),
                      letterSpacing: 2,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '1080P · 60FPS',
                    style: TextStyle(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withValues(alpha: 0.64),
                      letterSpacing: 2,
                      fontWeight: FontWeight.w700,
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

class _ScanFramePainter extends CustomPainter {
  const _ScanFramePainter({required this.isDark});

  final bool isDark;

  @override
  void paint(Canvas canvas, Size size) {
    final bg = Rect.fromLTWH(0, 0, size.width, size.height);
    final wash = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: isDark
            ? [
                const Color(0xFF3A1B12).withValues(alpha: 0.52),
                const Color(0xFF111111).withValues(alpha: 0.1),
                const Color(0xFF090909).withValues(alpha: 0.72),
              ]
            : [
                const Color(0xFFFFD8C8).withValues(alpha: 0.9),
                const Color(0xFFFFFFFF).withValues(alpha: 0.4),
                const Color(0xFFFFF2EA).withValues(alpha: 0.8),
              ],
      ).createShader(bg);
    canvas.drawRect(bg, wash);

    final gridPaint = Paint()
      ..color = (isDark ? Colors.white : Colors.black)
          .withValues(alpha: isDark ? 0.055 : 0.05)
      ..strokeWidth = 1;
    for (var x = 0.0; x < size.width; x += 28) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (var y = 0.0; y < size.height; y += 28) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final horizon = Paint()
      ..shader = LinearGradient(
        colors: [
          AppTheme.orange.withValues(alpha: 0),
          AppTheme.orange.withValues(alpha: 0.75),
          AppTheme.orange.withValues(alpha: 0),
        ],
      ).createShader(Rect.fromLTWH(20, size.height * 0.68, size.width - 40, 4))
      ..strokeWidth = 2;
    canvas.drawLine(
      Offset(24, size.height * 0.68),
      Offset(size.width - 24, size.height * 0.68),
      horizon,
    );

    _drawCorners(canvas, size);
    _drawFoot(canvas, size);

    final center = Paint()..color = AppTheme.orange.withValues(alpha: 0.85);
    canvas.drawCircle(Offset(size.width * 0.5, size.height * 0.52), 6, center);
  }

  void _drawCorners(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppTheme.orange
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.2
      ..strokeCap = StrokeCap.square;
    const inset = 22.0;
    const len = 22.0;
    const radius = 18.0;

    final path = Path()
      ..moveTo(inset, inset + len)
      ..lineTo(inset, inset + radius)
      ..quadraticBezierTo(inset, inset, inset + radius, inset)
      ..lineTo(inset + len, inset)
      ..moveTo(size.width - inset - len, inset)
      ..lineTo(size.width - inset - radius, inset)
      ..quadraticBezierTo(
          size.width - inset, inset, size.width - inset, inset + radius)
      ..lineTo(size.width - inset, inset + len)
      ..moveTo(inset, size.height - inset - len)
      ..lineTo(inset, size.height - inset - radius)
      ..quadraticBezierTo(
          inset, size.height - inset, inset + radius, size.height - inset)
      ..lineTo(inset + len, size.height - inset)
      ..moveTo(size.width - inset - len, size.height - inset)
      ..lineTo(size.width - inset - radius, size.height - inset)
      ..quadraticBezierTo(
        size.width - inset,
        size.height - inset,
        size.width - inset,
        size.height - inset - radius,
      )
      ..lineTo(size.width - inset, size.height - inset - len);
    canvas.drawPath(path, paint);
  }

  void _drawFoot(Canvas canvas, Size size) {
    final foot = Path()
      ..moveTo(size.width * 0.43, size.height * 0.79)
      ..cubicTo(size.width * 0.35, size.height * 0.68, size.width * 0.34,
          size.height * 0.44, size.width * 0.36, size.height * 0.33)
      ..cubicTo(size.width * 0.39, size.height * 0.20, size.width * 0.48,
          size.height * 0.20, size.width * 0.56, size.height * 0.22)
      ..cubicTo(size.width * 0.67, size.height * 0.27, size.width * 0.68,
          size.height * 0.45, size.width * 0.70, size.height * 0.62)
      ..cubicTo(size.width * 0.72, size.height * 0.80, size.width * 0.61,
          size.height * 0.86, size.width * 0.50, size.height * 0.84)
      ..cubicTo(size.width * 0.47, size.height * 0.83, size.width * 0.45,
          size.height * 0.82, size.width * 0.43, size.height * 0.79);

    final paint = Paint()
      ..color = AppTheme.orange.withValues(alpha: 0.72)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.5
      ..strokeCap = StrokeCap.round;

    for (final metric in foot.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final segment = metric.extractPath(distance, distance + 8);
        canvas.drawPath(segment, paint);
        distance += 16;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _ScanFramePainter oldDelegate) =>
      oldDelegate.isDark != isDark;
}
