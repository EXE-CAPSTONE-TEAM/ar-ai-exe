import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/models/kiri_status.dart';

void main() {
  test('parses a ready-for-crop Kiri response', () {
    final status = KiriStatus.fromJson({
      'scanSessionId': 'scan_1',
      'projectId': 'proj_1',
      'status': 'ready_for_crop',
      'progress': 75,
      'previewUrl': '/preview',
      'cropBox': {
        'center': {'x': 0, 'y': 0, 'z': 0},
        'size': {'x': 1, 'y': 0.8, 'z': 0.7},
        'rotation': {'x': 0, 'y': 15, 'z': 0},
      },
    });

    expect(status.canCrop, isTrue);
    expect(status.cropBox?.size.y, 0.8);
    expect(status.cropBox?.rotation.y, 15);
  });

  test('serializes crop coordinates in normalized space', () {
    const crop = CropBox(
      center: CropAxis(x: 0.1, y: -0.2, z: 0),
      size: CropAxis(x: 0.8, y: 0.9, z: 1),
    );

    expect(crop.toJson()['coordinateSpace'], 'normalized');
    expect((crop.toJson()['center'] as Map<String, dynamic>)['x'], 0.1);
  });
}
