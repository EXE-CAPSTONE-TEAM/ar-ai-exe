import 'package:flutter/material.dart';

import '../app/app_theme.dart';

class ScanHeroCard extends StatelessWidget {
  const ScanHeroCard({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return AspectRatio(
      aspectRatio: 0.84,
      child: Container(
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: isDark ? const Color(0x15FFFFFF) : const Color(0x12FF5A36),
          borderRadius: BorderRadius.circular(30),
          border: Border.all(
            color: isDark ? const Color(0x22FFFFFF) : const Color(0x28FF5A36),
            width: 1.0,
          ),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(26),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: isDark ? AppTheme.darkCard : const Color(0xFFFFF6F0),
              borderRadius: BorderRadius.circular(26),
              border: Border.all(
                color: isDark ? AppTheme.darkCardBorder : const Color(0xFFFFD0BC),
                width: 1.2,
              ),
              boxShadow: [
                BoxShadow(
                  color: isDark
                      ? Colors.black.withValues(alpha: 0.5)
                      : AppTheme.orange.withValues(alpha: 0.08),
                  blurRadius: 24,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Stack(
              children: [
                Positioned.fill(
                  child: CustomPaint(painter: _ScanFramePainter(isDark: isDark)),
                ),
                Align(
                  alignment: const Alignment(0, -0.80),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xEE0A0A0C) : Colors.white,
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(
                        color: isDark
                            ? const Color(0x44FF5A36)
                            : const Color(0xFFFFC5AC),
                        width: 1.2,
                      ),
                      boxShadow: [
                        if (isDark)
                          BoxShadow(
                            color: AppTheme.orange.withValues(alpha: 0.12),
                            blurRadius: 16,
                          ),
                      ],
                    ),
                    child: Padding(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: Text(
                        'HƯỚNG CAMERA VÀO GIÀY · 360°',
                        textAlign: TextAlign.center,
                        style: AppTheme.headingFont(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.1,
                          color: isDark ? Colors.white : Colors.black,
                        ),
                      ),
                    ),
                  ),
                ),
                Positioned(
                  left: 16,
                  right: 16,
                  bottom: 14,
                  child: Row(
                    children: [
                      const CircleAvatar(
                          radius: 4, backgroundColor: AppTheme.statusScanned),
                      const SizedBox(width: 7),
                      Text(
                        'RADAR 360° · AI SENSING',
                        style: AppTheme.monoFont(
                          fontSize: 10,
                          color: Theme.of(context)
                              .colorScheme
                              .onSurface
                              .withValues(alpha: 0.65),
                          letterSpacing: 1.2,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        '720P / 1080P',
                        style: AppTheme.monoFont(
                          fontSize: 10,
                          color: Theme.of(context)
                              .colorScheme
                              .onSurface
                              .withValues(alpha: 0.65),
                          letterSpacing: 1.2,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
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
    _draw360OrbitRing(canvas, size);
    _drawSneakerContour(canvas, size);

    final center = Paint()..color = AppTheme.orange.withValues(alpha: 0.9);
    canvas.drawCircle(Offset(size.width * 0.5, size.height * 0.50), 4.5, center);
  }

  void _drawCorners(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppTheme.orange
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.8
      ..strokeCap = StrokeCap.square;
    const inset = 18.0;
    const len = 20.0;
    const radius = 14.0;

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

  void _draw360OrbitRing(Canvas canvas, Size size) {
    final center = Offset(size.width * 0.5, size.height * 0.53);
    final rect = Rect.fromCenter(
      center: center,
      width: size.width * 0.82,
      height: size.height * 0.44,
    );

    final orbitPaint = Paint()
      ..color = AppTheme.orange.withValues(alpha: 0.35)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;

    // Draw dashed elliptical orbit
    final ellipsePath = Path()..addOval(rect);
    for (final metric in ellipsePath.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final segment = metric.extractPath(distance, distance + 6);
        canvas.drawPath(segment, orbitPaint);
        distance += 14;
      }
    }

    // 4 Cardinal tick marks on the orbit
    final tickPaint = Paint()
      ..color = AppTheme.orange
      ..strokeWidth = 2.2;
    canvas.drawLine(
        Offset(center.dx, rect.top - 5), Offset(center.dx, rect.top + 5), tickPaint);
    canvas.drawLine(Offset(center.dx, rect.bottom - 5),
        Offset(center.dx, rect.bottom + 5), tickPaint);
    canvas.drawLine(Offset(rect.left - 5, center.dy),
        Offset(rect.left + 5, center.dy), tickPaint);
    canvas.drawLine(Offset(rect.right - 5, center.dy),
        Offset(rect.right + 5, center.dy), tickPaint);
  }

  void _drawSneakerContour(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Sneaker Profile Silhouette Path
    final sneaker = Path()
      // Heel bottom
      ..moveTo(w * 0.22, h * 0.58)
      // Sole baseline
      ..lineTo(w * 0.76, h * 0.58)
      // Toe spring curve
      ..cubicTo(w * 0.82, h * 0.56, w * 0.84, h * 0.51, w * 0.80, h * 0.46)
      // Toe box cap
      ..cubicTo(w * 0.75, h * 0.42, w * 0.68, h * 0.42, w * 0.62, h * 0.44)
      // Vamp & Eyestay up to collar
      ..lineTo(w * 0.47, h * 0.33)
      // Tongue & Ankle Collar
      ..cubicTo(w * 0.42, h * 0.32, w * 0.35, h * 0.33, w * 0.32, h * 0.38)
      // Heel collar down to counter
      ..cubicTo(w * 0.30, h * 0.42, w * 0.21, h * 0.47, w * 0.20, h * 0.53)
      // Back of heel to sole
      ..cubicTo(w * 0.19, h * 0.56, w * 0.20, h * 0.58, w * 0.22, h * 0.58);

    // Sole cushion accent line
    final soleAccent = Path()
      ..moveTo(w * 0.21, h * 0.60)
      ..lineTo(w * 0.77, h * 0.60)
      ..cubicTo(w * 0.80, h * 0.59, w * 0.81, h * 0.57, w * 0.78, h * 0.56)
      ..lineTo(w * 0.21, h * 0.56)
      ..close();

    final glowPaint = Paint()
      ..color = AppTheme.orange.withValues(alpha: 0.88)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.0
      ..strokeCap = StrokeCap.round;

    final fillSolePaint = Paint()
      ..color = AppTheme.orange.withValues(alpha: 0.16)
      ..style = PaintingStyle.fill;

    canvas.drawPath(soleAccent, fillSolePaint);

    // Render dashed sneaker contour
    for (final metric in sneaker.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final segment = metric.extractPath(distance, distance + 10);
        canvas.drawPath(segment, glowPaint);
        distance += 18;
      }
    }

    // Draw sneaker lace notches
    final lacePaint = Paint()
      ..color = AppTheme.orange.withValues(alpha: 0.75)
      ..strokeWidth = 2.0;
    canvas.drawLine(Offset(w * 0.49, h * 0.38), Offset(w * 0.55, h * 0.42), lacePaint);
    canvas.drawLine(Offset(w * 0.45, h * 0.41), Offset(w * 0.51, h * 0.45), lacePaint);
    canvas.drawLine(Offset(w * 0.41, h * 0.45), Offset(w * 0.47, h * 0.49), lacePaint);
  }

  @override
  bool shouldRepaint(covariant _ScanFramePainter oldDelegate) =>
      oldDelegate.isDark != isDark;
}
