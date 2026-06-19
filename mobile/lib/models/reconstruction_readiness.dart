class ReconstructionReadiness {
  ReconstructionReadiness({
    required this.ready,
    required this.message,
    required this.missingTools,
  });

  final bool ready;
  final String message;
  final List<String> missingTools;

  factory ReconstructionReadiness.fromJson(Map<String, dynamic> json) {
    return ReconstructionReadiness(
      ready: json['ready'] as bool? ?? false,
      message:
          json['message'] as String? ?? 'Reconstruction readiness is unknown.',
      missingTools: (json['missingTools'] as List<dynamic>? ?? const [])
          .map((value) => value.toString())
          .toList(),
    );
  }

  String get userMessage {
    if (missingTools.isEmpty) {
      return message;
    }
    return '$message Missing tools: ${missingTools.join(', ')}.';
  }
}
