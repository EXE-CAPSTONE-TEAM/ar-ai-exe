import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/app_config.dart';
import '../models/account.dart';
import '../models/template_models.dart';
import '../screens/auth_screen.dart';
import '../screens/my_designs_screen.dart';
import '../screens/plan_usage_screen.dart';
import '../screens/scan_home_screen.dart';
import '../screens/user_manual_screen.dart';
import '../services/api_exception.dart';
import '../services/backend_api.dart';
import 'app_theme.dart';

/// Bottom-nav tabs, in display order.
///
/// The app opens on [scan]: capturing a shoe is what the mobile app is for
/// (BR-42 keeps editing on Web/Desktop), so scanning is the landing tab rather
/// than Explore. Reordering this enum reorders the bar and keeps the default
/// pointing at the same tab.
enum HomeTab { explore, scan, manual, profile }

class AppShell extends StatefulWidget {
  const AppShell({
    required this.themeMode,
    required this.onThemeModeChanged,
    this.isGuest = false,
    super.key,
  });

  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;
  final bool isGuest;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  static const _initialTab = HomeTab.scan;

  HomeTab _tab = _initialTab;

  @override
  void initState() {
    super.initState();
    BackendApi.shared.sessionExpired.addListener(_onSessionExpired);
  }

  @override
  void dispose() {
    BackendApi.shared.sessionExpired.removeListener(_onSessionExpired);
    super.dispose();
  }

  /// Access tokens live 15 minutes (NFR-SEC-11) and the client refreshes them
  /// transparently; this only fires when the refresh itself was rejected.
  void _onSessionExpired() {
    if (!mounted || !BackendApi.shared.sessionExpired.value) {
      return;
    }
    _returnToSignIn(
      message: 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
    );
  }

  void _openAuth({bool register = true}) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AuthScreen(
          themeMode: widget.themeMode,
          onThemeModeChanged: widget.onThemeModeChanged,
          initialRegister: register,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).padding.bottom;
    final pages = [
      _ExploreTab(
        isGuest: widget.isGuest,
        onRequireAuth: () => _openAuth(register: true),
      ),
      ScanHomeScreen(
        isGuest: widget.isGuest,
        onRequireAuth: () => _openAuth(register: true),
        onOpenPlans: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => PlanUsageScreen(api: BackendApi.shared)),
        ),
      ),
      const UserManualScreen(),
      _ProfileTab(
        themeMode: widget.themeMode,
        onThemeModeChanged: widget.onThemeModeChanged,
        onLogout: _logout,
        isGuest: widget.isGuest,
        onRequireAuth: () => _openAuth(register: true),
      ),
    ];

    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(child: pages[_tab.index]),
          Positioned(
            left: 14,
            right: 14,
            bottom: bottomInset > 0 ? bottomInset + 8 : 16,
            child: _PillBottomNav(
              index: _tab.index,
              onChanged: (value) =>
                  setState(() => _tab = HomeTab.values[value]),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _logout() async {
    await BackendApi.shared.logout();
    if (!mounted) {
      return;
    }
    _returnToSignIn();
  }

  void _returnToSignIn({String? message}) {
    if (message != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
    }
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(
        builder: (_) => AuthScreen(
          themeMode: widget.themeMode,
          onThemeModeChanged: widget.onThemeModeChanged,
        ),
      ),
      (_) => false,
    );
  }
}

class _TabScaffold extends StatelessWidget {
  const _TabScaffold({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).padding.bottom;
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: Padding(
            padding: EdgeInsets.fromLTRB(18, 16, 18, 108 + bottomInset),
            child: child,
          ),
        ),
      ),
    );
  }
}

class _PillBottomNav extends StatelessWidget {
  const _PillBottomNav({
    required this.index,
    required this.onChanged,
  });

  final int index;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 400),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(32),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.6 : 0.14),
                blurRadius: 32,
                offset: const Offset(0, 16),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(32),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xD8141417)
                      : const Color(0xF2FFFFFF),
                  borderRadius: BorderRadius.circular(32),
                  border: Border.all(
                    color: isDark
                        ? const Color(0x33FF5A36)
                        : const Color(0xFFFFD5C4),
                    width: 1.2,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    Expanded(
                      child: _NavItem(
                        selected: index == 0,
                        icon: Icons.explore_outlined,
                        label: 'Khám phá',
                        onTap: () => onChanged(0),
                      ),
                    ),
                    Expanded(
                      child: _NavItem(
                        selected: index == 1,
                        icon: Icons.center_focus_strong,
                        label: 'Quét AI',
                        onTap: () => onChanged(1),
                      ),
                    ),
                    Expanded(
                      child: _NavItem(
                        selected: index == 2,
                        icon: Icons.menu_book_outlined,
                        label: 'Cẩm nang',
                        onTap: () => onChanged(2),
                      ),
                    ),
                    Expanded(
                      child: _NavItem(
                        selected: index == 3,
                        icon: Icons.person_outline,
                        label: 'Cá nhân',
                        onTap: () => onChanged(3),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.selected,
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final bool selected;
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final color = selected
        ? AppTheme.orange
        : (isDark ? const Color(0xFF8E8E93) : const Color(0xFF757575));
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              curve: Curves.easeOutCubic,
              width: selected ? 46 : 38,
              height: selected ? 34 : 30,
              decoration: BoxDecoration(
                color: selected
                    ? AppTheme.orange.withValues(alpha: 0.18)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(17),
              ),
              child: Icon(
                icon,
                color: selected ? AppTheme.orange : color,
                size: selected ? 22 : 20,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: selected
                    ? Theme.of(context).colorScheme.onSurface
                    : color,
                fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                fontSize: 11,
                letterSpacing: selected ? 0.2 : 0,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Opens the KusShoes web app in the device browser.
///
/// Only the site root is linked for now - the deployment has no SPA rewrite,
/// so sub-paths answer 404 (see [AppConfig.webAppUrl]).
Future<void> _openWebApp(BuildContext context, {String path = ''}) async {
  final messenger = ScaffoldMessenger.of(context);
  final uri = Uri.parse(AppConfig.webUrl(path));
  final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
  if (!opened) {
    messenger.showSnackBar(
      SnackBar(content: Text('Không mở được trình duyệt. Truy cập $uri')),
    );
  }
}

class _ExploreTab extends StatefulWidget {
  const _ExploreTab({
    required this.isGuest,
    this.onRequireAuth,
  });

  final bool isGuest;
  final VoidCallback? onRequireAuth;

  @override
  State<_ExploreTab> createState() => _ExploreTabState();
}

class _ExploreTabState extends State<_ExploreTab> {
  final BackendApi _api = BackendApi.shared;
  List<ShoeTemplate> _templates = [];
  bool _loading = true;
  String? _selectedCategory;

  static const _categories = [
    {'key': null, 'label': 'Tất cả'},
    {'key': 'sneaker', 'label': 'Sneaker'},
    {'key': 'running', 'label': 'Giày chạy'},
    {'key': 'boot', 'label': 'Boot'},
    {'key': 'loafer', 'label': 'Loafer'},
  ];

  @override
  void initState() {
    super.initState();
    _loadTemplates();
  }

  Future<void> _loadTemplates() async {
    setState(() => _loading = true);
    try {
      final list = await _api.listTemplates(category: _selectedCategory);
      if (!mounted) return;
      setState(() {
        _templates = list;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  Future<void> _onSelectTemplate(ShoeTemplate template) async {
    if (widget.isGuest) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Vui lòng đăng ký tài khoản để áp dụng phôi mẫu.'),
          action: SnackBarAction(
            label: 'ĐĂNG KÝ',
            textColor: AppTheme.orange,
            onPressed: () => widget.onRequireAuth?.call(),
          ),
        ),
      );
      return;
    }

    bool creating = false;
    await showModalBottomSheet<void>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetCtx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Container(
                    width: 50,
                    height: 50,
                    decoration: BoxDecoration(
                      color: AppTheme.orange.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.view_in_ar_outlined, color: AppTheme.orange, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          template.name,
                          style: AppTheme.headingFont(fontSize: 18, fontWeight: FontWeight.w900),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          template.categoryLabel,
                          style: const TextStyle(color: AppTheme.orange, fontSize: 13, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (template.description != null && template.description!.isNotEmpty)
                Text(
                  template.description!,
                  style: AppTheme.bodyFont(fontSize: 13.5, height: 1.4),
                )
              else
                const Text(
                  'Phôi giày mẫu 3D chuẩn tỉ lệ thực tế, sẵn sàng tùy biến màu sắc và tem decal trên Kus Studio Web.',
                  style: TextStyle(fontSize: 13, color: Colors.grey, height: 1.4),
                ),
              const SizedBox(height: 16),
              Row(
                children: [
                  _Tag('${template.layerCount} họa tiết', filled: true),
                  const SizedBox(width: 8),
                  _Tag('${template.useCount} lượt dùng', filled: false),
                ],
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                icon: const Icon(Icons.palette_outlined),
                label: creating
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('DÙNG MẪU NÀY THIẾT KẾ TRÊN WEB'),
                onPressed: creating
                    ? null
                    : () async {
                        setSheetState(() => creating = true);
                        try {
                          final project = await _api.createProject(name: '${template.name} Custom');
                          await _api.applyTemplate(projectId: project.id, templateId: template.id);
                          if (sheetCtx.mounted) Navigator.of(sheetCtx).pop();

                          await launchUrl(
                            Uri.parse(project.editorUrl),
                            mode: LaunchMode.externalApplication,
                          );
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Đã tạo dự án và mở Kus Studio Web!'),
                                backgroundColor: Colors.green,
                              ),
                            );
                          }
                        } catch (e) {
                          setSheetState(() => creating = false);
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text('Lỗi áp dụng mẫu: $e'), backgroundColor: Colors.red),
                            );
                          }
                        }
                      },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return _TabScaffold(
      child: ListView(
        children: [
          const _MiniBrand(),
          const SizedBox(height: 20),
          Text.rich(
            TextSpan(
              children: [
                const TextSpan(text: 'AI-Powered\n'),
                TextSpan(
                  text: '3D Shoe\n',
                  style:
                      TextStyle(color: Theme.of(context).colorScheme.primary),
                ),
                const TextSpan(text: 'Customization'),
              ],
            ),
            style: Theme.of(context).textTheme.displaySmall?.copyWith(
                  height: 0.98,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 12),
          Text(
            'Quét đôi giày thật bằng camera AI 360°, tùy biến sticker & vẽ tay trên Kus Studio Web và xuất file 3D GLB/OBJ chuẩn.',
            style: AppTheme.bodyFont(
              fontSize: 14,
              color: Theme.of(context)
                  .colorScheme
                  .onSurface
                  .withValues(alpha: 0.72),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 22),
          FilledButton.icon(
            onPressed: () => _openWebApp(context),
            icon: const Icon(Icons.open_in_browser),
            label: const Text('MỞ KUS STUDIO TRÊN WEB'),
          ),
          const SizedBox(height: 28),

          // Template Catalog Section
          Row(
            children: [
              const Expanded(child: _SectionLabel('PHÔI GIÀY MẪU CÓ SẴN')),
              if (_loading)
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: _categories.map((cat) {
                final selected = _selectedCategory == cat['key'];
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(cat['label']!),
                    selected: selected,
                    onSelected: (val) {
                      setState(() => _selectedCategory = val ? cat['key'] : null);
                      _loadTemplates();
                    },
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 14),

          if (!_loading && _templates.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Center(
                child: Text(
                  'Đang cập nhật thêm các mẫu giày 3D mới.',
                  style: TextStyle(color: Colors.grey, fontSize: 13),
                ),
              ),
            )
          else if (_templates.isNotEmpty)
            SizedBox(
              height: 170,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _templates.length,
                itemBuilder: (context, idx) {
                  final t = _templates[idx];
                  return Container(
                    width: 200,
                    margin: const EdgeInsets.only(right: 14),
                    child: Card(
                      clipBehavior: Clip.antiAlias,
                      child: InkWell(
                        onTap: () => _onSelectTemplate(t),
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  CircleAvatar(
                                    radius: 18,
                                    backgroundColor: AppTheme.orange.withValues(alpha: 0.15),
                                    child: const Icon(Icons.view_in_ar, size: 20, color: AppTheme.orange),
                                  ),
                                  const Spacer(),
                                  _Tag(t.categoryLabel, filled: false),
                                ],
                              ),
                              const Spacer(),
                              Text(
                                t.name,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${t.layerCount} họa tiết · ${t.useCount} lượt dùng',
                                style: const TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),

          const SizedBox(height: 30),
          const _SectionLabel('TÍNH NĂNG NỔI BẬT'),
          const SizedBox(height: 14),
          const _FeatureGrid(),
          const SizedBox(height: 24),
          const Row(
            children: [
              Expanded(child: _SectionLabel('LỘ TRÌNH PHÁT TRIỂN')),
              _Tag('Sắp ra mắt', filled: false),
            ],
          ),
          const SizedBox(height: 12),
          const _RoadmapTile(
            icon: Icons.storefront_outlined,
            title: 'KusShoe Store',
            badge: 'Phase 2',
            body: 'Mua phụ kiện giày, dây giày custom, charm trang trí.',
          ),
          const _RoadmapTile(
            icon: Icons.water_drop_outlined,
            title: 'Mạng Lưới Sneaker Spa',
            badge: 'Liên kết',
            body:
                'Liên kết đối tác vệ sinh giày chuyên sâu, khử mùi và repaint.',
          ),
          const _RoadmapTile(
            icon: Icons.diamond_outlined,
            title: 'Limited Drops',
            badge: 'Ý tưởng',
            body:
                'Các bộ sưu tập giày số giới hạn do AI và nghệ sĩ hợp tác.',
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Theme.of(context).brightness == Brightness.dark
                  ? Colors.white.withValues(alpha: 0.03)
                  : AppTheme.orange.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: Theme.of(context).brightness == Brightness.dark
                    ? Colors.white.withValues(alpha: 0.08)
                    : AppTheme.orange.withValues(alpha: 0.15),
              ),
            ),
            child: Text(
              'KusShoes tập trung tối đa vào trải nghiệm Quét 3D, Studio tùy biến Web và Xuất file GLB chuẩn cho xưởng gia công.',
              style: AppTheme.bodyFont(
                fontSize: 12,
                color: Theme.of(context)
                    .colorScheme
                    .onSurface
                    .withValues(alpha: 0.6),
                height: 1.4,
              ),
            ),
          ),
          const SizedBox(height: 12),
          const _WebsiteTile(),
        ],
      ),
    );
  }
}

class _MiniBrand extends StatelessWidget {
  const _MiniBrand();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: AppTheme.orange.withValues(alpha: 0.2),
                blurRadius: 8,
              ),
            ],
          ),
          padding: const EdgeInsets.all(4),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Image.asset(
              'assets/images/logo.png',
              fit: BoxFit.contain,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'KusShoes',
              style: AppTheme.headingFont(
                fontSize: 18,
                fontWeight: FontWeight.w900,
              ),
            ),
            Text(
              'Shape your shoes, show your style',
              style: AppTheme.bodyFont(fontSize: 11, color: Colors.grey),
            ),
          ],
        ),
      ],
    );
  }
}

class _FeatureGrid extends StatelessWidget {
  const _FeatureGrid();

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 1.15,
      children: const [
        _FeatureCard(
            icon: Icons.center_focus_strong,
            title: 'Quét Giày AI 360°',
            body: 'Dựng lưới 3D từ video camera thật.'),
        _FeatureCard(
            icon: Icons.layers_outlined,
            title: 'Thư Viện Phôi Chuẩn',
            body: 'Phôi sneaker, running, boot sẵn sàng.'),
        _FeatureCard(
            icon: Icons.auto_fix_high,
            title: 'Kus Studio Web',
            body: 'Dán decal, vẽ tay, ký tên trên web.'),
        _FeatureCard(
            icon: Icons.ios_share,
            title: 'Xuất File & Nghệ Nhân',
            body: 'Xuất file GLB & gửi link thợ vẽ.'),
      ],
    );
  }
}

class _FeatureCard extends StatelessWidget {
  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _IconBubble(icon: icon),
            const Spacer(),
            Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
            const SizedBox(height: 6),
            Text(
              body,
              style: TextStyle(
                color: Theme.of(context)
                    .colorScheme
                    .onSurface
                    .withValues(alpha: 0.66),
                fontSize: 12,
                height: 1.3,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RoadmapTile extends StatelessWidget {
  const _RoadmapTile({
    required this.icon,
    required this.title,
    required this.badge,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String badge;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        leading: _IconBubble(icon: icon, muted: true),
        title: Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 8,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
            _Tag(badge),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(body),
        ),
      ),
    );
  }
}

class _WebsiteTile extends StatelessWidget {
  const _WebsiteTile();

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.08),
      child: ListTile(
        leading: const _IconBubble(icon: Icons.open_in_new),
        title: const Text('Truy cập KusShoes Studio',
            style: TextStyle(fontWeight: FontWeight.w900)),
        subtitle: const Text('Mở 3D Editor trên web, xem thư viện phôi & cộng đồng'),
        trailing: const Icon(Icons.open_in_new, size: 18),
        onTap: () => _openWebApp(context),
      ),
    );
  }
}


class _ProfileTab extends StatefulWidget {
  const _ProfileTab({
    required this.themeMode,
    required this.onThemeModeChanged,
    required this.onLogout,
    this.isGuest = false,
    this.onRequireAuth,
  });

  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;
  final Future<void> Function() onLogout;
  final bool isGuest;
  final VoidCallback? onRequireAuth;

  @override
  State<_ProfileTab> createState() => _ProfileTabState();
}

class _ProfileTabState extends State<_ProfileTab> {
  BackendApi get _api => BackendApi.shared;

  UserProfile? _profile;
  AccountUsage? _usage;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (!widget.isGuest) {
      _load();
    }
  }

  /// SC-26: everything on this tab comes from the account endpoints. A guest
  /// session has no account to read, so it keeps the local-only view.
  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final profile = await _api.getProfile();
      final usage = await _api.getUsage();
      if (!mounted) return;
      setState(() {
        _profile = profile;
        _usage = usage;
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

  void _openMyDesigns() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => MyDesignsScreen(api: _api)),
    );
  }

  void _openPlanUsage() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => PlanUsageScreen(api: _api)),
    );
  }

  void _requireAccount() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Đăng ký tài khoản để dùng mục này.'),
        action: SnackBarAction(
          label: 'ĐĂNG KÝ',
          textColor: AppTheme.orange,
          onPressed: () => widget.onRequireAuth?.call(),
        ),
      ),
    );
  }

  Future<void> _pickAndUploadAvatar() async {
    try {
      final picker = ImagePicker();
      final photo = await picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 800,
        maxHeight: 800,
        imageQuality: 85,
      );
      if (photo == null || !mounted) return;

      final bytes = await photo.readAsBytes();
      final ext = photo.name.split('.').last.toLowerCase();
      final contentType = ext == 'png' ? 'image/png' : 'image/jpeg';

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đang tải ảnh đại diện lên...')),
      );

      final uploadInfo = await _api.requestAvatarUpload(
        contentType: contentType,
        fileSize: bytes.length,
      );
      final uploadUrl = uploadInfo['upload_url'];
      if (uploadUrl != null && uploadUrl.isNotEmpty) {
        await _api.uploadAvatarBytes(
          uploadUrl: uploadUrl,
          bytes: bytes,
          contentType: contentType,
        );
        await _load();
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Cập nhật ảnh đại diện thành công!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), backgroundColor: Colors.red),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Lỗi tải ảnh: $e'), backgroundColor: Colors.red),
      );
    }
  }

  Future<void> _editProfile() async {
    final profile = _profile;
    final firstNameController =
        TextEditingController(text: profile?.firstName ?? '');
    final lastNameController =
        TextEditingController(text: profile?.lastName ?? '');
    final phoneController =
        TextEditingController(text: profile?.phoneNumber ?? '');

    final updated = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Chỉnh sửa thông tin cá nhân'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: lastNameController,
                decoration: const InputDecoration(labelText: 'Họ và tên đệm'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: firstNameController,
                decoration: const InputDecoration(labelText: 'Tên'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(labelText: 'Số điện thoại'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Lưu'),
          ),
        ],
      ),
    );

    if (updated != true || !mounted) return;

    try {
      await _api.updateProfile(
        firstName: firstNameController.text.trim(),
        lastName: lastNameController.text.trim(),
        phoneNumber: phoneController.text.trim(),
      );
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cập nhật thông tin thành công!'),
          backgroundColor: Colors.green,
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), backgroundColor: Colors.red),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Lỗi: $e'), backgroundColor: Colors.red),
      );
    }
  }

  Future<void> _changePassword() async {
    final currentPassController = TextEditingController();
    final newPassController = TextEditingController();
    final confirmPassController = TextEditingController();
    String? dialogError;
    bool isChanging = false;

    await showDialog<void>(
      context: context,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Đổi mật khẩu'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: currentPassController,
                  obscureText: true,
                  decoration:
                      const InputDecoration(labelText: 'Mật khẩu hiện tại'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: newPassController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Mật khẩu mới (tối thiểu 6 ký tự)',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: confirmPassController,
                  obscureText: true,
                  decoration:
                      const InputDecoration(labelText: 'Xác nhận mật khẩu mới'),
                ),
                if (dialogError != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    dialogError!,
                    style: const TextStyle(color: Colors.red, fontSize: 12),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed:
                  isChanging ? null : () => Navigator.of(dialogCtx).pop(),
              child: const Text('Hủy'),
            ),
            FilledButton(
              onPressed: isChanging
                  ? null
                  : () async {
                      final curr = currentPassController.text;
                      final next = newPassController.text;
                      final confirm = confirmPassController.text;
                      if (curr.isEmpty || next.isEmpty) {
                        setDialogState(
                          () => dialogError = 'Vui lòng nhập đầy đủ thông tin',
                        );
                        return;
                      }
                      if (next.length < 6) {
                        setDialogState(
                          () => dialogError = 'Mật khẩu mới phải từ 6 ký tự',
                        );
                        return;
                      }
                      if (next != confirm) {
                        setDialogState(
                          () => dialogError = 'Xác nhận mật khẩu không khớp',
                        );
                        return;
                      }

                      setDialogState(() {
                        isChanging = true;
                        dialogError = null;
                      });

                      try {
                        await _api.changePassword(
                          currentPassword: curr,
                          newPassword: next,
                        );
                        if (dialogCtx.mounted) {
                          Navigator.of(dialogCtx).pop();
                        }
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Đổi mật khẩu thành công!'),
                              backgroundColor: Colors.green,
                            ),
                          );
                        }
                      } on ApiException catch (e) {
                        setDialogState(() {
                          isChanging = false;
                          dialogError = e.message;
                        });
                      } catch (e) {
                        setDialogState(() {
                          isChanging = false;
                          dialogError = 'Lỗi đổi mật khẩu: $e';
                        });
                      }
                    },
              child: isChanging
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Đổi mật khẩu'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submitFeedback() async {
    int rating = 5;
    final commentController = TextEditingController();
    bool isSending = false;
    String? error;

    await showDialog<void>(
      context: context,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Đánh giá & Góp ý ứng dụng'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Ý kiến của bạn giúp chúng tôi nâng cấp chất lượng tái tạo 3D đôi giày ngày một tốt hơn.',
                  style: TextStyle(fontSize: 13, color: Colors.grey),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(5, (index) {
                    final star = index + 1;
                    return IconButton(
                      icon: Icon(
                        star <= rating ? Icons.star : Icons.star_border,
                        color: Colors.amber,
                        size: 32,
                      ),
                      onPressed: () => setDialogState(() => rating = star),
                    );
                  }),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: commentController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: 'Nội dung góp ý (tùy chọn)',
                    hintText: 'Chia sẻ cảm nhận hoặc báo lỗi...',
                  ),
                ),
                if (error != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    error!,
                    style: const TextStyle(color: Colors.red, fontSize: 12),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed:
                  isSending ? null : () => Navigator.of(dialogCtx).pop(),
              child: const Text('Đóng'),
            ),
            FilledButton(
              onPressed: isSending
                  ? null
                  : () async {
                      setDialogState(() {
                        isSending = true;
                        error = null;
                      });
                      try {
                        await _api.submitFeedback(
                          rating: rating,
                          comment: commentController.text.trim(),
                        );
                        if (dialogCtx.mounted) {
                          Navigator.of(dialogCtx).pop();
                        }
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Cảm ơn bạn đã gửi đánh giá!'),
                              backgroundColor: Colors.green,
                            ),
                          );
                        }
                      } on ApiException catch (e) {
                        setDialogState(() {
                          isSending = false;
                          error = e.message;
                        });
                      } catch (e) {
                        setDialogState(() {
                          isSending = false;
                          error = 'Lỗi gửi đánh giá: $e';
                        });
                      }
                    },
              child: isSending
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Gửi đánh giá'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _deleteAccount() async {
    final passwordController = TextEditingController();
    String? error;
    bool isDeleting = false;

    await showDialog<void>(
      context: context,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('Xác nhận xóa tài khoản?'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'CẢNH BÁO: Toàn bộ thông tin cá nhân, các mẫu giày đã quét và các thiết kế của bạn sẽ bị xóa vĩnh viễn khỏi hệ thống KusShoes. Hành động này không thể hoàn tác.',
                  style: TextStyle(color: Colors.red, fontSize: 13, height: 1.4),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Vui lòng nhập mật khẩu đăng nhập để xác nhận xóa:',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: passwordController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Mật khẩu của bạn',
                    prefixIcon: Icon(Icons.lock_outline),
                  ),
                ),
                if (error != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    error!,
                    style: const TextStyle(color: Colors.red, fontSize: 12),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed:
                  isDeleting ? null : () => Navigator.of(dialogCtx).pop(),
              child: const Text('Hủy'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: Colors.red),
              onPressed: isDeleting
                  ? null
                  : () async {
                      final pass = passwordController.text;
                      if (pass.isEmpty) {
                        setDialogState(
                          () => error = 'Vui lòng nhập mật khẩu xác nhận',
                        );
                        return;
                      }
                      setDialogState(() {
                        isDeleting = true;
                        error = null;
                      });
                      try {
                        await _api.deleteAccount(password: pass);
                        if (dialogCtx.mounted) {
                          Navigator.of(dialogCtx).pop();
                        }
                        await widget.onLogout();
                      } on ApiException catch (e) {
                        setDialogState(() {
                          isDeleting = false;
                          error = e.message;
                        });
                      } catch (e) {
                        setDialogState(() {
                          isDeleting = false;
                          error = 'Lỗi xóa tài khoản: $e';
                        });
                      }
                    },
              child: isDeleting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Xóa tài khoản vĩnh viễn'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = widget.themeMode == ThemeMode.dark;
    final profile = _profile;
    final usage = _usage;

    return _TabScaffold(
      child: RefreshIndicator(
        onRefresh: widget.isGuest ? () async {} : _load,
        child: ListView(
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Hồ Sơ Cá Nhân',
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontWeight: FontWeight.w900),
                  ),
                ),
                IconButton.filledTonal(
                  onPressed: widget.onLogout,
                  iconSize: 18,
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.logout),
                  tooltip: 'Đăng xuất',
                ),
              ],
            ),
            const SizedBox(height: 14),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Row(
                  children: [
                    GestureDetector(
                      onTap: widget.isGuest ? null : _pickAndUploadAvatar,
                      child: Stack(
                        children: [
                          Container(
                            width: 58,
                            height: 58,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: AppTheme.orange.withValues(alpha: 0.8),
                                width: 2.5,
                              ),
                              color: AppTheme.orange.withValues(alpha: 0.1),
                              image: (profile?.avatarPath != null &&
                                      profile!.avatarPath!.isNotEmpty)
                                  ? DecorationImage(
                                      image: NetworkImage(profile.avatarPath!),
                                      fit: BoxFit.cover,
                                    )
                                  : null,
                            ),
                            child: (profile?.avatarPath == null ||
                                    profile!.avatarPath!.isEmpty)
                                ? Icon(
                                    widget.isGuest
                                        ? Icons.person_outline
                                        : Icons.account_circle,
                                    size: 30,
                                    color: AppTheme.orange,
                                  )
                                : null,
                          ),
                          if (!widget.isGuest)
                            Positioned(
                              bottom: 0,
                              right: 0,
                              child: Container(
                                padding: const EdgeInsets.all(4),
                                decoration: const BoxDecoration(
                                  color: AppTheme.orange,
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(
                                  Icons.camera_alt,
                                  size: 12,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.isGuest
                                ? 'Khách Trải Nghiệm'
                                : (profile?.displayName ??
                                    (_loading ? 'Đang tải…' : 'Tài khoản')),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTheme.headingFont(
                              fontSize: 16,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            widget.isGuest
                                ? 'Chế độ khách (chưa có lượt quét)'
                                : (profile?.email ?? ''),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTheme.bodyFont(
                              fontSize: 12,
                              color: Colors.grey,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            children: [
                              _Tag(
                                widget.isGuest
                                    ? 'Guest Trial'
                                    : 'Gói ${usage?.tierLabel ?? '—'}',
                                filled: true,
                              ),
                              if (!widget.isGuest &&
                                  profile?.accountCode.isNotEmpty == true)
                                _Tag(profile!.accountCode, filled: false),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),

            if (_error != null) ...[
              Card(
                color: Theme.of(context).colorScheme.errorContainer,
                child: ListTile(
                  leading: const Icon(Icons.cloud_off_outlined),
                  title: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onErrorContainer,
                      fontSize: 13,
                    ),
                  ),
                  trailing: TextButton(
                    onPressed: _load,
                    child: const Text('Thử lại'),
                  ),
                ),
              ),
              const SizedBox(height: 14),
            ],

            // Guest upsell callout
            if (widget.isGuest) ...[
              InkWell(
                onTap: widget.onRequireAuth,
                borderRadius: BorderRadius.circular(18),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        AppTheme.orange.withValues(alpha: 0.12),
                        AppTheme.crimson.withValues(alpha: 0.08),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(18),
                    border:
                        Border.all(color: AppTheme.orange.withValues(alpha: 0.35)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.stars, color: AppTheme.orange, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'NÂNG CẤP LÊN BASIC / PRO',
                              style: AppTheme.headingFont(
                                fontSize: 13.5,
                                fontWeight: FontWeight.w800,
                                color: AppTheme.orange,
                              ),
                            ),
                          ),
                          const Icon(
                            Icons.arrow_forward_ios,
                            size: 13,
                            color: AppTheme.orange,
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Đăng ký tài khoản để lưu giữ mô hình scan vĩnh viễn, mở khóa toàn bộ kho phôi và xuất file GLB cho thợ gia công.',
                        style: AppTheme.bodyFont(fontSize: 12.5, height: 1.4),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),
            ],

            // Live counters from GET /users/me/usage — a null limit on the
            // plan means unlimited, rendered as the bare count.
            Row(
              children: [
                Expanded(
                  child: _StatCard(
                    value: widget.isGuest
                        ? '0'
                        : AccountUsage.ratio(
                            usage?.projectsCount ?? 0,
                            usage?.maxProjects,
                          ),
                    label: 'DỰ ÁN',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _StatCard(
                    value: widget.isGuest
                        ? '0'
                        : AccountUsage.ratio(
                            usage?.exportsCount ?? 0,
                            usage?.maxExportsPerMonth,
                          ),
                    label: 'FILE XUẤT',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _StatCard(
                    value: widget.isGuest
                        ? '0'
                        : AccountUsage.ratio(
                            usage?.aiCreditsUsed ?? 0,
                            usage?.aiCreditsLimit,
                          ),
                    label: 'AI CREDIT',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            const _SectionLabel('CÀI ĐẶT & QUẢN LÝ'),
            const SizedBox(height: 8),
            _MenuTile(
              icon:
                  isDark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
              title: 'Giao diện',
              subtitle: isDark
                  ? 'Chế độ tối (Dark mode)'
                  : 'Chế độ sáng (Light mode)',
              trailing: Switch(
                value: isDark,
                activeThumbColor: AppTheme.orange,
                onChanged: (value) => widget
                    .onThemeModeChanged(value ? ThemeMode.dark : ThemeMode.light),
              ),
            ),
            _MenuTile(
              icon: Icons.palette_outlined,
              title: 'Thiết kế của tôi',
              subtitle: widget.isGuest
                  ? 'Cần tài khoản để xem dự án'
                  : 'Danh sách dự án & mở trên Kus Studio Web',
              onTap: widget.isGuest ? _requireAccount : _openMyDesigns,
            ),
            _MenuTile(
              icon: Icons.card_membership_outlined,
              title: 'Gói cước & Hạn mức',
              subtitle: widget.isGuest
                  ? 'Cần tài khoản để xem hạn mức'
                  : 'Gói hiện tại, hạn mức dự án / xuất file / AI credit',
              onTap: widget.isGuest ? _requireAccount : _openPlanUsage,
            ),
            _MenuTile(
              icon: Icons.person_outline,
              title: 'Thông tin cá nhân',
              subtitle: widget.isGuest
                  ? 'Cần tài khoản để chỉnh sửa hồ sơ'
                  : 'Đổi họ tên, số điện thoại liên lạc',
              onTap: widget.isGuest ? _requireAccount : _editProfile,
            ),
            _MenuTile(
              icon: Icons.lock_outline,
              title: 'Đổi mật khẩu',
              subtitle: widget.isGuest
                  ? 'Cần tài khoản để đổi mật khẩu'
                  : 'Cập nhật mật khẩu bảo mật tài khoản',
              onTap: widget.isGuest ? _requireAccount : _changePassword,
            ),
            _MenuTile(
              icon: Icons.feedback_outlined,
              title: 'Đánh giá & Góp ý',
              subtitle: 'Gửi ý kiến đóng góp nâng cấp KusShoes',
              onTap: widget.isGuest ? _requireAccount : _submitFeedback,
            ),
            if (!widget.isGuest)
              _MenuTile(
                icon: Icons.delete_forever_outlined,
                title: 'Xóa tài khoản',
                subtitle: 'Xóa vĩnh viễn dữ liệu tài khoản và các mẫu scan',
                isDestructive: true,
                onTap: _deleteAccount,
              ),
          ],
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 6),
        child: Column(
          children: [
            FittedBox(
              child: Text(
                value,
                maxLines: 1,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: const TextStyle(letterSpacing: 1.1, fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  const _MenuTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.trailing,
    this.onTap,
    this.isDestructive = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool isDestructive;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        dense: true,
        visualDensity: VisualDensity.compact,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
        leading: _IconBubble(
          icon: icon,
          muted: !isDestructive,
          radius: 17,
          colorOverride: isDestructive ? Colors.redAccent : null,
        ),
        title: Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w800,
            color: isDestructive ? Colors.redAccent : null,
          ),
        ),
        subtitle: Text(
          subtitle,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 12),
        ),
        trailing: trailing ??
            Icon(
              Icons.chevron_right,
              color: isDestructive ? Colors.redAccent : null,
            ),
        onTap: onTap,
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(letterSpacing: 2, fontWeight: FontWeight.w900),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.text, {this.filled = true});

  final String text;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.orange.withValues(alpha: filled ? 0.18 : 0.08),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.orange.withValues(alpha: 0.34)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        child: Text(
          text,
          style: const TextStyle(
              color: AppTheme.orange,
              fontSize: 11,
              fontWeight: FontWeight.w900),
        ),
      ),
    );
  }
}

class _IconBubble extends StatelessWidget {
  const _IconBubble({
    required this.icon,
    this.muted = false,
    this.radius = 22,
    this.colorOverride,
  });

  final IconData icon;
  final bool muted;
  final double radius;
  final Color? colorOverride;

  @override
  Widget build(BuildContext context) {
    final effectiveColor = colorOverride ??
        (muted
            ? Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.65)
            : AppTheme.orange);

    return CircleAvatar(
      radius: radius,
      backgroundColor: colorOverride != null
          ? colorOverride!.withValues(alpha: 0.12)
          : (muted
              ? Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.04)
              : AppTheme.orange.withValues(alpha: 0.16)),
      child: Icon(
        icon,
        size: radius * 0.95,
        color: effectiveColor,
      ),
    );
  }
}
