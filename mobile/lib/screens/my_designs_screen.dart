import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../app/app_theme.dart';
import '../models/account.dart';
import '../services/api_exception.dart';
import '../services/backend_api.dart';
import 'project_trash_screen.dart';

/// SC-26 "Thiết kế của tôi" — the signed-in user's projects from
/// `GET /api/v1/projects`.
///
/// Read-only by design: BR-42 puts the full editor on Web/Desktop only, so a
/// row hands off to `editor_url` in the browser rather than editing in place.
class MyDesignsScreen extends StatefulWidget {
  const MyDesignsScreen({required this.api, super.key});

  final BackendApi api;

  @override
  State<MyDesignsScreen> createState() => _MyDesignsScreenState();
}

class _MyDesignsScreenState extends State<MyDesignsScreen> {
  final _scrollController = ScrollController();
  final List<ProjectSummary> _projects = [];

  String? _nextCursor;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _load();
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients || _loadingMore || _nextCursor == null) {
      return;
    }
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 300) {
      _loadMore();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await widget.api.listProjects();
      if (!mounted) return;
      setState(() {
        _projects
          ..clear()
          ..addAll(page.items);
        _nextCursor = page.nextCursor;
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

  Future<void> _loadMore() async {
    final cursor = _nextCursor;
    if (cursor == null || _loadingMore) {
      return;
    }
    setState(() => _loadingMore = true);
    try {
      final page = await widget.api.listProjects(cursor: cursor);
      if (!mounted) return;
      setState(() {
        _projects.addAll(page.items);
        _nextCursor = page.nextCursor;
        _loadingMore = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _loadingMore = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  Future<void> _openInEditor(ProjectSummary project) async {
    final messenger = ScaffoldMessenger.of(context);
    if (project.editorUrl.isEmpty) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Dự án này chưa có liên kết editor.')),
      );
      return;
    }
    final opened = await launchUrl(
      Uri.parse(project.editorUrl),
      mode: LaunchMode.externalApplication,
    );
    if (!opened) {
      messenger.showSnackBar(
        SnackBar(content: Text('Không mở được ${project.editorUrl}')),
      );
    }
  }

  Future<void> _renameProject(ProjectSummary project) async {
    final controller = TextEditingController(text: project.name);
    final newName = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Đổi tên dự án'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'Tên mẫu giày',
            hintText: 'Nhập tên mới...',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () {
              final text = controller.text.trim();
              if (text.isNotEmpty) Navigator.of(ctx).pop(text);
            },
            child: const Text('Lưu'),
          ),
        ],
      ),
    );

    if (newName == null || newName == project.name || !mounted) return;

    try {
      final updated = await widget.api.updateProject(project.id, name: newName);
      if (!mounted) return;
      setState(() {
        final index = _projects.indexWhere((p) => p.id == project.id);
        if (index != -1) {
          _projects[index] = updated;
        }
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã cập nhật tên dự án.')),
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

  Future<void> _deleteProject(ProjectSummary project) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Xóa dự án?'),
        content: Text(
          'Dự án "${project.name}" sẽ được chuyển vào thùng rác. Bạn có thể khôi phục sau này.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Xóa vào thùng rác'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    try {
      await widget.api.deleteProject(project.id);
      if (!mounted) return;
      setState(() {
        _projects.removeWhere((p) => p.id == project.id);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Đã chuyển "${project.name}" vào thùng rác.'),
          action: SnackBarAction(
            label: 'Thùng rác',
            onPressed: () {
              Navigator.of(context)
                  .push(
                MaterialPageRoute(
                  builder: (_) => ProjectTrashScreen(api: widget.api),
                ),
              )
                  .then((_) {
                if (mounted) _load();
              });
            },
          ),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Thiết kế của tôi'),
        actions: [
          IconButton(
            tooltip: 'Thùng rác',
            icon: const Icon(Icons.delete_outline),
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => ProjectTrashScreen(api: widget.api),
                ),
              );
              if (mounted) _load();
            },
          ),
          IconButton(
            tooltip: 'Tải lại',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    final error = _error;
    if (error != null) {
      return _CenteredMessage(
        icon: Icons.cloud_off_outlined,
        title: 'Không tải được danh sách',
        body: error,
        actionLabel: 'Thử lại',
        onAction: _load,
      );
    }

    if (_projects.isEmpty) {
      return const _CenteredMessage(
        icon: Icons.palette_outlined,
        title: 'Chưa có thiết kế nào',
        body: 'Quét một đôi giày để tạo dự án đầu tiên, rồi tiếp tục thiết kế '
            'trên Kus Studio Web.',
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        controller: _scrollController,
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        itemCount: _projects.length + (_nextCursor == null ? 0 : 1),
        itemBuilder: (context, index) {
          if (index >= _projects.length) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          return _ProjectTile(
            project: _projects[index],
            onOpen: () => _openInEditor(_projects[index]),
            onRename: () => _renameProject(_projects[index]),
            onDelete: () => _deleteProject(_projects[index]),
          );
        },
      ),
    );
  }
}

class _ProjectTile extends StatelessWidget {
  const _ProjectTile({
    required this.project,
    required this.onOpen,
    required this.onRename,
    required this.onDelete,
  });

  final ProjectSummary project;
  final VoidCallback onOpen;
  final VoidCallback onRename;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor: AppTheme.orange.withValues(alpha: 0.14),
          child: Icon(
            project.isLocked ? Icons.lock_outline : Icons.view_in_ar_outlined,
            color: AppTheme.orange,
          ),
        ),
        title: Text(
          project.name,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            [
              project.statusLabel,
              if (project.updatedAt != null) _relativeTime(project.updatedAt!),
            ].join(' · '),
            style: AppTheme.monoFont(fontSize: 11, color: Colors.grey),
          ),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.open_in_new, size: 20),
              tooltip: 'Mở Kus Studio Web',
              onPressed: onOpen,
            ),
            PopupMenuButton<String>(
              icon: const Icon(Icons.more_vert, size: 20),
              onSelected: (value) {
                if (value == 'rename') {
                  onRename();
                } else if (value == 'delete') {
                  onDelete();
                }
              },
              itemBuilder: (context) => [
                const PopupMenuItem(
                  value: 'rename',
                  child: Row(
                    children: [
                      Icon(Icons.edit_outlined, size: 18),
                      SizedBox(width: 8),
                      Text('Đổi tên'),
                    ],
                  ),
                ),
                const PopupMenuItem(
                  value: 'delete',
                  child: Row(
                    children: [
                      Icon(Icons.delete_outline, size: 18, color: Colors.red),
                      SizedBox(width: 8),
                      Text('Xóa vào thùng rác', style: TextStyle(color: Colors.red)),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
        onTap: onOpen,
      ),
    );
  }
}

String _relativeTime(DateTime when) {
  final diff = DateTime.now().difference(when);
  if (diff.inMinutes < 1) return 'vừa xong';
  if (diff.inHours < 1) return '${diff.inMinutes} phút trước';
  if (diff.inDays < 1) return '${diff.inHours} giờ trước';
  if (diff.inDays < 30) return '${diff.inDays} ngày trước';
  return '${when.day}/${when.month}/${when.year}';
}

class _CenteredMessage extends StatelessWidget {
  const _CenteredMessage({
    required this.icon,
    required this.title,
    required this.body,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String body;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final label = actionLabel;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 46, color: Colors.grey),
            const SizedBox(height: 16),
            Text(
              title,
              textAlign: TextAlign.center,
              style: AppTheme.headingFont(
                fontSize: 17,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              body,
              textAlign: TextAlign.center,
              style: AppTheme.bodyFont(
                fontSize: 13,
                color: Colors.grey,
                height: 1.4,
              ),
            ),
            if (label != null && onAction != null) ...[
              const SizedBox(height: 20),
              FilledButton(onPressed: onAction, child: Text(label)),
            ],
          ],
        ),
      ),
    );
  }
}
