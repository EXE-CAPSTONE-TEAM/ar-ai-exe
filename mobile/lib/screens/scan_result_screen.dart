import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

class ScanResultScreen extends StatelessWidget {
  const ScanResultScreen({
    required this.scanSessionId,
    required this.status,
    required this.processingStarted,
    required this.webDesignUrl,
    super.key,
  });

  final String scanSessionId;
  final String status;
  final bool processingStarted;
  final String webDesignUrl;

  @override
  Widget build(BuildContext context) {
    final statusLabel = _statusLabel(status);

    return Scaffold(
      appBar: AppBar(title: const Text('Scan uploaded')),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Scan session ID',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    SelectableText(scanSessionId),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: () => _copyScanId(context),
                      icon: const Icon(Icons.copy),
                      label: const Text('Copy scan ID'),
                    ),
                    const SizedBox(height: 24),
                    Text('Status',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    _StatusChip(
                        label: statusLabel, isProcessing: processingStarted),
                    const SizedBox(height: 16),
                    Text(
                      processingStarted
                          ? 'Both shoe videos uploaded. Reconstruction is running on the backend and may take several minutes.'
                          : status == 'toolchain_unavailable'
                              ? 'Both shoe videos uploaded. Backend reconstruction toolchain is not available yet. Keep this scan ID and retry processing after deployment is fixed.'
                              : 'Both shoe videos uploaded. Processing has not started yet.',
                    ),
                    const SizedBox(height: 24),
                    Text('Web design URL',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    SelectableText(webDesignUrl),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        FilledButton.icon(
                          onPressed: () => _openDesignUrl(context),
                          icon: const Icon(Icons.open_in_browser),
                          label: const Text('Open in Web Designer'),
                        ),
                        OutlinedButton.icon(
                          onPressed: () => _copyDesignUrl(context),
                          icon: const Icon(Icons.copy),
                          label: const Text('Copy link'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () =>
                      Navigator.of(context).popUntil((route) => route.isFirst),
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: const Text('Scan another shoe'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openDesignUrl(BuildContext context) async {
    final uri = Uri.parse(webDesignUrl);
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open web designer.')),
      );
    }
  }

  Future<void> _copyDesignUrl(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: webDesignUrl));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Design link copied.')),
      );
    }
  }

  Future<void> _copyScanId(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: scanSessionId));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Scan ID copied.')),
      );
    }
  }

  String _statusLabel(String value) {
    return switch (value) {
      'uploaded' => 'Uploaded',
      'queued' => 'Queued',
      'toolchain_unavailable' => 'Toolchain unavailable',
      'extracting_frames' => 'Extracting frames',
      'filtering_frames' => 'Filtering frames',
      'preparing_reconstruction' => 'Preparing reconstruction',
      'reconstructing' => 'Reconstructing',
      'cleaning_mesh' => 'Cleaning mesh',
      'exporting' => 'Exporting',
      'completed' => 'Completed',
      'failed' => 'Failed',
      _ => value,
    };
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.isProcessing});

  final String label;
  final bool isProcessing;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: isProcessing
            ? colorScheme.primaryContainer
            : colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        child: Text(
          label,
          style: TextStyle(
            color: isProcessing
                ? colorScheme.onPrimaryContainer
                : colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}
