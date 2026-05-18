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
    return Scaffold(
      appBar: AppBar(title: const Text('Scan uploaded')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Scan session ID', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            SelectableText(scanSessionId),
            const SizedBox(height: 24),
            Text('Status', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(status),
            const SizedBox(height: 24),
            Text(
              processingStarted
                  ? 'Uploaded successfully. Backend processing has started.'
                  : 'Uploaded successfully. Processing has not started yet.',
            ),
            const SizedBox(height: 24),
            Text('Web design URL', style: Theme.of(context).textTheme.titleMedium),
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
            const Spacer(),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
              icon: const Icon(Icons.add_a_photo_outlined),
              label: const Text('Scan another shoe'),
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
}