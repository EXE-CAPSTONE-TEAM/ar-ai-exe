class CropAxis {
  const CropAxis({required this.x, required this.y, required this.z});

  final double x;
  final double y;
  final double z;

  CropAxis copyWith({double? x, double? y, double? z}) => CropAxis(
        x: x ?? this.x,
        y: y ?? this.y,
        z: z ?? this.z,
      );

  Map<String, dynamic> toJson() => {'x': x, 'y': y, 'z': z};

  factory CropAxis.fromJson(Map<String, dynamic> json) => CropAxis(
        x: (json['x'] as num).toDouble(),
        y: (json['y'] as num).toDouble(),
        z: (json['z'] as num).toDouble(),
      );
}

class CropBox {
  const CropBox({
    this.center = const CropAxis(x: 0, y: 0, z: 0),
    this.size = const CropAxis(x: 1, y: 1, z: 1),
    this.rotation = const CropAxis(x: 0, y: 0, z: 0),
  });

  final CropAxis center;
  final CropAxis size;
  final CropAxis rotation;

  CropBox copyWith({CropAxis? center, CropAxis? size, CropAxis? rotation}) =>
      CropBox(
        center: center ?? this.center,
        size: size ?? this.size,
        rotation: rotation ?? this.rotation,
      );

  Map<String, dynamic> toJson() => {
        'center': center.toJson(),
        'size': size.toJson(),
        'rotation': rotation.toJson(),
        'coordinateSpace': 'normalized',
      };

  factory CropBox.fromJson(Map<String, dynamic> json) => CropBox(
        center: CropAxis.fromJson(json['center'] as Map<String, dynamic>),
        size: CropAxis.fromJson(json['size'] as Map<String, dynamic>),
        rotation:
            CropAxis.fromJson(json['rotation'] as Map<String, dynamic>),
      );
}

class KiriStatus {
  const KiriStatus({
    required this.scanSessionId,
    required this.status,
    required this.progress,
    this.projectId,
    this.providerStatus,
    this.previewUrl,
    this.cropBox,
    this.modelAssetId,
    this.errorMessage,
  });

  final String scanSessionId;
  final String? projectId;
  final String status;
  final String? providerStatus;
  final int progress;
  final String? previewUrl;
  final CropBox? cropBox;
  final String? modelAssetId;
  final String? errorMessage;

  bool get canCrop => status == 'ready_for_crop' || status == 'crop_configured';
  bool get isSaving => status == 'crop_baking';
  bool get isReady => status == 'ready';
  bool get isFailed => status == 'failed' || status == 'expired';

  factory KiriStatus.fromJson(Map<String, dynamic> json) => KiriStatus(
        scanSessionId: json['scanSessionId'] as String,
        projectId: json['projectId'] as String?,
        status: json['status'] as String,
        providerStatus: json['providerStatus'] as String?,
        progress: json['progress'] as int? ?? 0,
        previewUrl: json['previewUrl'] as String?,
        cropBox: json['cropBox'] == null
            ? null
            : CropBox.fromJson(json['cropBox'] as Map<String, dynamic>),
        modelAssetId: json['modelAssetId'] as String?,
        errorMessage: json['errorMessage'] as String?,
      );
}
