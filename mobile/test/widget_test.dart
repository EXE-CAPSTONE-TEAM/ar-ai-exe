import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:shoe_visual_customizer_mobile/app/app_shell.dart';
import 'package:shoe_visual_customizer_mobile/config/app_config.dart';
import 'package:shoe_visual_customizer_mobile/screens/auth_screen.dart';
import 'package:shoe_visual_customizer_mobile/screens/scan_home_screen.dart';

import 'package:shoe_visual_customizer_mobile/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const secureStorageChannel =
      MethodChannel('plugins.it_nomads.com/flutter_secure_storage');

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      secureStorageChannel,
      (call) async => call.method == 'read' ? null : true,
    );
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      secureStorageChannel,
      null,
    );
  });

  testWidgets('shows authentication entry screen', (WidgetTester tester) async {
    await tester.pumpWidget(const ShoeScannerApp());
    await tester.pumpAndSettle();

    expect(find.text('KusShoes'), findsOneWidget);
  });

  testWidgets('starts in light mode', (WidgetTester tester) async {
    await tester.pumpWidget(const ShoeScannerApp());
    await tester.pumpAndSettle();

    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.themeMode, ThemeMode.light);
  });

  testWidgets('opens on the Quét AI tab and fits a 360dp phone',
      (WidgetTester tester) async {
    // 360x800 is the common narrow Android size; a RenderFlex overflow here
    // fails the test, which is how the header/nav overflows were caught.
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(themeMode: ThemeMode.light, onThemeModeChanged: (_) {}),
      ),
    );
    await tester.pump();

    // Scanning is the point of the mobile app, so it is the landing tab.
    expect(HomeTab.values[1], HomeTab.scan);
    expect(find.byType(ScanHomeScreen), findsOneWidget);
  });

  test('webUrl joins paths without doubling slashes', () {
    expect(AppConfig.webUrl(), isNot(endsWith('/')));
    expect(AppConfig.webUrl('/pricing'), endsWith('/pricing'));
    expect(AppConfig.webUrl('pricing'), AppConfig.webUrl('/pricing'));
    expect(AppConfig.webUrl('/pricing'), isNot(contains('//pricing')));
  });

  testWidgets('guest tapping scan CTA shows upgrade sheet and navigates to register',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          themeMode: ThemeMode.light,
          onThemeModeChanged: (_) {},
          isGuest: true,
        ),
      ),
    );
    await tester.pump();

    // Tap the scan CTA button
    final scanButton = find.textContaining('QUÉT 360°');
    expect(scanButton, findsOneWidget);
    await tester.tap(scanButton);
    await tester.pumpAndSettle();

    // Upgrade sheet is displayed with register CTA
    expect(find.text('Quét 3D cần tài khoản có gói'), findsOneWidget);
    final registerCta = find.text('ĐĂNG KÝ TÀI KHOẢN');
    expect(registerCta, findsOneWidget);

    // Tap register CTA
    await tester.tap(registerCta);
    await tester.pumpAndSettle();

    // Verifies navigation to AuthScreen with registration form active
    expect(find.byType(AuthScreen), findsOneWidget);
    expect(find.text('Tạo tài khoản'), findsOneWidget);
  });
}
