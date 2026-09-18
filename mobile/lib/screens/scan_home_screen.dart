import 'package:flutter/material.dart';

import '../app/app_theme.dart';
import '../models/reconstruction_readiness.dart';
import '../services/backend_api.dart';
import '../widgets/scan_hero_card.dart';
import 'scan_setup_screen.dart';

class ScanHomeScreen extends StatefulWidget {
  const ScanHomeScreen({this.isGuest = false, super.key});

  final bool isGuest;

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
            padding: const EdgeInsets.fromLTRB(18, 20, 18, 132),
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.orange.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.orange.withValues(alpha: 0.35)),
                    ),
                    child: Text(
                      'BƯỚC 01 · QUÉT AI 360°',
                      style: AppTheme.monoFont(
                        color: AppTheme.orange,
                        letterSpacing: 1.2,
                        fontSize: 11,
                      ),
                    ),
                  ),
                  const Spacer(),
                  // Quota Badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: widget.isGuest
                          ? AppTheme.statusScanned.withValues(alpha: 0.15)
                          : AppTheme.orange.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: widget.isGuest
                            ? AppTheme.statusScanned.withValues(alpha: 0.4)
                            : AppTheme.orange.withValues(alpha: 0.4),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircleAvatar(
                          radius: 4,
                          backgroundColor: widget.isGuest
                              ? AppTheme.statusScanned
                              : AppTheme.orange,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          widget.isGuest ? 'GUEST: 1 SCAN THỬ' : 'BASIC: 1/1 SCAN',
                          style: AppTheme.monoFont(
                            fontSize: 10.5,
                            color: widget.isGuest
                                ? AppTheme.statusScanned
                                : AppTheme.orange,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                'Quét Giày 3D Bằng AI',
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                      fontWeight: FontWeight.w900,
                      height: 1.05,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                'Tự động nhận diện phôi giày, tái tạo đám mây điểm 360° và nén thành mô hình GLB chuẩn Kus Studio.',
                style: AppTheme.bodyFont(
                  fontSize: 13.5,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 22),
              const ScanHeroCard(),
              const SizedBox(height: 32),
              Center(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.orange.withValues(alpha: 0.45),
                        blurRadius: 36,
                        spreadRadius: 4,
                      ),
                    ],
                  ),
                  child: FilledButton(
                    onPressed: _openSetup,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppTheme.orange,
                      foregroundColor: Colors.black,
                      shape: const CircleBorder(),
                      fixedSize: const Size(96, 96),
                    ),
                    child: const Icon(Icons.center_focus_strong, size: 40),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Bắt Đầu Tạo Lưới 3D Bằng AI',
                textAlign: TextAlign.center,
                style: AppTheme.headingFont(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Hỗ trợ camera 720p/1080p · KusShoes Neural Engine',
                textAlign: TextAlign.center,
                style: AppTheme.monoFont(
                  fontSize: 11,
                  color: Theme.of(context)
                      .colorScheme
                      .onSurface
                      .withValues(alpha: 0.55),
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 28),

              // 3 Standard Shoe Presets (BR-41)
              const _StandardPresetsRow(),
              const SizedBox(height: 24),

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

class _StandardPresetsRow extends StatelessWidget {
  const _StandardPresetsRow();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'PHÔI MẪU 3D CÓ SẴN (BR-41)',
                style: AppTheme.monoFont(
                  fontSize: 11.5,
                  letterSpacing: 1.2,
                  color: AppTheme.orange,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                'Miễn phí',
                style: AppTheme.monoFont(fontSize: 10, color: Colors.white70),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 94,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: const [
              _PresetCard(
                title: 'Sneaker Low-Top',
                type: 'Cổ thấp · Canvas',
                icon: Icons.sports_tennis_outlined,
              ),
              SizedBox(width: 10),
              _PresetCard(
                title: 'Runner Blade Pro',
                type: 'Chạy bộ · Mesh lưới',
                icon: Icons.directions_run_outlined,
              ),
              SizedBox(width: 10),
              _PresetCard(
                title: 'Classic High Boot',
                type: 'Cao cổ · Da thuộc',
                icon: Icons.hiking_outlined,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _PresetCard extends StatelessWidget {
  const _PresetCard({
    required this.title,
    required this.type,
    required this.icon,
  });

  final String title;
  final String type;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: 165,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark ? AppTheme.darkCard : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? AppTheme.darkCardBorder : const Color(0x18000000),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: AppTheme.orange.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppTheme.orange, size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTheme.headingFont(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  type,
                  maxLines: 1,
                  style: AppTheme.bodyFont(
                    fontSize: 10.5,
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withValues(alpha: 0.6),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
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
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'TIẾN TRÌNH TẠO MÔ HÌNH 3D',
              style: AppTheme.monoFont(
                fontSize: 11,
                letterSpacing: 1.2,
                color: AppTheme.orange,
              ),
            ),
            const SizedBox(height: 16),
            const _GenerationStep(
              stepNumber: '1',
              text: 'Tải video/ảnh 360° lên máy chủ...',
            ),
            const _GenerationStep(
              stepNumber: '2',
              text: 'AI tái tạo đám mây điểm & dựng lưới 3D...',
            ),
            const _GenerationStep(
              stepNumber: '3',
              text: 'Nén sang định dạng GLB... Sẵn sàng!',
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: onOpen,
              icon: const Icon(Icons.videocam_outlined),
              label: const Text('BẮT ĐẦU CẤU HÌNH & QUÉT'),
            ),
          ],
        ),
      ),
    );
  }
}

class _GenerationStep extends StatelessWidget {
  const _GenerationStep({
    required this.stepNumber,
    required this.text,
  });

  final String stepNumber;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: AppTheme.orange,
            ),
            alignment: Alignment.center,
            child: Text(
              stepNumber,
              style: AppTheme.monoFont(
                fontSize: 12,
                fontWeight: FontWeight.w900,
                color: Colors.black,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              text,
              style: AppTheme.headingFont(
                fontSize: 13.5,
                fontWeight: FontWeight.w700,
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
