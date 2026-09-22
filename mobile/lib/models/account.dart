/// Models for the KusShoes account endpoints the mobile app reads.
///
/// Field names mirror the backend schemas exactly (`app/schemas/user.py`,
/// `app/schemas/subscription.py`, `app/schemas/project.py`) so a contract
/// change surfaces here rather than as a blank screen.
library;

int? _asInt(Object? value) => value is num ? value.toInt() : null;

String _asString(Object? value, {String fallback = ''}) =>
    value is String ? value : fallback;

DateTime? _asDate(Object? value) =>
    value is String ? DateTime.tryParse(value) : null;

/// `GET /api/v1/users/me` → UserDetailResponse
class UserProfile {
  const UserProfile({
    required this.id,
    required this.accountCode,
    required this.email,
    required this.username,
    required this.firstName,
    required this.lastName,
    required this.totalDesigns,
    required this.status,
    this.avatarPath,
    this.phoneNumber,
    this.bio,
    this.memberSince,
  });

  final String id;
  final String accountCode;
  final String email;
  final String username;
  final String firstName;
  final String lastName;
  final int totalDesigns;
  final String status;
  final String? avatarPath;
  final String? phoneNumber;
  final String? bio;
  final DateTime? memberSince;

  /// Falls back through display name → username → email local part so the
  /// profile header never renders empty.
  String get displayName {
    final full = '$firstName $lastName'.trim();
    if (full.isNotEmpty) {
      return full;
    }
    if (username.isNotEmpty) {
      return '@$username';
    }
    return email.split('@').first;
  }

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: _asString(json['id']),
      accountCode: _asString(json['account_code']),
      email: _asString(json['email']),
      username: _asString(json['username']),
      firstName: _asString(json['first_name']),
      lastName: _asString(json['last_name']),
      totalDesigns: _asInt(json['total_designs']) ?? 0,
      status: _asString(json['status'], fallback: 'active'),
      avatarPath: json['avatar_path'] as String?,
      phoneNumber: json['phone_number'] as String?,
      bio: json['bio'] as String?,
      memberSince: _asDate(json['member_since']),
    );
  }
}

/// `GET /api/v1/users/me/usage` → UsageResponse
///
/// A null limit means unlimited on this plan. [maxScansPerCycle] is the §3.2.8
/// scan allowance (free 0 / basic 1 / pro 3); the backend tracks no per-cycle
/// "scans used" counter, so only the allowance can be shown.
class AccountUsage {
  const AccountUsage({
    required this.tier,
    required this.projectsCount,
    required this.exportsCount,
    required this.aiCreditsUsed,
    this.maxProjects,
    this.maxExportsPerMonth,
    this.aiCreditsLimit,
    this.maxScansPerCycle,
  });

  final String tier;
  final int projectsCount;
  final int exportsCount;
  final int aiCreditsUsed;
  final int? maxProjects;
  final int? maxExportsPerMonth;
  final int? aiCreditsLimit;
  final int? maxScansPerCycle;

  String get tierLabel => switch (tier.toLowerCase()) {
        'free' => 'FREE',
        'basic' => 'BASIC',
        'pro' => 'PRO',
        'team' => 'TEAM',
        _ => tier.toUpperCase(),
      };

  /// Renders "3/20" or "3" when the plan has no cap.
  static String ratio(int used, int? limit) =>
      limit == null ? '$used' : '$used/$limit';

  factory AccountUsage.fromJson(Map<String, dynamic> json) {
    return AccountUsage(
      tier: _asString(json['tier'], fallback: 'free'),
      projectsCount: _asInt(json['projects_count']) ?? 0,
      exportsCount: _asInt(json['exports_count']) ?? 0,
      aiCreditsUsed: _asInt(json['ai_credits_used']) ?? 0,
      maxProjects: _asInt(json['max_projects']),
      maxExportsPerMonth: _asInt(json['max_exports_per_month']),
      aiCreditsLimit: _asInt(json['ai_credits_limit']),
      maxScansPerCycle: _asInt(json['max_scans_per_cycle']),
    );
  }
}

/// `GET /api/v1/subscription` → SubscriptionResponse
class SubscriptionInfo {
  const SubscriptionInfo({
    required this.tier,
    required this.status,
    required this.cancelAtPeriodEnd,
    this.startedAt,
    this.expiresAt,
  });

  final String tier;
  final String status;
  final bool cancelAtPeriodEnd;
  final DateTime? startedAt;
  final DateTime? expiresAt;

  String get statusLabel => switch (status.toLowerCase()) {
        'active' => 'Đang hoạt động',
        'grace' => 'Đang ân hạn',
        'expired' => 'Đã hết hạn',
        'cancelled' => 'Đã hủy',
        _ => status,
      };

  factory SubscriptionInfo.fromJson(Map<String, dynamic> json) {
    return SubscriptionInfo(
      tier: _asString(json['tier'], fallback: 'free'),
      status: _asString(json['status'], fallback: 'active'),
      cancelAtPeriodEnd: json['cancel_at_period_end'] == true,
      startedAt: _asDate(json['started_at']),
      expiresAt: _asDate(json['expires_at']),
    );
  }
}

/// `GET /api/v1/projects` → ProjectListResponse.items
class ProjectSummary {
  const ProjectSummary({
    required this.id,
    required this.name,
    required this.status,
    required this.isLocked,
    required this.editorUrl,
    this.description,
    this.thumbnailPath,
    this.updatedAt,
  });

  final String id;
  final String name;
  final String status;
  final bool isLocked;
  final String editorUrl;
  final String? description;
  final String? thumbnailPath;
  final DateTime? updatedAt;

  /// BR-43 project lifecycle labels.
  String get statusLabel => switch (status.toLowerCase()) {
        'draft' => 'Nháp',
        'in_progress' || 'editing' => 'Đang chỉnh',
        'baked' => 'Baked',
        'exported' => 'Đã xuất',
        _ => status,
      };

  factory ProjectSummary.fromJson(Map<String, dynamic> json) {
    return ProjectSummary(
      id: _asString(json['id']),
      name: _asString(json['name'], fallback: 'Dự án chưa đặt tên'),
      status: _asString(json['status'], fallback: 'draft'),
      isLocked: json['is_locked'] == true,
      editorUrl: _asString(json['editor_url']),
      description: json['description'] as String?,
      thumbnailPath: json['thumbnail_path'] as String?,
      updatedAt: _asDate(json['updated_at']),
    );
  }
}

/// One page of `GET /api/v1/projects`.
class ProjectPage {
  const ProjectPage({required this.items, this.nextCursor});

  final List<ProjectSummary> items;
  final String? nextCursor;

  bool get hasMore => nextCursor != null;

  factory ProjectPage.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'];
    return ProjectPage(
      items: rawItems is List
          ? rawItems
              .whereType<Map<String, dynamic>>()
              .map(ProjectSummary.fromJson)
              .toList()
          : const [],
      nextCursor: json['next_cursor'] as String?,
    );
  }
}

/// `GET /api/v1/plans` → PlanResponse
class BillingPlan {
  const BillingPlan({
    required this.id,
    required this.tier,
    this.billingCycle,
    required this.priceVnd,
    this.maxProjects,
    this.maxExportsPerMonth,
    required this.allowedExportFormats,
    required this.bakePriority,
    this.maxAiCreditsPerCycle,
    this.maxScansPerCycle,
    required this.allowDrawArtwork,
  });

  final String id;
  final String tier;
  final String? billingCycle;
  final int priceVnd;
  final int? maxProjects;
  final int? maxExportsPerMonth;
  final List<String> allowedExportFormats;
  final String bakePriority;
  final int? maxAiCreditsPerCycle;
  final int? maxScansPerCycle;
  final bool allowDrawArtwork;

  String get tierLabel => switch (tier.toLowerCase()) {
        'free' => 'MIỄN PHÍ',
        'basic' => 'BASIC',
        'pro' => 'PRO CHUYÊN NGHIỆP',
        'team' || 'enterprise' => 'ENTERPRISE',
        _ => tier.toUpperCase(),
      };

  String get formattedPrice {
    if (priceVnd == 0) return '0 đ';
    // Format 199000 -> 199.000 đ
    final str = priceVnd.toString();
    final buffer = StringBuffer();
    int count = 0;
    for (int i = str.length - 1; i >= 0; i--) {
      buffer.write(str[i]);
      count++;
      if (count % 3 == 0 && i > 0) {
        buffer.write('.');
      }
    }
    return '${buffer.toString().split('').reversed.join()} đ';
  }

  factory BillingPlan.fromJson(Map<String, dynamic> json) {
    final rawFormats = json['allowed_export_formats'] as List<dynamic>? ?? const [];
    return BillingPlan(
      id: _asString(json['id']),
      tier: _asString(json['tier'], fallback: 'free'),
      billingCycle: json['billing_cycle'] as String?,
      priceVnd: _asInt(json['price_vnd']) ?? 0,
      maxProjects: _asInt(json['max_projects']),
      maxExportsPerMonth: _asInt(json['max_exports_per_month']),
      allowedExportFormats: rawFormats.map((e) => e.toString()).toList(),
      bakePriority: _asString(json['bake_priority'], fallback: 'normal'),
      maxAiCreditsPerCycle: _asInt(json['max_ai_credits_per_cycle']),
      maxScansPerCycle: _asInt(json['max_scans_per_cycle']),
      allowDrawArtwork: json['allow_draw_artwork'] == true,
    );
  }
}

/// `GET /api/v1/subscription/invoices` → InvoiceResponse
class InvoiceItem {
  const InvoiceItem({
    required this.id,
    required this.orderCode,
    required this.planTier,
    required this.billingCycle,
    required this.amountVnd,
    required this.paymentMethod,
    required this.status,
    this.receiptNumber,
    this.paidAt,
    required this.createdAt,
  });

  final String id;
  final int orderCode;
  final String planTier;
  final String billingCycle;
  final int amountVnd;
  final String paymentMethod;
  final String status;
  final String? receiptNumber;
  final DateTime? paidAt;
  final DateTime createdAt;

  factory InvoiceItem.fromJson(Map<String, dynamic> json) {
    return InvoiceItem(
      id: _asString(json['id']),
      orderCode: _asInt(json['order_code']) ?? 0,
      planTier: _asString(json['plan_tier'], fallback: 'basic'),
      billingCycle: _asString(json['billing_cycle'], fallback: 'monthly'),
      amountVnd: _asInt(json['amount_vnd']) ?? 0,
      paymentMethod: _asString(json['payment_method'], fallback: 'payos'),
      status: _asString(json['status'], fallback: 'pending'),
      receiptNumber: json['receipt_number'] as String?,
      paidAt: _asDate(json['paid_at']),
      createdAt: _asDate(json['created_at']) ?? DateTime.now(),
    );
  }
}

/// `GET /api/v1/exports` → ExportRecord
class ExportItem {
  const ExportItem({
    required this.id,
    required this.projectId,
    required this.format,
    required this.status,
    this.fileSize,
    required this.createdAt,
  });

  final String id;
  final String projectId;
  final String format;
  final String status;
  final int? fileSize;
  final DateTime createdAt;

  factory ExportItem.fromJson(Map<String, dynamic> json) {
    return ExportItem(
      id: _asString(json['id']),
      projectId: _asString(json['project_id']),
      format: _asString(json['format'], fallback: 'glb'),
      status: _asString(json['status'], fallback: 'completed'),
      fileSize: _asInt(json['file_size']),
      createdAt: _asDate(json['created_at']) ?? DateTime.now(),
    );
  }
}
