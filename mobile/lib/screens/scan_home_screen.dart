import 'package:flutter/material.dart';

import '../app/app_theme.dart';
import '../models/reconstruction_readiness.dart';
import '../services/backend_api.dart';
import '../widgets/scan_hero_card.dart';
import 'scan_setup_screen.dart';

class ScanHomeScreen extends StatefulWidget {
  const ScanHomeScreen({super.key});

  @override
  State<ScanHomeScreen> createState() => _ScanHomeScreenState();
}

class _ScanHomeScreenState extends State<ScanHomeScreen> {
  final _api = BackendApi();
  late Future<ReconstructionReadiness> _readiness =
      _api.getReconstructionReadiness();

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(18, 24, 18, 132),
            children: [
              const Text(
                'STEP 01 · AI SCAN',
                style: TextStyle(
                  color: AppTheme.orange,
                  letterSpacing: 6,
                  fontWeight: FontWeight.w900,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Capture your foot in 3D',
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                      fontWeight: FontWeight.w900,
                      height: 0.98,
                    ),
              ),
              const SizedBox(height: 28),
              const ScanHeroCard(),
              const SizedBox(height: 40),
              Center(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.orange.withValues(alpha: 0.28),
                        blurRadius: 46,
                        spreadRadius: 8,
                      ),
                    ],
                  ),
                  child: FilledButton(
                    onPressed: _openSetup,
                    style: FilledButton.styleFrom(
                      shape: const CircleBorder(),
                      fixedSize: const Size(102, 102),
                    ),
                    child: const Icon(Icons.auto_awesome, size: 42),
                  ),
                ),
              ),
              const SizedBox(height: 28),
              Text(
                'Start AI 3D Mesh Generation',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                'Powered by KusShoe Neural Engine',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Theme.of(context)
                      .colorScheme
                      .onSurface
                      .withValues(alpha: 0.62),
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 28),
              _GenerationPanel(onOpen: _openSetup),
              const SizedBox(height: 16),
              _ReadinessStrip(
                readiness: _readiness,
                onRefresh: () => setState(() {
                  _readiness = _api.getReconstructionReadiness();
                }),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _openSetup() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ScanSetupScreen(api: _api)),
    );
  }
}

class _GenerationPanel extends StatelessWidget {
  const _GenerationPanel({required this.onOpen});

  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(22, 22, 22, 20),
        child: Column(
          children: [
            const _GenerationStep(text: 'Uploading video/photos...'),
            const _GenerationStep(
                text: 'AI Generating 3D Shoe Mesh via API...'),
            const _GenerationStep(text: 'Compressing to GLB format... Ready!'),
            const SizedBox(height: 18),
            FilledButton(
              onPressed: onOpen,
              child: const Text('Open in 3D Editor'),
            ),
          ],
        ),
      ),
    );
  }
}

class _GenerationStep extends StatelessWidget {
  const _GenerationStep({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Row(
        children: [
          const CircleAvatar(
            radius: 24,
            backgroundColor: AppTheme.orange,
            child: Icon(Icons.check, color: Colors.black),
          ),
          const SizedBox(width: 18),
          Expanded(
            child: Text(
              text,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReadinessStrip extends StatelessWidget {
  const _ReadinessStrip({
    required this.readiness,
    required this.onRefresh,
  });

  final Future<ReconstructionReadiness> readiness;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ReconstructionReadiness>(
      future: readiness,
      builder: (context, snapshot) {
        final title = snapshot.connectionState != ConnectionState.done
            ? 'Checking backend mesh readiness...'
            : snapshot.hasError
                ? 'Preview mode · backend offline'
                : snapshot.data!.ready
                    ? 'Backend mesh pipeline ready'
                    : 'Backend mesh pipeline needs attention';
        final icon = snapshot.connectionState != ConnectionState.done
            ? Icons.sync
            : snapshot.hasError
                ? Icons.cloud_off_outlined
                : snapshot.data!.ready
                    ? Icons.check_circle_outline
                    : Icons.warning_amber_rounded;

        return DecoratedBox(
          decoration: BoxDecoration(
            color:
                Theme.of(context).colorScheme.primary.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppTheme.orange.withValues(alpha: 0.25)),
          ),
          child: ListTile(
            leading: Icon(icon, color: AppTheme.orange),
            title: Text(title,
                style: const TextStyle(fontWeight: FontWeight.w800)),
            trailing: IconButton(
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh',
            ),
          ),
        );
      },
    );
  }
}
