import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

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
  List<BillingPlan> _plans = [];
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
      final usage = await widget.api.getUsage();
      final subscription = await widget.api.getSubscription();
      List<BillingPlan> plans = [];
      try {
        plans = await widget.api.listPlans();
      } catch (_) {
        // Best effort for plan catalog
      }
      if (!mounted) return;
      setState(() {
        _usage = usage;
        _subscription = subscription;
        _plans = plans;
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Lỗi kết nối: $e';
        _loading = false;
      });
    }
  }

  Future<void> _startCheckout(BillingPlan plan) async {
    String selectedCycle = 'monthly';
    String selectedGateway = 'payos';
    bool checkingOut = false;
    String? checkoutError;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetCtx) {
        return StatefulBuilder(
          builder: (ctx, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 24,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Text(
                        'Nâng cấp gói ${plan.tierLabel}',
                        style: AppTheme.headingFont(
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => Navigator.of(sheetCtx).pop(),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Giá: ${plan.formattedPrice} / tháng',
                    style: const TextStyle(
                      color: AppTheme.orange,
                      fontWeight: FontWeight.w800,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'CHU KỲ THANH TOÁN',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 1.2),
                  ),
                  const SizedBox(height: 8),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'monthly', label: Text('Theo tháng')),
                      ButtonSegment(value: 'yearly', label: Text('Theo năm (-15%)')),
                    ],
                    selected: {selectedCycle},
                    onSelectionChanged: checkingOut
                        ? null
                        : (vals) => setModalState(() => selectedCycle = vals.first),
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'CỔNG THANH TOÁN',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 1.2),
                  ),
                  InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: checkingOut
                        ? null
                        : () => setModalState(() => selectedGateway = 'payos'),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: selectedGateway == 'payos'
                              ? AppTheme.orange
                              : Colors.grey.withValues(alpha: 0.3),
                          width: selectedGateway == 'payos' ? 2 : 1,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            selectedGateway == 'payos'
                                ? Icons.radio_button_checked
                                : Icons.radio_button_off,
                            color: selectedGateway == 'payos'
                                ? AppTheme.orange
                                : Colors.grey,
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'PayOS (Chuyển khoản VietQR nhanh)',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                  ),
                                ),
                                SizedBox(height: 2),
                                Text(
                                  'Quét mã QR tự động từ tất cả app ngân hàng',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: checkingOut
                        ? null
                        : () => setModalState(() => selectedGateway = 'momo'),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: selectedGateway == 'momo'
                              ? AppTheme.orange
                              : Colors.grey.withValues(alpha: 0.3),
                          width: selectedGateway == 'momo' ? 2 : 1,
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            selectedGateway == 'momo'
                                ? Icons.radio_button_checked
                                : Icons.radio_button_off,
                            color: selectedGateway == 'momo'
                                ? AppTheme.orange
                                : Colors.grey,
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Ví điện tử MoMo',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                  ),
                                ),
                                SizedBox(height: 2),
                                Text(
                                  'Thanh toán tức thì qua ứng dụng MoMo',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  if (checkoutError != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      checkoutError!,
                      style: const TextStyle(color: Colors.red, fontSize: 13),
                    ),
                  ],
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: checkingOut
                        ? null
                        : () async {
                            setModalState(() {
                              checkingOut = true;
                              checkoutError = null;
                            });
                            try {
                              final checkoutUrl = await widget.api.createCheckoutSession(
                                tier: plan.tier,
                                billingCycle: selectedCycle,
                                gateway: selectedGateway,
                              );
                              if (checkoutUrl.isEmpty) {
                                throw const ApiException(
                                  message: 'Không lấy được đường link thanh toán.',
                                );
                              }

                              if (sheetCtx.mounted) {
                                Navigator.of(sheetCtx).pop();
                              }

                              // Open in external browser / banking app
                              await launchUrl(
                                Uri.parse(checkoutUrl),
                                mode: LaunchMode.externalApplication,
                              );

                              // Show in-app payment wait confirmation sheet
                              if (mounted) {
                                _showPaymentAwaitingModal();
                              }
                            } on ApiException catch (e) {
                              setModalState(() {
                                checkingOut = false;
                                checkoutError = e.message;
                              });
                            } catch (e) {
                              setModalState(() {
                                checkingOut = false;
                                checkoutError = 'Lỗi khởi tạo thanh toán: $e';
                              });
                            }
                          },
                    child: checkingOut
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('Tiến hành thanh toán'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  void _showPaymentAwaitingModal() {
    showModalBottomSheet<void>(
      context: context,
      isDismissible: false,
      enableDrag: false,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppTheme.orange.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.payment, color: AppTheme.orange, size: 32),
              ),
              const SizedBox(height: 16),
              Text(
                'Đang chờ thanh toán',
                style: AppTheme.headingFont(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              const Text(
                'Cổng thanh toán đã được mở trên trình duyệt. Sau khi hoàn tất chuyển khoản, bấm nút bên dưới để làm mới hạn mức tài khoản.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, height: 1.4, color: Colors.grey),
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () {
                  Navigator.of(ctx).pop();
                  _load();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Đang cập nhật hạn mức mới...')),
                  );
                },
                child: const Text('Tôi đã chuyển khoản thành công'),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('Đóng'),
              ),
            ],
          ),
        );
      },
    );
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

          // Available Plans Catalog from GET /api/v1/plans
          if (_plans.isNotEmpty) ...[
            const SizedBox(height: 28),
            Text(
              'CÁC GÓI NÂNG CẤP',
              style: AppTheme.monoFont(
                fontSize: 11,
                letterSpacing: 1.4,
                color: Colors.grey,
              ),
            ),
            const SizedBox(height: 14),
            ..._plans.map((plan) {
              final isCurrent = plan.tier.toLowerCase() == usage.tier.toLowerCase();
              return Card(
                margin: const EdgeInsets.only(bottom: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                  side: BorderSide(
                    color: isCurrent
                        ? AppTheme.orange
                        : Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
                    width: isCurrent ? 2 : 1,
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            plan.tierLabel,
                            style: AppTheme.headingFont(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const Spacer(),
                          Text(
                            plan.formattedPrice,
                            style: const TextStyle(
                              color: AppTheme.orange,
                              fontWeight: FontWeight.w900,
                              fontSize: 16,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        '• Dự án: ${plan.maxProjects == null ? 'Không giới hạn' : '${plan.maxProjects} dự án'}\n'
                        '• Xuất file: ${plan.maxExportsPerMonth == null ? 'Không giới hạn' : '${plan.maxExportsPerMonth} lượt/tháng'}\n'
                        '• AI Credits: ${plan.maxAiCreditsPerCycle == null ? 'Không giới hạn' : '${plan.maxAiCreditsPerCycle} credits'}\n'
                        '• Quét 3D: ${plan.maxScansPerCycle == null ? 'Không giới hạn' : '${plan.maxScansPerCycle} lượt/chu kỳ'}',
                        style: AppTheme.bodyFont(fontSize: 13, height: 1.5),
                      ),
                      const SizedBox(height: 16),
                      if (isCurrent)
                        const OutlinedButton(
                          onPressed: null,
                          child: Text('Gói hiện tại của bạn'),
                        )
                      else
                        FilledButton(
                          onPressed: () => _startCheckout(plan),
                          child: Text('Nâng cấp lên ${plan.tierLabel}'),
                        ),
                    ],
                  ),
                ),
              );
            }),
          ],
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
