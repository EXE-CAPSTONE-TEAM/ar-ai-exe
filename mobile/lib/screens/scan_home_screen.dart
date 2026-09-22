import 'package:flutter/material.dart';

import '../app/app_theme.dart';
import '../models/account.dart';
import '../services/api_exception.dart';
import '../services/backend_api.dart';
import '../widgets/scan_hero_card.dart';
import 'auth_screen.dart';
import 'plan_usage_screen.dart';
import 'scan_setup_screen.dart';

class ScanHomeScreen extends StatefulWidget {
  const ScanHomeScreen({
    this.isGuest = false,
    this.onRequireAuth,
    this.onOpenPlans,
    super.key,
  });

  final bool isGuest;
  final VoidCallback? onRequireAuth;
  final VoidCallback? onOpenPlans;

  @override
  State<ScanHomeScreen> createState() => _ScanHomeScreenState();
}

class _ScanHomeScreenState extends State<ScanHomeScreen> {
  BackendApi get _api => BackendApi.shared;

  AccountUsage? _usage;
  bool _loadingUsage = false;

  @override
  void initState() {
    super.initState();
    if (!widget.isGuest) {
      _loadUsage();
    }
  }

  /// BR-92: quota figures come from the plan table via the backend, never from
  /// a literal in the UI.
  Future<void> _loadUsage() async {
    setState(() => _loadingUsage = true);
    try {
      final usage = await _api.getUsage();
      if (!mounted) return;
      setState(() {
        _usage = usage;
        _loadingUsage = false;
      });
    } on ApiException {
      // The badge is informational; a failure leaves it in its loading-less
      // unknown state rather than blocking the scan entry point.
      if (!mounted) return;
      setState(() => _loadingUsage = false);
    }
  }

  /// Text for the quota chip. There is no per-cycle "scans used" counter on
  /// the backend, so this shows the plan's allowance, not a used/total ratio.
  String get _quotaLabel {
    if (widget.isGuest) {
      return 'KHÁCH: 0 LƯỢT QUÉT';
    }
    if (_loadingUsage) {
      return 'ĐANG TẢI…';
    }
    final usage = _usage;
    if (usage == null) {
      return 'CHƯA RÕ HẠN MỨC';
    }
    final scans = usage.maxScansPerCycle;
    if (scans == null) {
      return '${usage.tierLabel}: KHÔNG GIỚI HẠN';
    }
    return '${usage.tierLabel}: $scans LƯỢT QUÉT';
  }

  /// BR-99: Free has no scan allowance, so the CTA sells the upgrade instead
  /// of starting a flow the backend will reject.
  bool get _canScan {
    if (widget.isGuest) {
      return false;
    }
    final scans = _usage?.maxScansPerCycle;
    return scans == null || scans > 0;
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bottomInset = MediaQuery.of(context).padding.bottom;

    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: LayoutBuilder(
            builder: (context, constraints) {
              return SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: EdgeInsets.fromLTRB(20, 16, 20, 108 + bottomInset),
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight - (108 + bottomInset) - 16,
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Header HUD Deck
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              // Eyebrow Tag (Double-Bezel micro badge)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: AppTheme.orange.withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(999),
                                  border: Border.all(
                                    color: AppTheme.orange.withValues(alpha: 0.35),
                                    width: 1,
                                  ),
                                ),
                                child: Text(
                                  'AI 3D SCANNER · 360°',
                                  style: AppTheme.monoFont(
                                    color: AppTheme.orange,
                                    letterSpacing: 1.4,
                                    fontSize: 10,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              // Quota Badge — Flexible so a longer tier or
                              // locale ellipsizes instead of overflowing.
                              Flexible(
                                fit: FlexFit.loose,
                                child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: widget.isGuest
                                      ? AppTheme.statusScanned.withValues(alpha: 0.12)
                                      : AppTheme.orange.withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(999),
                                  border: Border.all(
                                    color: widget.isGuest
                                        ? AppTheme.statusScanned.withValues(alpha: 0.35)
                                        : AppTheme.orange.withValues(alpha: 0.35),
                                    width: 1,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    CircleAvatar(
                                      radius: 3.5,
                                      backgroundColor: widget.isGuest
                                          ? AppTheme.statusScanned
                                          : AppTheme.orange,
                                    ),
                                    const SizedBox(width: 6),
                                      Flexible(
                                        child: Text(
                                          _quotaLabel,
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: AppTheme.monoFont(
                                            fontSize: 10,
                                            fontWeight: FontWeight.w700,
                                            letterSpacing: 0.5,
                                            color: widget.isGuest
                                                ? AppTheme.statusScanned
                                                : AppTheme.orange,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            'Quét Giày 3D',
                            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                                  fontWeight: FontWeight.w900,
                                  letterSpacing: -0.5,
                                  height: 1.1,
                                ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Đặt giày vào tâm ngắm để AI nhận diện phôi và tạo lưới 3D.',
                            style: AppTheme.bodyFont(
                              fontSize: 13,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurface
                                  .withValues(alpha: 0.65),
                              height: 1.35,
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 16),

                      // Viewfinder Card
                      const ScanHeroCard(),

                      const SizedBox(height: 20),

                      // Action Deck (Capsule Button-in-Button)
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          DecoratedBox(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(32),
                              gradient: const LinearGradient(
                                colors: [AppTheme.orange, Color(0xFFFF3E24)],
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: AppTheme.orange.withValues(alpha: isDark ? 0.35 : 0.25),
                                  blurRadius: 24,
                                  offset: const Offset(0, 8),
                                ),
                              ],
                            ),
                            child: Material(
                              color: Colors.transparent,
                              child: InkWell(
                                borderRadius: BorderRadius.circular(32),
                                onTap: _openSetup,
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 24,
                                    vertical: 14,
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Flexible(
                                        child: Text(
                                          _canScan
                                              ? 'BẮT ĐẦU QUÉT 360°'
                                              : 'NÂNG CẤP ĐỂ QUÉT 360°',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          textAlign: TextAlign.center,
                                          style: AppTheme.headingFont(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w900,
                                            letterSpacing: 1.2,
                                            color: Colors.black,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      Container(
                                        width: 34,
                                        height: 34,
                                        decoration: BoxDecoration(
                                          color: Colors.black.withValues(alpha: 0.16),
                                          shape: BoxShape.circle,
                                        ),
                                        child: const Icon(
                                          Icons.center_focus_strong,
                                          color: Colors.black,
                                          size: 19,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 10),
                          Text(
                            _canScan
                                ? 'Xoay quanh đôi giày trong 30-60 giây · Chuẩn GLB'
                                : 'Chế độ khách & gói Free chưa có lượt quét · Cần Basic trở lên',
                            textAlign: TextAlign.center,
                            style: AppTheme.monoFont(
                              fontSize: 11,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurface
                                  .withValues(alpha: 0.5),
                              letterSpacing: 0.4,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  void _openSetup() {
    if (!_canScan) {
      _showGuestUpgradeSheet();
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ScanSetupScreen(api: _api)),
    );
  }

  /// BR-41 (guest) and BR-99 (Free has 0 scans): explain the boundary instead
  /// of letting bootstrap fail with an auth or quota error.
  void _showGuestUpgradeSheet() {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.fromLTRB(24, 4, 24, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.lock_outline, color: AppTheme.orange),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Quét 3D cần tài khoản có gói',
                    style: AppTheme.headingFont(
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              widget.isGuest
                  ? 'Chế độ khách cho bạn xem trước phôi giày demo và các công '
                      'cụ cơ bản. Mỗi lượt dựng lưới 3D tốn chi phí xử lý, nên '
                      'tính năng quét đi kèm gói Basic hoặc Pro.'
                  : 'Gói hiện tại của bạn chưa có lượt quét 3D nào trong chu '
                      'kỳ này. Nâng cấp lên Basic hoặc Pro để mở khóa tính '
                      'năng quét.',
              style: AppTheme.bodyFont(fontSize: 13.5, height: 1.45),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () {
                  Navigator.of(sheetContext).pop();
                  if (widget.isGuest) {
                    if (widget.onRequireAuth != null) {
                      widget.onRequireAuth!();
                    } else {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const AuthScreen(initialRegister: true),
                        ),
                      );
                    }
                  } else {
                    if (widget.onOpenPlans != null) {
                      widget.onOpenPlans!();
                    } else {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => PlanUsageScreen(api: _api),
                        ),
                      );
                    }
                  }
                },
                icon: Icon(
                  widget.isGuest ? Icons.person_add_alt : Icons.upgrade,
                ),
                label: Text(
                  widget.isGuest ? 'ĐĂNG KÝ TÀI KHOẢN' : 'XEM GÓI CƯỚC',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
