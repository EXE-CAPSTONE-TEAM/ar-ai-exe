import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/models/kiri_status.dart';

void main() {
  test('parses a ready/raw Kiri response', () {
    final status = KiriStatus.fromJson({
      'scanSessionId': 'scan_1',
      'projectId': 'proj_1',
      'status': 'raw',
      'progress': 100,
      'previewUrl': '/preview',
      'modelAssetId': 'asset_123',
    });

    expect(status.isReady, isTrue);
    expect(status.isFailed, isFalse);
    expect(status.progress, 100);
    expect(status.previewUrl, '/preview');
    expect(status.modelAssetId, 'asset_123');
  });

  test('parses an in-progress Kiri response', () {
    final status = KiriStatus.fromJson({
      'scanSessionId': 'scan_2',
      'status': 'kiri_processing',
      'progress': 45,
    });

    expect(status.isReady, isFalse);
    expect(status.isFailed, isFalse);
    expect(status.progress, 45);
    expect(status.previewUrl, isNull);
  });

  test('parses a failed Kiri response', () {
    final status = KiriStatus.fromJson({
      'scanSessionId': 'scan_3',
      'status': 'failed',
      'progress': 10,
      'errorMessage': 'Dựng mô hình thất bại do video thiếu sáng.',
    });

    expect(status.isReady, isFalse);
    expect(status.isFailed, isTrue);
    expect(status.errorMessage, contains('thiếu sáng'));
  });
}
