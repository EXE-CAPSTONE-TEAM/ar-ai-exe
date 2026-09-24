import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:shoe_visual_customizer_mobile/models/scan_metadata.dart';
import 'package:shoe_visual_customizer_mobile/screens/upload_progress_screen.dart';
import 'package:shoe_visual_customizer_mobile/services/api_exception.dart';
import 'package:shoe_visual_customizer_mobile/services/backend_api.dart';

/// Records the `clientRequestId` of every bootstrap and fails every upload so
/// the retry path runs.
class _RecordingApi extends BackendApi {
  final List<String> requestIds = [];
  int sessionsCreated = 0;
  int uploadAttempts = 0;

  @override
  Future<ScanGrant> beginScan({
    required String projectName,
    required String clientRequestId,
  }) async {
    requestIds.add(clientRequestId);
    return const ScanGrant(
      projectId: 'p1',
      projectName: 'p1',
      webProjectUrl: 'https://example.invalid/projects/p1',
    );
  }

  @override
  Future<String> createScanSession({required ScanMetadata metadata}) async {
    sessionsCreated += 1;
    return 'session-1';
  }

  @override
  Future<void> uploadScanVideo({
    required String scanSessionId,
    required XFile videoFile,
    void Function(int sent, int total)? onProgress,
  }) async {
    uploadAttempts += 1;
    throw const ApiException(message: 'Mất kết nối khi tải lên.');
  }
}

/// Lets pending futures resolve without waiting for the indeterminate progress
/// indicator to stop animating.
Future<void> _flush(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets('retrying an upload reuses one client_request_id', (tester) async {
    final api = _RecordingApi();

    await tester.pumpWidget(
      MaterialApp(
        home: UploadProgressScreen(
          api: api,
          metadata: _metadata(),
          videoFile: XFile('scan.mp4'),
        ),
      ),
    );
    await _flush(tester);

    expect(api.requestIds, hasLength(1));
    expect(find.text('Thử tải lên lại'), findsOneWidget);

    await tester.tap(find.text('Thử tải lên lại'));
    await _flush(tester);

    // `scans/bootstrap` is idempotent on client_request_id: reusing it resumes
    // the same project. A fresh id per retry created a new empty project and
    // consumed another scan allowance.
    expect(api.requestIds, hasLength(2));
    expect(api.requestIds.first, api.requestIds.last);

    // The compute-side session is reused too, so retries do not pile up
    // orphan scan sessions.
    expect(api.sessionsCreated, 1);
    expect(api.uploadAttempts, 2);
  });

  testWidgets('an expired session offers sign-in, not a doomed retry',
      (tester) async {
    final api = _ExpiredSessionApi();

    await tester.pumpWidget(
      MaterialApp(
        home: UploadProgressScreen(
          api: api,
          metadata: _metadata(),
          videoFile: XFile('scan.mp4'),
        ),
      ),
    );
    await _flush(tester);

    expect(find.text('Đăng nhập lại'), findsOneWidget);
    expect(find.text('Thử tải lên lại'), findsNothing);
  });
}

class _ExpiredSessionApi extends BackendApi {
  @override
  Future<ScanGrant> beginScan({
    required String projectName,
    required String clientRequestId,
  }) async {
    throw const ApiException(
      message: 'Bạn cần đăng nhập trước khi quét giày.',
      isAuthExpired: true,
    );
  }
}

ScanMetadata _metadata() => ScanMetadata(
      sizeSystem: 'EU',
      size: '42',
      side: 'left',
      type: 'sneaker',
      material: 'canvas',
      condition: 'used',
      lengthCm: 27,
      widthCm: 9.5,
      calibrationReference: 'A4 paper',
      lighting: 'bright',
      background: 'plain',
      customizationGoal: const ['change_color'],
    );
