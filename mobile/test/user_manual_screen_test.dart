import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/app/app_theme.dart';
import 'package:shoe_visual_customizer_mobile/screens/user_manual_screen.dart';

void main() {
  testWidgets('UserManualScreen renders friendly UI and fits 360dp screen',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.dark(),
        home: const Scaffold(
          body: UserManualScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Verify friendly title and header tag
    expect(find.text('Tự Tạo Giày Riêng'), findsOneWidget);
    expect(find.text('DỄ HIỂU TRONG 1 PHÚT'), findsOneWidget);

    // Verify Tab 0 (3 Bước Làm) default state
    expect(find.text('1'), findsOneWidget);
    expect(find.text('Cầm Điện Thoại Quay 1 Vòng'), findsOneWidget);
    expect(find.text('BƯỚC ĐI VÒNG QUANH GIÀY'), findsOneWidget);

    // Switch to Tab 1 (Mẹo Quay Đẹp)
    await tester.tap(find.text('Mẹo Quay Đẹp'));
    await tester.pumpAndSettle();
    expect(find.text('MẸO ĐỂ CÓ MẪU GIÀY ĐẸP'), findsOneWidget);
    expect(find.text('NHỮNG ĐIỀU NÊN TRÁNH'), findsOneWidget);

    // Switch to Tab 2 (Gửi Thợ Vẽ)
    await tester.tap(find.text('Gửi Thợ Vẽ'));
    await tester.pumpAndSettle();
    expect(find.text('ĐƯA THIẾT KẾ RA GIÀY THẬT'), findsOneWidget);
    expect(find.text('Thử Trang Trí Giày Ngay'), findsOneWidget);
  });
}
