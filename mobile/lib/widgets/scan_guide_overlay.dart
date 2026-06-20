import 'package:flutter/material.dart';

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
        painter: _GuidePainter(),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DecoratedBox(
                decoration: BoxDecoration(
                  color: const Color(0xFF0A0F14).withOpacity(0.72),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.white.withOpacity(0.12)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    children: [
                      Text(
                        passTitle,
                        style: const TextStyle(
                          color: Color(0xFFF36A35),
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        isRecording
                            ? '$recordingInstruction $seconds s'
                            : '$idleInstruction Recommended scan: 30-60 s.',
                        style: const TextStyle(color: Colors.white),
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
  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height / 2),
      width: size.width * 0.82,
      height: size.height * 0.46,
    );
    final paint = Paint()
      ..color = const Color(0xFFF36A35)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;
    canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(20)), paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
