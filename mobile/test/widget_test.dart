import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:shoe_visual_customizer_mobile/config/app_config.dart';

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

  test('webUrl joins paths without doubling slashes', () {
    expect(AppConfig.webUrl(), isNot(endsWith('/')));
    expect(AppConfig.webUrl('/pricing'), endsWith('/pricing'));
    expect(AppConfig.webUrl('pricing'), AppConfig.webUrl('/pricing'));
    expect(AppConfig.webUrl('/pricing'), isNot(contains('//pricing')));
  });

  testWidgets('does not ship an internal admin login shortcut',
      (WidgetTester tester) async {
    // Regression guard: the shortcut carried hardcoded admin credentials, so
    // anyone who unzipped the APK could read them.
    await tester.pumpWidget(const ShoeScannerApp());
    await tester.pumpAndSettle();

    expect(find.textContaining('Admin'), findsNothing);
    expect(find.textContaining('admin@'), findsNothing);
  });
}
