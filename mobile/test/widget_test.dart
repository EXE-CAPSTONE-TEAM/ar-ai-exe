import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

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

    expect(find.text('Shoe Scanner'), findsOneWidget);
    expect(find.text('Use local demo'), findsOneWidget);
  });
}
