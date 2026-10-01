import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/models/kiri_status.dart';
import 'package:shoe_visual_customizer_mobile/screens/scan_result_screen.dart';
import 'package:shoe_visual_customizer_mobile/services/backend_api.dart';

class _MockResultApi extends BackendApi {
  _MockResultApi({this.statusToReturn, this.statusAfterSave});

  final KiriStatus? statusToReturn;

  /// What the relay reports once save-project has queued the publish.
  final KiriStatus? statusAfterSave;

  String? savedProjectName;
  int saveCallCount = 0;
  int getStatusCallCount = 0;
  int startProcessingCallCount = 0;

  /// What the relay reports once a retry has re-queued the reconstruction.
  KiriStatus? statusAfterRetry;

  @override
  Future<KiriStatus> startKiriProcessing({
    required String scanSessionId,
  }) async {
    startProcessingCallCount++;
    return statusAfterRetry ??
        KiriStatus(
          scanSessionId: scanSessionId,
          status: 'queued',
          progress: 5,
        );
  }

  @override
  Future<KiriStatus> getKiriStatus({required String scanSessionId}) async {
    getStatusCallCount++;
    if (startProcessingCallCount > 0 && statusAfterRetry != null) {
      return statusAfterRetry!;
    }
    if (saveCallCount > 0) {
      return statusAfterSave ??
          KiriStatus(
            scanSessionId: scanSessionId,
            status: 'ready',
            progress: 100,
          );
    }
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
      status: 'crop_baking',
      progress: 90,
    );
  }
}

/// Lets the save loop's poll delay elapse and the follow-up status resolve.
Future<void> _pollOnce(WidgetTester tester) async {
  await tester.pump(const Duration(seconds: 3));
  await _flush(tester);
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
      // Publish is still running on the relay: keep spinning, no success yet.
      expect(find.text('Đang lưu project...'), findsOneWidget);
      expect(find.text('Đã lưu project'), findsNothing);

      await _pollOnce(tester);

      expect(find.text('Đã lưu project'), findsOneWidget);
      expect(
        find.text('Dự án của bạn đã được lưu thành công!'),
        findsOneWidget,
      );
    });

    testWidgets('a failed publish stops the spinner and allows another try',
        (tester) async {
      final api = _MockResultApi(
        statusAfterSave: const KiriStatus(
          scanSessionId: 'sess-100',
          status: 'failed',
          progress: 0,
          errorMessage: 'Kiri publish failed.',
        ),
      );

      await tester.pumpWidget(
        MaterialApp(
          home: ScanResultScreen(
            scanSessionId: 'sess-100',
            api: api,
            status: 'raw',
          ),
        ),
      );
      await _flush(tester);

      final saveButton = find.text('Lưu project');
      await tester.ensureVisible(saveButton);
      await tester.pump();
      await tester.tap(saveButton);
      await _flush(tester);
      await _pollOnce(tester);

      expect(find.text('Lưu project'), findsOneWidget);
      expect(find.text('Đã lưu project'), findsNothing);
      expect(
        find.text('Lưu dự án thất bại: Kiri publish failed.'),
        findsOneWidget,
      );
    });

    testWidgets('ready_for_crop shows 100% and stops polling so the user can save',
        (tester) async {
      const readyForCrop = KiriStatus(
        scanSessionId: 'sess-300',
        status: 'ready_for_crop',
        progress: 75,
      );
      final api = _MockResultApi(statusToReturn: readyForCrop);

      await tester.pumpWidget(
        MaterialApp(
          home: ScanResultScreen(
            scanSessionId: 'sess-300',
            api: api,
            status: 'kiri_processing',
            initialStatus: const KiriStatus(
              scanSessionId: 'sess-300',
              status: 'kiri_processing',
              progress: 55,
            ),
          ),
        ),
      );
      await _flush(tester);

      expect(find.text('SẴN SÀNG'), findsOneWidget);
      expect(find.text('RAW MODEL PREVIEW'), findsOneWidget);
      expect(find.textContaining('100%'), findsOneWidget);
      expect(find.textContaining('75%'), findsNothing);

      final callsAfterReady = api.getStatusCallCount;
      await tester.pump(const Duration(seconds: 10));
      expect(api.getStatusCallCount, callsAfterReady);

      final saveButton = find.text('Lưu project');
      await tester.ensureVisible(saveButton);
      await tester.pump();
      await tester.tap(saveButton);
      await _flush(tester);
      await _pollOnce(tester);

      expect(api.saveCallCount, 1);
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

    testWidgets('"Thử lại" after a failed reconstruction re-queues it on the relay',
        (tester) async {
      final api = _MockResultApi(
        statusToReturn: const KiriStatus(
          scanSessionId: 'sess-500',
          status: 'failed',
          progress: 0,
          errorMessage: 'success',
        ),
      )..statusAfterRetry = const KiriStatus(
          scanSessionId: 'sess-500',
          status: 'kiri_processing',
          progress: 40,
        );

      await tester.pumpWidget(
        MaterialApp(
          home: ScanResultScreen(
            scanSessionId: 'sess-500',
            api: api,
            status: 'failed',
          ),
        ),
      );
      await _flush(tester);
      expect(find.text('Dựng mô hình thất bại'), findsOneWidget);

      final retry = find.text('Thử lại');
      await tester.ensureVisible(retry);
      await tester.pump();
      await tester.tap(retry);
      await _flush(tester);

      expect(api.startProcessingCallCount, 1);
      expect(find.text('Dựng mô hình thất bại'), findsNothing);
      expect(find.textContaining('40%'), findsOneWidget);

      // Leave the screen so the periodic poll timer is cancelled.
      await tester.pumpWidget(const SizedBox());
    });
  });
}
