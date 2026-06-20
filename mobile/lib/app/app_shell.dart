import 'package:flutter/material.dart';

import '../screens/auth_screen.dart';
import '../screens/scan_home_screen.dart';
import '../services/backend_api.dart';
import 'app_theme.dart';

class AppShell extends StatefulWidget {
  const AppShell({
    required this.themeMode,
    required this.onThemeModeChanged,
    super.key,
  });

  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 1;

  @override
  Widget build(BuildContext context) {
    final pages = [
      const _ExploreTab(),
      const ScanHomeScreen(),
      const _NotifyTab(),
      _ProfileTab(
        themeMode: widget.themeMode,
        onThemeModeChanged: widget.onThemeModeChanged,
        onLogout: _logout,
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
                  label: 'Explore',
                  onTap: () => onChanged(0),
                ),
                _NavItem(
                  selected: index == 1,
                  icon: Icons.center_focus_strong,
                  label: 'AI Scan',
                  onTap: () => onChanged(1),
                ),
                _NavItem(
                  selected: index == 2,
                  icon: Icons.notifications_none,
                  label: 'Notify',
                  onTap: () => onChanged(2),
                ),
                _NavItem(
                  selected: index == 3,
                  icon: Icons.person_outline,
                  label: 'Profile',
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
            'Quet ban chan 3D, thiet ke giay ca nhan hoa bang AI va dat san xuat chi trong vai phut.',
            style: TextStyle(
              color: Theme.of(context)
                  .colorScheme
                  .onSurface
                  .withValues(alpha: 0.7),
              height: 1.5,
            ),
          ),
          const SizedBox(height: 22),
          FilledButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.arrow_forward),
            label: const Text('Thiet ke ngay tren web'),
          ),
          const SizedBox(height: 30),
          const _SectionLabel('TINH NANG NOI BAT'),
          const SizedBox(height: 14),
          const _FeatureGrid(),
          const SizedBox(height: 24),
          const Row(
            children: [
              Expanded(child: _SectionLabel('SAP RA MAT')),
              _Tag('Roadmap 2025', filled: false),
            ],
          ),
          const SizedBox(height: 12),
          const _RoadmapTile(
            icon: Icons.storefront_outlined,
            title: 'KusShoe Store',
            badge: 'Store',
            body: 'Mua phu kien giay, day giay custom, de tang chieu cao.',
          ),
          const _RoadmapTile(
            icon: Icons.water_drop_outlined,
            title: 'Dich vu ve sinh & Spa',
            badge: 'Service',
            body:
                'Dat lich ve sinh giay chuyen sau, khu mui va repaint tai nha.',
          ),
          const _RoadmapTile(
            icon: Icons.diamond_outlined,
            title: 'Limited Drops',
            badge: 'Drop',
            body:
                'Cac bo suu tap gioi han do AI va nghe si Viet Nam dong thiet ke.',
          ),
          const _RoadmapTile(
            icon: Icons.local_shipping_outlined,
            title: 'Giao hang toan quoc',
            badge: 'Logistics',
            body: 'Theo doi don hang va doi tra size de dang qua ung dung.',
          ),
          const SizedBox(height: 4),
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
        const CircleAvatar(
          radius: 18,
          backgroundColor: AppTheme.orange,
          child: Text('K',
              style:
                  TextStyle(color: Colors.black, fontWeight: FontWeight.w900)),
        ),
        const SizedBox(width: 10),
        Text(
          'KusShoe',
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.w900),
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
            title: '3D Foot Scan',
            body: 'Quet chan chinh xac bang camera.'),
        _FeatureCard(
            icon: Icons.auto_fix_high,
            title: 'AI Generator',
            body: 'Tao mau giay tu mo ta ngon ngu.'),
        _FeatureCard(
            icon: Icons.layers_outlined,
            title: 'Material Lab',
            body: 'Chon da, vai, luoi va mau sac.'),
        _FeatureCard(
            icon: Icons.ios_share,
            title: 'Export & Share',
            body: 'Xuat GLB, chia se thiet ke.'),
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
        title: const Text('Truy cap KusShoe.vn',
            style: TextStyle(fontWeight: FontWeight.w900)),
        subtitle: const Text('Kham pha gallery, dat hang & ho tro truc tuyen'),
        trailing: const Icon(Icons.chevron_right),
        onTap: () {},
      ),
    );
  }
}

class _NotifyTab extends StatelessWidget {
  const _NotifyTab();

  @override
  Widget build(BuildContext context) {
    return _TabScaffold(
      child: ListView(
        children: const [
          Row(
            children: [
              Expanded(
                  child: _KickerTitle(kicker: 'INBOX', title: 'Notifications')),
              _NewBadge(),
            ],
          ),
          SizedBox(height: 28),
          _NotificationHero(),
          SizedBox(height: 18),
          _NotificationTile(
            icon: Icons.bolt,
            title: 'Welcome to KusShoe',
            body: 'Start your first 3D scan and get 10% off your custom order.',
            time: '2m ago',
            unread: true,
          ),
          _NotificationTile(
            icon: Icons.trending_up,
            title: 'New Drop Alert',
            body:
                "The 'Neon Blaze' sole pack just landed. Check it out online.",
            time: '1h ago',
            unread: true,
          ),
          _NotificationTile(
            icon: Icons.inventory_2_outlined,
            title: 'Order Shipped',
            body:
                'Your KusShoe Custom Mini #01 is on its way to Ho Chi Minh City.',
            time: '3h ago',
          ),
          _NotificationTile(
            icon: Icons.workspace_premium_outlined,
            title: 'Weekly Inspiration',
            body: "See this week's top community designs on our web gallery.",
            time: '1d ago',
          ),
        ],
      ),
    );
  }
}

class _NotificationHero extends StatelessWidget {
  const _NotificationHero();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: ListTile(
        contentPadding: EdgeInsets.symmetric(horizontal: 22, vertical: 22),
        leading: _IconBubble(icon: Icons.open_in_new, large: true),
        title: Text('Visit KusShoe Website',
            style: TextStyle(fontWeight: FontWeight.w900)),
        subtitle: Text('kushoe.vn - New drops & gallery'),
        trailing: Icon(Icons.chevron_right),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({
    required this.icon,
    required this.title,
    required this.body,
    required this.time,
    this.unread = false,
  });

  final IconData icon;
  final String title;
  final String body;
  final String time;
  final bool unread;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: unread
          ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.06)
          : null,
      margin: const EdgeInsets.only(bottom: 18),
      child: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.all(22),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _IconBubble(icon: icon, muted: true),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title,
                          style: const TextStyle(
                              fontSize: 20, fontWeight: FontWeight.w900)),
                      const SizedBox(height: 8),
                      Text(body,
                          style: TextStyle(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurface
                                  .withValues(alpha: 0.72),
                              height: 1.45)),
                      const SizedBox(height: 14),
                      Text(time,
                          style: TextStyle(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurface
                                  .withValues(alpha: 0.48))),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (unread)
            const Positioned(
              top: 20,
              right: 20,
              child: CircleAvatar(radius: 6, backgroundColor: AppTheme.orange),
            ),
        ],
      ),
    );
  }
}

class _ProfileTab extends StatelessWidget {
  const _ProfileTab({
    required this.themeMode,
    required this.onThemeModeChanged,
    required this.onLogout,
  });

  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;
  final Future<void> Function() onLogout;

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
                  'My Profile',
                  style: Theme.of(context)
                      .textTheme
                      .displaySmall
                      ?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              IconButton.filledTonal(
                onPressed: onLogout,
                icon: const Icon(Icons.settings_outlined),
              ),
            ],
          ),
          const SizedBox(height: 22),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Row(
                children: [
                  Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                          color: AppTheme.orange.withValues(alpha: 0.6),
                          width: 3),
                    ),
                    child: const Icon(Icons.person_outline, size: 48),
                  ),
                  const SizedBox(width: 24),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Nguyen Van A',
                            style: TextStyle(
                                fontSize: 24, fontWeight: FontWeight.w900)),
                        SizedBox(height: 8),
                        Text('Ho Chi Minh City, VN'),
                        SizedBox(height: 14),
                        Wrap(
                          spacing: 8,
                          children: [
                            _Tag('Pro Member', filled: true),
                            _Tag('Since 2024', filled: false),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 22),
          const Row(
            children: [
              Expanded(child: _StatCard(value: '12', label: 'DESIGNS')),
              SizedBox(width: 14),
              Expanded(child: _StatCard(value: '5', label: 'ORDERS')),
              SizedBox(width: 14),
              Expanded(child: _StatCard(value: '2.4k', label: 'POINTS')),
            ],
          ),
          const SizedBox(height: 28),
          const _SectionLabel('MENU'),
          const SizedBox(height: 12),
          _MenuTile(
            icon: isDark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
            title: 'Appearance',
            subtitle: isDark ? 'Dark mode' : 'Light mode',
            trailing: Switch(
              value: isDark,
              activeThumbColor: AppTheme.orange,
              onChanged: (value) =>
                  onThemeModeChanged(value ? ThemeMode.dark : ThemeMode.light),
            ),
          ),
          const _MenuTile(
              icon: Icons.shopping_bag_outlined,
              title: 'My Designs',
              subtitle: '12 custom shoes'),
          const _MenuTile(
              icon: Icons.inventory_2_outlined,
              title: 'Orders',
              subtitle: '3 active, 2 completed'),
          const _MenuTile(
              icon: Icons.favorite_border,
              title: 'Saved',
              subtitle: '8 favorite drops'),
          const _MenuTile(
              icon: Icons.credit_card,
              title: 'Payment Methods',
              subtitle: 'Visa .... 4242'),
          const _MenuTile(
              icon: Icons.calendar_month_outlined,
              title: 'History',
              subtitle: 'Scan & purchase log'),
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

class _KickerTitle extends StatelessWidget {
  const _KickerTitle({required this.kicker, required this.title});

  final String kicker;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          kicker,
          style: const TextStyle(
            color: AppTheme.orange,
            letterSpacing: 6,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          title,
          style: Theme.of(context)
              .textTheme
              .displaySmall
              ?.copyWith(fontWeight: FontWeight.w900),
        ),
      ],
    );
  }
}

class _NewBadge extends StatelessWidget {
  const _NewBadge();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.orange.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.orange.withValues(alpha: 0.4)),
      ),
      child: const Padding(
        padding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Text('2 new',
            style:
                TextStyle(color: AppTheme.orange, fontWeight: FontWeight.w900)),
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
    this.large = false,
  });

  final IconData icon;
  final bool muted;
  final bool large;

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: large ? 32 : 22,
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
