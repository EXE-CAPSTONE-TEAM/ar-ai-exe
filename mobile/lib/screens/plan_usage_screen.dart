import 'package:flutter/material.dart';

import '../app/app_theme.dart';
import '../models/account.dart';
import '../services/api_exception.dart';
import '../services/backend_api.dart';

/// SC-26 "Gói cước & Hạn mức" — plan and per-cycle quota, read from
/// `GET /api/v1/subscription` and `GET /api/v1/users/me/usage`.
///
/// Every number here comes from the backend, which reads the §3.2.8 plan table
/// (BR-92: one source of truth for quota figures across every screen).
class PlanUsageScreen extends StatefulWidget {
  const PlanUsageScreen({required this.api, super.key});

  final BackendApi api;

  @override
  State<PlanUsageScreen> createState() => _PlanUsageScreenState();
}

class _PlanUsageScreenState extends State<PlanUsageScreen> {
  AccountUsage? _usage;
  SubscriptionInfo? _subscription;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // Sequential rather than concurrent: both calls can trigger the shared
      // single-flight token refresh, and this keeps the failure attributable.
      final usage = await widget.api.getUsage();
      final subscription = await widget.api.getSubscription();
      if (!mounted) return;
      setState(() {
        _usage = usage;
        _subscription = subscription;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Gói cước & Hạn mức')),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    final error = _error;
    if (error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_outlined, size: 46, color: Colors.grey),
              const SizedBox(height: 16),
              Text(error, textAlign: TextAlign.center),
              const SizedBox(height: 20),
              FilledButton(onPressed: _load, child: const Text('Thử lại')),
            ],
          ),
        ),
      );
    }

    final usage = _usage!;
    final subscription = _subscription;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 28),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        'GÓI ${usage.tierLabel}',
                        style: AppTheme.headingFont(
                          fontSize: 22,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const Spacer(),
                      if (subscription != null)
                        Text(
                          subscription.statusLabel,
                          style: AppTheme.monoFont(
                            fontSize: 11,
                            color: AppTheme.orange,
                          ),
                        ),
                    ],
                  ),
                  if (subscription?.expiresAt case final expiresAt?) ...[
                    const SizedBox(height: 8),
                    Text(
                      subscription!.cancelAtPeriodEnd
                          ? 'Kết thúc ngày ${_date(expiresAt)}'
                          : 'Gia hạn trước ngày ${_date(expiresAt)}',
                      style: AppTheme.bodyFont(
                        fontSize: 13,
                        color: Colors.grey,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 22),
          Text(
            'HẠN MỨC CHU KỲ NÀY',
            style: AppTheme.monoFont(
              fontSize: 11,
              letterSpacing: 1.4,
              color: Colors.grey,
            ),
          ),
          const SizedBox(height: 12),
          _QuotaBar(
            label: 'Dự án đã lưu',
            used: usage.projectsCount,
            limit: usage.maxProjects,
          ),
          _QuotaBar(
            label: 'AI Credits (tách nền)',
            used: usage.aiCreditsUsed,
            limit: usage.aiCreditsLimit,
          ),
          _QuotaBar(
            label: 'Lượt xuất file',
            used: usage.exportsCount,
            limit: usage.maxExportsPerMonth,
          ),
          const SizedBox(height: 10),
          // The backend has no per-cycle "scans used" counter yet, so the
          // allowance is shown on its own rather than as a used/total ratio.
          Card(
            child: ListTile(
              leading: const Icon(
                Icons.center_focus_strong,
                color: AppTheme.orange,
              ),
              title: const Text(
                'Lượt quét 3D mỗi chu kỳ',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(
                usage.maxScansPerCycle == null
                    ? 'Không giới hạn'
                    : '${usage.maxScansPerCycle} lượt',
                style: AppTheme.bodyFont(fontSize: 13, color: Colors.grey),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _date(DateTime value) =>
      '${value.day.toString().padLeft(2, '0')}/'
      '${value.month.toString().padLeft(2, '0')}/${value.year}';
}

class _QuotaBar extends StatelessWidget {
  const _QuotaBar({required this.label, required this.used, this.limit});

  final String label;
  final int used;
  final int? limit;

  @override
  Widget build(BuildContext context) {
    final cap = limit;
    // A null limit is "unlimited" on this plan, not zero.
    final fraction = cap == null || cap == 0
        ? null
        : (used / cap).clamp(0.0, 1.0).toDouble();

    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                cap == null ? '$used · không giới hạn' : '$used/$cap',
                style: AppTheme.monoFont(fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: fraction ?? 0,
              minHeight: 8,
              backgroundColor:
                  Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.08),
              valueColor: AlwaysStoppedAnimation(
                fraction != null && fraction >= 1
                    ? AppTheme.crimson
                    : AppTheme.orange,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
