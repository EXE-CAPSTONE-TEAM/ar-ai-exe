import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../app/app_theme.dart';
import '../config/app_config.dart';
import '../models/kiri_status.dart';
import '../services/api_exception.dart';
import '../services/backend_api.dart';

class ScanResultScreen extends StatefulWidget {
  const ScanResultScreen({
    required this.scanSessionId,
    this.api,
    this.status = 'processing',
    this.processingStarted = true,
    this.webDesignUrl = '',
    this.initialStatus,
    this.projectName = 'Đôi giày của tôi',
    this.isGuest = false,
    super.key,
  });

  final String scanSessionId;
  final BackendApi? api;
  final String status;
  final bool processingStarted;
  final String webDesignUrl;
  final KiriStatus? initialStatus;
  final String projectName;
  final bool isGuest;

  @override
  State<ScanResultScreen> createState() => _ScanResultScreenState();
}

class _ScanResultScreenState extends State<ScanResultScreen> {
  BackendApi get _api => widget.api ?? BackendApi.shared;

  late final TextEditingController _projectNameController;
  Timer? _pollTimer;

  late String _currentStatus;
  int _progress = 0;
  String? _previewUrl;
  bool _loadingPreview = false;
  bool _polling = false;
  bool _saving = false;
  bool _saved = false;
  String? _errorMessage;

  bool get _isDone =>
      _currentStatus == 'completed' ||
      _currentStatus == 'ready' ||
      _currentStatus == 'raw';

  bool get _isFailed =>
      _currentStatus == 'failed' || _currentStatus == 'expired';

  @override
  void initState() {
    super.initState();
    _projectNameController = TextEditingController(text: widget.projectName);
    _currentStatus = widget.initialStatus?.status ?? widget.status;
    _progress = widget.initialStatus?.progress ?? 0;
    _previewUrl = widget.initialStatus?.previewUrl;

    if (_isDone) {
      _fetchPreviewUrl();
    } else if (!_isFailed) {
      _startPolling();
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _projectNameController.dispose();
    super.dispose();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _poll());
    unawaited(_poll());
  }

  Future<void> _poll() async {
    if (_polling) return;
    _polling = true;
    try {
      final status =
          await _api.getKiriStatus(scanSessionId: widget.scanSessionId);
      if (!mounted) return;
      setState(() {
        _currentStatus = status.status;
        _progress = status.progress;
        if (status.errorMessage != null) {
          _errorMessage = status.errorMessage;
        }
      });
      if (_isDone) {
        _pollTimer?.cancel();
        await _fetchPreviewUrl();
      } else if (status.isFailed) {
        _pollTimer?.cancel();
      }
    } catch (error) {
      if (mounted) {
        setState(() => _errorMessage = ApiException.from(error).message);
      }
    } finally {
      _polling = false;
    }
  }

  Future<void> _fetchPreviewUrl() async {
    if (_loadingPreview) return;
    setState(() => _loadingPreview = true);
    try {
      final locationUrl = await _api.getKiriPreviewLocationUrl(
        scanSessionId: widget.scanSessionId,
      );
      if (!mounted) return;
      setState(() {
        _previewUrl = locationUrl;
        _errorMessage = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage =
            'Không thể tải bản xem trước 3D: ${ApiException.from(error).message}';
      });
    } finally {
      if (mounted) {
        setState(() => _loadingPreview = false);
      }
    }
  }

  Future<void> _saveProject() async {
    final name = _projectNameController.text.trim();
    if (name.isEmpty || _saving) return;
    setState(() {
      _saving = true;
      _errorMessage = null;
    });
    try {
      await _api.saveKiriProject(
        scanSessionId: widget.scanSessionId,
        projectName: name,
      );
      if (!mounted) return;
      setState(() => _saved = true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã lưu dự án thành công!')),
      );
    } catch (error) {
      if (!mounted) return;
      final msg = ApiException.from(error).message;
      setState(() => _errorMessage = msg);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Lưu dự án thất bại: $msg')),
      );
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  Future<void> _openDesktop() async {
    final targetUrl = widget.webDesignUrl.isNotEmpty
        ? widget.webDesignUrl
        : AppConfig.webUrl('/design/${widget.scanSessionId}');
    final uri = Uri.parse(targetUrl);
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && mounted) {
      await Clipboard.setData(ClipboardData(text: targetUrl));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã sao chép liên kết mở trên Desktop.')),
      );
    }
  }

  Future<void> _copyScanId(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: widget.scanSessionId));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã sao chép mã phiên quét.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          'AFTERSACN · DỰNG LƯỚI 3D',
          style: AppTheme.monoFont(
            fontSize: 14,
            letterSpacing: 1.2,
            color: AppTheme.orange,
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Checklist Progress Section (SRS v2.2 SC-23)
                    Container(
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: isDark ? AppTheme.darkCard : Colors.white,
                        borderRadius: BorderRadius.circular(22),
                        border: Border.all(
                          color: isDark
                              ? AppTheme.darkCardBorder
                              : const Color(0x18000000),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                'TIẾN TRÌNH DỰNG 3D AI',
                                style: AppTheme.monoFont(
                                  fontSize: 11,
                                  color: AppTheme.orange,
                                  letterSpacing: 1.2,
                                ),
                              ),
                              const Spacer(),
                              _StatusBadge(
                                status: _currentStatus,
                                isProcessing: !_isDone && !_isFailed,
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          _ChecklistRow(
                            title: '1. Đã tải lên video 360°',
                            done: true,
                            isDark: isDark,
                          ),
                          const SizedBox(height: 10),
                          _ChecklistRow(
                            title: '2. AI tái tạo điểm & tạo lưới raw 3D',
                            done: _isDone,
                            isDark: isDark,
                          ),
                          const SizedBox(height: 10),
                          _ChecklistRow(
                            title: '3. Phôi raw sẵn sàng chuyển tiếp Desktop',
                            done: _isDone,
                            isDark: isDark,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),

                    // 3D Model Preview Card (Raw model preview)
                    AspectRatio(
                      aspectRatio: 1.35,
                      child: Container(
                        decoration: BoxDecoration(
                          color: isDark
                              ? const Color(0xFF101014)
                              : const Color(0xFFF3F1EC),
                          borderRadius: BorderRadius.circular(22),
                          border: Border.all(
                            color: AppTheme.orange.withValues(alpha: 0.35),
                          ),
                        ),
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            if (_previewUrl != null)
                              ClipRRect(
                                borderRadius: BorderRadius.circular(22),
                                child: ModelViewer(
                                  src: _previewUrl!,
                                  alt: 'Mô hình quét raw',
                                  ar: false,
                                  autoRotate: true,
                                  cameraControls: true,
                                  backgroundColor: Colors.transparent,
                                ),
                              )
                            else if (_isFailed)
                              Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.error_outline,
                                    size: 48,
                                    color: Theme.of(context).colorScheme.error,
                                  ),
                                  const SizedBox(height: 10),
                                  Text(
                                    'Dựng mô hình thất bại',
                                    style: AppTheme.headingFont(
                                      fontSize: 15,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  if (_errorMessage != null) ...[
                                    const SizedBox(height: 6),
                                    Padding(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 16),
                                      child: Text(
                                        _errorMessage!,
                                        textAlign: TextAlign.center,
                                        style: AppTheme.bodyFont(
                                          fontSize: 12,
                                          color: Colors.grey,
                                        ),
                                      ),
                                    ),
                                  ],
                                  const SizedBox(height: 12),
                                  OutlinedButton.icon(
                                    onPressed: _startPolling,
                                    icon: const Icon(Icons.refresh, size: 16),
                                    label: const Text('Thử lại'),
                                  ),
                                ],
                              )
                            else
                              Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  CircularProgressIndicator(
                                    value: _progress > 0
                                        ? _progress / 100.0
                                        : null,
                                    color: AppTheme.orange,
                                  ),
                                  const SizedBox(height: 14),
                                  Text(
                                    _loadingPreview
                                        ? 'ĐANG TẢI MÔ HÌNH 3D...'
                                        : 'ĐANG DỰNG LƯỚI 3D RAW (${_progress}%)',
                                    style: AppTheme.monoFont(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w700,
                                      color: AppTheme.orange,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Vui lòng chờ trong giây lát',
                                    style: AppTheme.bodyFont(
                                      fontSize: 11,
                                      color: Colors.grey,
                                    ),
                                  ),
                                ],
                              ),
                            Positioned(
                              top: 12,
                              left: 14,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: _isDone
                                      ? AppTheme.statusScanned
                                          .withValues(alpha: 0.15)
                                      : AppTheme.statusProcessing
                                          .withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  _isDone
                                      ? 'RAW MODEL PREVIEW'
                                      : 'ĐANG XỬ LÝ',
                                  style: AppTheme.monoFont(
                                    fontSize: 10,
                                    color: _isDone
                                        ? AppTheme.statusScanned
                                        : AppTheme.statusProcessing,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    // Project name input
                    TextField(
                      controller: _projectNameController,
                      maxLength: 160,
                      decoration: const InputDecoration(
                        labelText: 'Tên dự án',
                        prefixIcon: Icon(Icons.folder_outlined),
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),

                    // Primary Action 1: 'Lưu project'
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _saving ? null : _saveProject,
                        icon: _saving
                            ? const SizedBox.square(
                                dimension: 18,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : Icon(_saved
                                ? Icons.check_circle_outline
                                : Icons.save_alt),
                        label: Text(_saving
                            ? 'Đang lưu project...'
                            : (_saved ? 'Đã lưu project' : 'Lưu project')),
                        style: FilledButton.styleFrom(
                          backgroundColor:
                              _saved ? AppTheme.statusScanned : null,
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),

                    // Primary Action 2: 'Mở trên Desktop'
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: _openDesktop,
                        icon: const Icon(Icons.desktop_windows_outlined),
                        label: const Text('Mở trên Desktop'),
                      ),
                    ),
                    const SizedBox(height: 18),

                    // Session Info
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: isDark ? AppTheme.darkSurface : Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.white12),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'MÃ PHIÊN QUÉT (SCAN ID)',
                                  style: AppTheme.monoFont(
                                      fontSize: 10, color: Colors.grey),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  widget.scanSessionId,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: AppTheme.monoFont(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            onPressed: () => _copyScanId(context),
                            icon: const Icon(Icons.copy,
                                size: 18, color: AppTheme.orange),
                            tooltip: 'Copy ID',
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),

                    // Guest conversion notice (BR-41)
                    if (widget.isGuest) ...[
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppTheme.orange.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                              color: AppTheme.orange.withValues(alpha: 0.35)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.info_outline,
                                color: AppTheme.orange, size: 20),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                'Bạn đang ở Chế độ Khách. Đăng ký tài khoản để lưu mô hình này vĩnh viễn vào bộ sưu tập của bạn.',
                                style: AppTheme.bodyFont(fontSize: 12.5),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                    ],
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
              child: SizedBox(
                width: double.infinity,
                child: TextButton.icon(
                  onPressed: () =>
                      Navigator.of(context).popUntil((route) => route.isFirst),
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: const Text('QUÉT ĐÔI GIÀY KHÁC'),
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.orange,
                    textStyle: AppTheme.headingFont(
                        fontSize: 14, fontWeight: FontWeight.w800),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChecklistRow extends StatelessWidget {
  const _ChecklistRow({
    required this.title,
    required this.done,
    required this.isDark,
  });

  final String title;
  final bool done;
  final bool isDark;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: done
                ? AppTheme.statusScanned
                : Colors.grey.withValues(alpha: 0.3),
          ),
          child: Icon(
            done ? Icons.check : Icons.hourglass_empty,
            size: 14,
            color: done ? Colors.black : Colors.white,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            style: AppTheme.bodyFont(
              fontSize: 13.5,
              fontWeight: done ? FontWeight.w600 : FontWeight.w400,
              color: done
                  ? (isDark ? Colors.white : Colors.black)
                  : Colors.grey,
            ),
          ),
        ),
      ],
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status, required this.isProcessing});

  final String status;
  final bool isProcessing;

  @override
  Widget build(BuildContext context) {
    final color =
        isProcessing ? AppTheme.statusProcessing : AppTheme.statusScanned;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        isProcessing ? 'ĐANG DỰNG LƯỚI' : 'SẴN SÀNG',
        style: AppTheme.monoFont(
          fontSize: 10,
          color: color,
        ),
      ),
    );
  }
}
