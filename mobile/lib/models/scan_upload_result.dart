class ScanUploadResult {
  ScanUploadResult({
    required this.scanSessionId,
    required this.status,
    required this.processingStarted,
    required this.webDesignUrl,
  });

  final String scanSessionId;
  final String status;
  final bool processingStarted;
  final String webDesignUrl;

  factory ScanUploadResult.fromJson(Map<String, dynamic> json) {
    final scanSession = json['scanSession'] as Map<String, dynamic>;
    return ScanUploadResult(
      scanSessionId: scanSession['id'] as String,
      status: scanSession['status'] as String,
      processingStarted: json['processingStarted'] as bool,
      webDesignUrl: json['webDesignUrl'] as String,
    );
  }
}
