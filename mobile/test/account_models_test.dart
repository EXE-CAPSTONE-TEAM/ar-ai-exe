import 'package:flutter_test/flutter_test.dart';

import 'package:shoe_visual_customizer_mobile/models/account.dart';

void main() {
  group('AccountUsage', () {
    test('parses a Basic plan payload from /users/me/usage', () {
      final usage = AccountUsage.fromJson(const {
        'tier': 'basic',
        'max_projects': 20,
        'max_exports_per_month': 100,
        'projects_count': 3,
        'exports_count': 7,
        'ai_credits_used': 12,
        'ai_credits_limit': 100,
        'max_scans_per_cycle': 1,
      });

      expect(usage.tierLabel, 'BASIC');
      expect(usage.projectsCount, 3);
      expect(usage.maxScansPerCycle, 1);
      expect(AccountUsage.ratio(usage.projectsCount, usage.maxProjects), '3/20');
    });

    test('treats a null limit as unlimited, not zero', () {
      final usage = AccountUsage.fromJson(const {
        'tier': 'pro',
        'projects_count': 5,
        'exports_count': 0,
        'ai_credits_used': 0,
        'max_projects': null,
        'ai_credits_limit': null,
      });

      expect(usage.maxProjects, isNull);
      expect(AccountUsage.ratio(usage.projectsCount, usage.maxProjects), '5');
    });

    test('survives a payload missing the newer scan field', () {
      // Older backends do not send max_scans_per_cycle; the badge must degrade
      // rather than throw.
      final usage = AccountUsage.fromJson(const {
        'tier': 'free',
        'projects_count': 0,
        'exports_count': 0,
        'ai_credits_used': 0,
      });

      expect(usage.maxScansPerCycle, isNull);
      expect(usage.tierLabel, 'FREE');
    });
  });

  group('UserProfile', () {
    test('builds a display name from first and last name', () {
      final profile = UserProfile.fromJson(const {
        'id': 'u1',
        'account_code': 'KS-2026-00042',
        'email': 'mai@example.com',
        'username': 'mai',
        'first_name': 'Mai',
        'last_name': 'Trần',
        'total_designs': 4,
        'status': 'active',
      });

      expect(profile.displayName, 'Mai Trần');
      expect(profile.accountCode, 'KS-2026-00042');
    });

    test('falls back to username then email when names are blank', () {
      final withUsername = UserProfile.fromJson(const {
        'id': 'u1',
        'account_code': '',
        'email': 'mai@example.com',
        'username': 'mai',
        'first_name': '',
        'last_name': '',
        'total_designs': 0,
        'status': 'active',
      });
      expect(withUsername.displayName, '@mai');

      final emailOnly = UserProfile.fromJson(const {
        'id': 'u1',
        'account_code': '',
        'email': 'mai@example.com',
        'username': '',
        'first_name': '',
        'last_name': '',
        'total_designs': 0,
        'status': 'active',
      });
      expect(emailOnly.displayName, 'mai');
    });
  });

  group('ProjectPage', () {
    test('parses items and exposes the cursor', () {
      final page = ProjectPage.fromJson(const {
        'items': [
          {
            'id': 'p1',
            'name': 'Giày cưới',
            'status': 'in_progress',
            'is_locked': false,
            'editor_url': 'https://app.example/editor/p1',
            'updated_at': '2026-09-01T10:00:00Z',
          },
        ],
        'next_cursor': 'abc123',
      });

      expect(page.items, hasLength(1));
      expect(page.items.single.statusLabel, 'Đang chỉnh');
      expect(page.hasMore, isTrue);
      expect(page.nextCursor, 'abc123');
    });

    test('handles an empty page with no cursor', () {
      final page = ProjectPage.fromJson(const {'items': [], 'next_cursor': null});
      expect(page.items, isEmpty);
      expect(page.hasMore, isFalse);
    });
  });
}
