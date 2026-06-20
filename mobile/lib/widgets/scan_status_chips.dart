import 'package:flutter/material.dart';

class ScanStatusChips extends StatelessWidget {
  const ScanStatusChips({
    required this.items,
    this.compact = false,
    super.key,
  });

  final List<ScanStatusItem> items;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: compact ? 6 : 8,
      runSpacing: compact ? 6 : 8,
      children: [
        for (final item in items)
          DecoratedBox(
            decoration: BoxDecoration(
              color: item.color.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: item.color.withValues(alpha: 0.42)),
            ),
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: compact ? 9 : 11,
                vertical: compact ? 6 : 7,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(item.icon, size: compact ? 14 : 15, color: item.color),
                  const SizedBox(width: 6),
                  Text(
                    item.label,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: compact ? 11 : 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class ScanStatusItem {
  const ScanStatusItem({
    required this.icon,
    required this.label,
    required this.color,
  });

  final IconData icon;
  final String label;
  final Color color;
}
