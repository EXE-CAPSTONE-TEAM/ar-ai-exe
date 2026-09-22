import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:shoe_visual_customizer_mobile/widgets/scan_guide_overlay.dart';

void main() {
  testWidgets('ScanGuideOverlay shows idle multi-tier instruction when not recording',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ScanGuideOverlay(
            seconds: 0,
            isRecording: false,
          ),
        ),
      ),
    );

    expect(find.textContaining('0-20s: Ngang thân giày'), findsOneWidget);
    expect(find.textContaining('20-45s: Nghiêng 45° từ trên xuống'), findsOneWidget);
  });

  testWidgets('ScanGuideOverlay displays Tier 1 guidance for first 20 seconds',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ScanGuideOverlay(
            seconds: 10,
            isRecording: true,
          ),
        ),
      ),
    );

    expect(find.text('TẦNG 1: NGANG THÂN GIÀY'), findsOneWidget);
    expect(find.textContaining('Giữ máy ngang tầm thân giày'), findsOneWidget);
  });

  testWidgets('ScanGuideOverlay switches to Tier 2 guidance at and after 20 seconds',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ScanGuideOverlay(
            seconds: 22,
            isRecording: true,
          ),
        ),
      ),
    );

    expect(find.text('TẦNG 2: NGHIÊNG 45° TRÊN XUỐNG'), findsOneWidget);
    expect(find.textContaining('Nâng máy góc nghiêng 45°'), findsOneWidget);
  });
}
