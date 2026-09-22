import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:shoe_visual_customizer_mobile/app/app_shell.dart';
import 'package:shoe_visual_customizer_mobile/models/account.dart';
import 'package:shoe_visual_customizer_mobile/services/backend_api.dart';

/// A signed-in account, so the tab renders its real content rather than the
/// "could not load" banner an unauthenticated run would show.
class _SignedInApi extends BackendApi {
  @override
  Future<UserProfile> getProfile() async => UserProfile.fromJson(const {
        'id': 'u1',
        'account_code': 'KS-2026-00002',
        'email': 'verify@example.com',
        'username': 'verifyuser',
        'first_name': 'Verify',
        'last_name': 'User',
        'total_designs': 0,
        'status': 'active',
      });

  @override
  Future<AccountUsage> getUsage() async => AccountUsage.fromJson(const {
        'tier': 'free',
        'max_projects': 3,
        'max_exports_per_month': 0,
        'projects_count': 0,
        'exports_count': 0,
        'ai_credits_used': 0,
        'ai_credits_limit': 5,
        'max_scans_per_cycle': 0,
      });
}

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
        .setMockMethodCallHandler(secureStorageChannel, null);
  });

  testWidgets('Cá nhân tab displays profile info and allows scrolling settings',
      (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    BackendApi.shared = _SignedInApi();

    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(themeMode: ThemeMode.light, onThemeModeChanged: (_) {}),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Cá nhân'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    // Verify user profile details render correctly
    expect(find.text('Verify User'), findsOneWidget);
    expect(find.text('verify@example.com'), findsOneWidget);
    expect(find.text('KS-2026-00002'), findsOneWidget);

    // Verify key menu items are present in the list
    expect(find.text('Thiết kế của tôi'), findsOneWidget);
    expect(find.text('Gói cước & Hạn mức'), findsOneWidget);
    expect(find.text('Thông tin cá nhân'), findsOneWidget);

    // Scroll to see the bottom options (Đánh giá, Xóa tài khoản)
    final scrollable = find
        .descendant(
          of: find.byType(RefreshIndicator),
          matching: find.byType(Scrollable),
        )
        .first;

    await tester.drag(scrollable, const Offset(0, -300));
    await tester.pump();

    expect(find.text('Đánh giá & Góp ý'), findsOneWidget);
    expect(find.text('Xóa tài khoản'), findsOneWidget);
  });
}
