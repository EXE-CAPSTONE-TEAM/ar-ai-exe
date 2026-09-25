import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/models/kiri_status.dart';
import 'package:shoe_visual_customizer_mobile/screens/scan_result_screen.dart';
import 'package:shoe_visual_customizer_mobile/services/backend_api.dart';

class _MockResultApi extends BackendApi {
  _MockResultApi({this.statusToReturn});

  final KiriStatus? statusToReturn;

  String? savedProjectName;
  int saveCallCount = 0;
  int getStatusCallCount = 0;

  @override
  Future<KiriStatus> getKiriStatus({required String scanSessionId}) async {
    getStatusCallCount++;
    return statusToReturn ??
        KiriStatus(
          scanSessionId: scanSessionId,
          status: 'raw',
          progress: 100,
        );
  }

  @override
  Future<String> getKiriPreviewLocationUrl({
    required String scanSessionId,
  }) async {
    // A preview URL would mount ModelViewer, which needs a platform WebView that
    // widget tests do not have; the screen keeps working without a preview.
    throw Exception('no preview in widget tests');
  }

  @override
  Future<KiriStatus> saveKiriProject({
    required String scanSessionId,
    required String projectName,
  }) async {
    saveCallCount++;
    savedProjectName = projectName;
    return KiriStatus(
      scanSessionId: scanSessionId,
      status: 'saving',
      progress: 100,
    );
  }
}

Future<void> _flush(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  group('ScanResultScreen', () {
    testWidgets('displays raw model preview card, "Lưu project", and "Mở trên Desktop"',
        (tester) async {
      final api = _MockResultApi(
        statusToReturn: const KiriStatus(
          scanSessionId: 'sess-100',
          status: 'raw',
          progress: 100,
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ScanResultScreen(
            scanSessionId: 'sess-100',
            api: api,
            status: 'raw',
            webDesignUrl: 'https://app.kusshoes.com/design/sess-100',
          ),
        ),
      );
      await _flush(tester);

      // Verify raw model preview badge is shown
      expect(find.text('RAW MODEL PREVIEW'), findsOneWidget);

      // Verify "Lưu project" button and "Mở trên Desktop" button exist
      expect(find.text('Lưu project'), findsOneWidget);
      expect(find.text('Mở trên Desktop'), findsOneWidget);

      // Verify project name input field exists
      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Đôi giày của tôi'), findsOneWidget);
    });

    testWidgets('tapping "Lưu project" calls saveKiriProject with current name',
        (tester) async {
      final api = _MockResultApi();

      await tester.pumpWidget(
        MaterialApp(
          home: ScanResultScreen(
            scanSessionId: 'sess-100',
            api: api,
            status: 'raw',
            projectName: 'Giày Sneaker Phố',
          ),
        ),
      );
      await _flush(tester);

      final saveButton = find.text('Lưu project');
      expect(saveButton, findsOneWidget);

      await tester.ensureVisible(saveButton);
      await tester.pump();
      await tester.tap(saveButton);
      await _flush(tester);

      expect(api.saveCallCount, 1);
      expect(api.savedProjectName, 'Giày Sneaker Phố');
      expect(find.text('Đã lưu project'), findsOneWidget);
    });

    testWidgets('shows progress status while reconstruction is ongoing',
        (tester) async {
      final api = _MockResultApi(
        statusToReturn: const KiriStatus(
          scanSessionId: 'sess-200',
          status: 'kiri_processing',
          progress: 60,
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ScanResultScreen(
            scanSessionId: 'sess-200',
            api: api,
            status: 'kiri_processing',
            initialStatus: const KiriStatus(
              scanSessionId: 'sess-200',
              status: 'kiri_processing',
              progress: 60,
            ),
          ),
        ),
      );
      await tester.pump();

      expect(find.text('ĐANG XỬ LÝ'), findsOneWidget);
      expect(find.textContaining('60%'), findsOneWidget);
    });
  });
}
