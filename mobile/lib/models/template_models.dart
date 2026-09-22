import 'package:flutter/foundation.dart';

@immutable
class ShoeTemplate {
  const ShoeTemplate({
    required this.id,
    required this.name,
    this.description,
    this.category,
    this.thumbnailPath,
    required this.layerCount,
    required this.useCount,
  });

  factory ShoeTemplate.fromJson(Map<String, dynamic> json) {
    return ShoeTemplate(
      id: json['id'] as String,
      name: json['name'] as String? ?? 'Phôi giày mẫu',
      description: json['description'] as String?,
      category: json['category'] as String?,
      thumbnailPath: json['thumbnail_path'] as String?,
      layerCount: json['layer_count'] as int? ?? 0,
      useCount: json['use_count'] as int? ?? 0,
    );
  }

  final String id;
  final String name;
  final String? description;
  final String? category;
  final String? thumbnailPath;
  final int layerCount;
  final int useCount;

  String get categoryLabel {
    switch (category?.toLowerCase()) {
      case 'sneaker':
        return 'Sneaker Thể Thao';
      case 'running':
        return 'Giày Chạy';
      case 'boot':
        return 'Boot / Cổ Cao';
      case 'loafer':
        return 'Loafer / Công Sở';
      case 'sandal':
        return 'Sandal / Thoáng Khí';
      default:
        return 'Phôi Tự Do';
    }
  }
}
