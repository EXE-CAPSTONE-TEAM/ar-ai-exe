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

  /// Statuses in which the raw model exists and can be previewed and saved.
  /// The relay stops at `ready_for_crop` (progress 75) until the app calls
  /// save-project, so the app must treat it as done rather than keep waiting.
  static const readyStatuses = {
    'ready',
    'completed',
    'raw',
    'ready_for_crop',
    'crop_configured',
  };
  static const failedStatuses = {'failed', 'expired'};

  bool get isReady => readyStatuses.contains(status);
  bool get isSaving => status == 'saving' || status == 'crop_baking';
  bool get isFailed => failedStatuses.contains(status);

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
