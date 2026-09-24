class KiriStatus {
  const KiriStatus({
    required this.scanSessionId,
    required this.status,
    required this.progress,
    this.projectId,
    this.providerStatus,
    this.previewUrl,
    this.modelAssetId,
    this.errorMessage,
  });

  final String scanSessionId;
  final String? projectId;
  final String status;
  final String? providerStatus;
  final int progress;
  final String? previewUrl;
  final String? modelAssetId;
  final String? errorMessage;

  bool get isReady =>
      status == 'ready' || status == 'completed' || status == 'raw';
  bool get isSaving => status == 'saving' || status == 'crop_baking';
  bool get isFailed => status == 'failed' || status == 'expired';

  factory KiriStatus.fromJson(Map<String, dynamic> json) => KiriStatus(
        scanSessionId: json['scanSessionId'] as String,
        projectId: json['projectId'] as String?,
        status: json['status'] as String,
        providerStatus: json['providerStatus'] as String?,
        progress: json['progress'] as int? ?? 0,
        previewUrl: json['previewUrl'] as String?,
        modelAssetId: json['modelAssetId'] as String?,
        errorMessage: json['errorMessage'] as String?,
      );
}
