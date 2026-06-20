import 'package:flutter/material.dart';

import '../app/app_theme.dart';

class BrandHeader extends StatelessWidget {
  const BrandHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: AppTheme.orange,
            borderRadius: BorderRadius.circular(14),
          ),
          child: const Center(
            child: Text(
              'K',
              style: TextStyle(
                color: Color(0xFF07110E),
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'KusShoe',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
            ),
            SizedBox(height: 2),
            Text(
              'AI shoe studio',
              style: TextStyle(color: Color(0xFF9BA7B6), fontSize: 12),
            ),
          ],
        ),
      ],
    );
  }
}
