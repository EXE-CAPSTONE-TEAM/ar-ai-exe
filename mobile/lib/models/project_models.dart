import 'package:flutter/foundation.dart';

@immutable
class ProjectDetail {
  const ProjectDetail({
    required this.id,
    required this.name,
    this.description,
    required this.status,
    required this.isLocked,
    this.thumbnailPath,
    required this.editorUrl,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ProjectDetail.fromJson(Map<String, dynamic> json) {
    return ProjectDetail(
      id: json['id'] as String,
      name: json['name'] as String? ?? 'Chưa đặt tên',
      description: json['description'] as String?,
      status: json['status'] as String? ?? 'active',
      isLocked: json['is_locked'] as bool? ?? false,
      thumbnailPath: json['thumbnail_path'] as String?,
      editorUrl: json['editor_url'] as String? ?? '',
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }

  final String id;
  final String name;
  final String? description;
  final String status;
  final bool isLocked;
  final String? thumbnailPath;
  final String editorUrl;
  final DateTime createdAt;
  final DateTime updatedAt;
}

@immutable
class ProjectTrashItem {
  const ProjectTrashItem({
    required this.id,
    required this.name,
    this.description,
    this.thumbnailPath,
    required this.deletedAt,
  });

  factory ProjectTrashItem.fromJson(Map<String, dynamic> json) {
    return ProjectTrashItem(
      id: json['id'] as String,
      name: json['name'] as String? ?? 'Dự án đã xóa',
      description: json['description'] as String?,
      thumbnailPath: json['thumbnail_path'] as String?,
      deletedAt: DateTime.tryParse(json['deleted_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }

  final String id;
  final String name;
  final String? description;
  final String? thumbnailPath;
  final DateTime deletedAt;
}

@immutable
class ProjectTrashPage {
  const ProjectTrashPage({
    required this.items,
    this.nextCursor,
    required this.totalCount,
  });

  factory ProjectTrashPage.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? const [];
    return ProjectTrashPage(
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map(ProjectTrashItem.fromJson)
          .toList(growable: false),
      nextCursor: json['next_cursor'] as String?,
      totalCount: json['total_count'] as int? ?? rawItems.length,
    );
  }

  final List<ProjectTrashItem> items;
  final String? nextCursor;
  final int totalCount;
}
