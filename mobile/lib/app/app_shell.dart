import 'package:flutter/material.dart';

import '../screens/auth_screen.dart';
import '../screens/scan_home_screen.dart';
import '../screens/user_manual_screen.dart';
import '../services/backend_api.dart';
import 'app_theme.dart';

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
  int _index = 1;

  @override
  Widget build(BuildContext context) {
    final pages = [
      const _ExploreTab(),
      ScanHomeScreen(isGuest: widget.isGuest),
      const UserManualScreen(),
      _ProfileTab(
        themeMode: widget.themeMode,
        onThemeModeChanged: widget.onThemeModeChanged,
        onLogout: _logout,
        isGuest: widget.isGuest,
      ),
    ];

    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(child: pages[_index]),
          Positioned(
            left: 12,
            right: 12,
            bottom: 16,
            child: _PillBottomNav(
              index: _index,
              onChanged: (value) => setState(() => _index = value),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _logout() async {
    await BackendApi().logout();
    if (!mounted) {
      return;
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
    return SafeArea(
      bottom: false,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 430),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 132),
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
        constraints: const BoxConstraints(maxWidth: 410),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: isDark ? const Color(0xF2151515) : Colors.white,
            borderRadius: BorderRadius.circular(28),
            border: Border.all(
              color: isDark ? const Color(0xFF2C2C2C) : const Color(0xFFFFD0BC),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.5 : 0.12),
                blurRadius: 28,
                offset: const Offset(0, 18),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(10, 10, 10, 9),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _NavItem(
                  selected: index == 0,
                  icon: Icons.explore_outlined,
                  label: 'Khám phá',
                  onTap: () => onChanged(0),
                ),
                _NavItem(
                  selected: index == 1,
                  icon: Icons.center_focus_strong,
                  label: 'Quét AI',
                  onTap: () => onChanged(1),
                ),
                _NavItem(
                  selected: index == 2,
                  icon: Icons.menu_book_outlined,
                  label: 'Cẩm nang',
                  onTap: () => onChanged(2),
                ),
                _NavItem(
                  selected: index == 3,
                  icon: Icons.person_outline,
                  label: 'Cá nhân',
                  onTap: () => onChanged(3),
                ),
              ],
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
    final color = selected ? AppTheme.orange : const Color(0xFF9D9D9D);
    return InkWell(
      borderRadius: BorderRadius.circular(24),
      onTap: onTap,
      child: SizedBox(
        width: 82,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: selected ? 52 : 42,
              height: selected ? 52 : 42,
              decoration: BoxDecoration(
                color: selected ? AppTheme.orange : Colors.transparent,
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                color: selected ? Colors.black : color,
                size: selected ? 27 : 25,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              label,
              maxLines: 1,
              style: TextStyle(
                color:
                    selected ? Theme.of(context).colorScheme.onSurface : color,
                fontWeight: FontWeight.w800,
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ExploreTab extends StatelessWidget {
  const _ExploreTab();

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
            'Quét đôi giày thật bằng camera AI 360°, tùy biến sticker & vẽ tay trên Kus Studio Web và xuất file chuẩn cho nghệ nhân gia công ngoài đời thực.',
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
            onPressed: () {},
            icon: const Icon(Icons.open_in_browser),
            label: const Text('MỞ KUS STUDIO TRÊN WEB'),
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
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.04),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              'Ghi chú (SC-27): Các tính năng trên thuộc kế hoạch mở rộng tương lai. Trong kỳ EXE201, KusShoes tập trung vào Quét 3D, Thiết kế web và Xuất file.',
              style: AppTheme.bodyFont(
                fontSize: 11.5,
                color: Colors.grey,
                height: 1.35,
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
            gradient: const LinearGradient(
              colors: [AppTheme.orange, AppTheme.crimson],
            ),
            borderRadius: BorderRadius.circular(12),
          ),
          alignment: Alignment.center,
          child: const Text(
            'K',
            style: TextStyle(
              color: Colors.black,
              fontWeight: FontWeight.w900,
              fontSize: 20,
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
        trailing: const Icon(Icons.chevron_right),
        onTap: () {},
      ),
    );
  }
}


class _ProfileTab extends StatelessWidget {
  const _ProfileTab({
    required this.themeMode,
    required this.onThemeModeChanged,
    required this.onLogout,
    this.isGuest = false,
  });

  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;
  final Future<void> Function() onLogout;
  final bool isGuest;

  @override
  Widget build(BuildContext context) {
    final isDark = themeMode == ThemeMode.dark;
    return _TabScaffold(
      child: ListView(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Hồ Sơ Cá Nhân',
                  style: Theme.of(context)
                      .textTheme
                      .displaySmall
                      ?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              IconButton.filledTonal(
                onPressed: onLogout,
                icon: const Icon(Icons.logout),
                tooltip: 'Đăng xuất',
              ),
            ],
          ),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(22),
              child: Row(
                children: [
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: AppTheme.orange.withValues(alpha: 0.8),
                        width: 2.5,
                      ),
                      color: AppTheme.orange.withValues(alpha: 0.1),
                    ),
                    child: Icon(
                      isGuest ? Icons.person_outline : Icons.account_circle,
                      size: 42,
                      color: AppTheme.orange,
                    ),
                  ),
                  const SizedBox(width: 20),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isGuest ? 'Khách Trải Nghiệm' : 'Nguyễn Văn A',
                          style: AppTheme.headingFont(
                            fontSize: 20,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          isGuest
                              ? 'Chế độ khách (1 scan thử)'
                              : 'TP. Hồ Chí Minh, VN',
                          style: AppTheme.bodyFont(
                            fontSize: 13,
                            color: Colors.grey,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          children: [
                            _Tag(
                              isGuest ? 'Guest Trial' : 'Gói Basic',
                              filled: true,
                            ),
                            _Tag(
                              isGuest ? 'Chưa đăng ký' : 'EXE201 Beta',
                              filled: false,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Guest upsell callout
          if (isGuest) ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    AppTheme.orange.withValues(alpha: 0.12),
                    AppTheme.crimson.withValues(alpha: 0.08),
                  ],
                ),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: AppTheme.orange.withValues(alpha: 0.35)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.stars, color: AppTheme.orange, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        'NÂNG CẤP LÊN BASIC / PRO',
                        style: AppTheme.headingFont(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w800,
                          color: AppTheme.orange,
                        ),
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
            const SizedBox(height: 20),
          ],

          Row(
            children: [
              Expanded(
                child: _StatCard(
                  value: isGuest ? '1/1' : '1',
                  label: isGuest ? 'SCAN THỬ' : 'LƯỢT QUÉT',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _StatCard(
                  value: isGuest ? '0' : '12',
                  label: 'DỰ ÁN',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _StatCard(
                  value: isGuest ? '0' : '4',
                  label: 'FILE XUẤT',
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          const _SectionLabel('CÀI ĐẶT & QUẢN LÝ'),
          const SizedBox(height: 10),
          _MenuTile(
            icon: isDark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
            title: 'Giao diện',
            subtitle: isDark ? 'Chế độ tối (Dark mode)' : 'Chế độ sáng (Light mode)',
            trailing: Switch(
              value: isDark,
              activeThumbColor: AppTheme.orange,
              onChanged: (value) =>
                  onThemeModeChanged(value ? ThemeMode.dark : ThemeMode.light),
            ),
          ),
          const _MenuTile(
            icon: Icons.palette_outlined,
            title: 'Thiết kế của tôi',
            subtitle: 'Quản lý các bản nháp & file 3D',
          ),
          const _MenuTile(
            icon: Icons.card_membership_outlined,
            title: 'Gói cước & Hạn mức',
            subtitle: 'Xem gói Basic/Pro và lượt quét còn lại',
          ),
          const _MenuTile(
            icon: Icons.history_outlined,
            title: 'Lịch sử quét 3D',
            subtitle: 'Xem các phiên scan và file GLB đã xử lý',
          ),
        ],
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
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Column(
          children: [
            Text(value,
                style:
                    const TextStyle(fontSize: 28, fontWeight: FontWeight.w900)),
            const SizedBox(height: 10),
            Text(label, style: const TextStyle(letterSpacing: 2, fontSize: 12)),
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
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
        leading: _IconBubble(icon: icon, muted: true),
        title: Text(title,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
        subtitle: Text(subtitle),
        trailing: trailing ?? const Icon(Icons.chevron_right),
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
  });

  final IconData icon;
  final bool muted;

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 22,
      backgroundColor: muted
          ? Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.04)
          : AppTheme.orange.withValues(alpha: 0.16),
      child: Icon(
        icon,
        color: muted
            ? Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.65)
            : AppTheme.orange,
      ),
    );
  }
}
