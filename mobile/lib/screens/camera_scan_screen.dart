import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../config/app_config.dart';
import '../models/scan_metadata.dart';
import '../services/backend_api.dart';
import '../widgets/scan_guide_overlay.dart';
import 'upload_progress_screen.dart';

/// BR-34: a Scan Job accepts a video of at most 60 seconds, and at most 200MB
/// in total across both passes. Recording stops automatically at the cap so an
/// over-long clip is never uploaded only to be rejected.
const maxPassDuration = Duration(seconds: 60);

/// Below this a 360-degree orbit cannot have been completed; the provider
/// would fail reconstruction and BR-36 only refunds one bad input per cycle.
const minPassDuration = Duration(seconds: 10);

/// Recommended floor from the scan guide ("xoay quanh đôi giày 30-60 giây").
const recommendedPassDuration = Duration(seconds: 30);

/// BR-34 total budget for one Scan Job, across both passes.
const maxJobBytes = 200 * 1024 * 1024;

enum ScanPass {
  sideOrbit,
  topOrbit;

  String get apiValue => switch (this) {
        ScanPass.sideOrbit => 'side-orbit',
        ScanPass.topOrbit => 'top-orbit',
      };

  String get title => switch (this) {
        ScanPass.sideOrbit => 'Vòng quét ngang',
        ScanPass.topOrbit => 'Vòng quét chéo trên',
      };

  String get idleInstruction => switch (this) {
        ScanPass.sideOrbit =>
          'Giữ máy ngang tầm thân giày và đi vòng quanh 360°.',
        ScanPass.topOrbit =>
          'Giữ máy chếch 30-45° từ trên xuống và đi vòng quanh 360°.',
      };

  String get recordingInstruction => switch (this) {
        ScanPass.sideOrbit =>
          'Di chuyển chậm quanh thân giày. Giữ giày ở giữa khung.',
        ScanPass.topOrbit =>
          'Giữ phần mũ giày trong khung. Không cần quét đế giày.',
      };
}

class CameraScanScreen extends StatefulWidget {
  const CameraScanScreen({
    required this.api,
    required this.metadata,
    required this.pass,
    this.sideVideoFile,
    super.key,
  });

  final BackendApi api;
  final ScanMetadata metadata;
  final ScanPass pass;
  final XFile? sideVideoFile;

  @override
  State<CameraScanScreen> createState() => _CameraScanScreenState();
}

class _CameraScanScreenState extends State<CameraScanScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  Timer? _timer;
  int _seconds = 0;
  bool _isRecording = false;
  bool _isStopping = false;
  String? _error;

  /// True when the camera is unavailable because the user declined: the fix is
  /// in system settings, not a retry, so the UI offers a different action.
  bool _permissionDenied = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _requestPermissionThenStart();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    WakelockPlus.disable();
    _controller?.dispose();
    super.dispose();
  }

  /// Android reclaims the camera when the app goes to the background, so the
  /// controller must be torn down and rebuilt rather than reused on resume.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      if (_isRecording) {
        // An interrupted orbit is not usable; drop it rather than upload a
        // half-circle the provider will reject.
        unawaited(_abandonRecording());
      }
      _controller = null;
      unawaited(controller.dispose());
      if (mounted) {
        setState(() {});
      }
    } else if (state == AppLifecycleState.resumed) {
      unawaited(_initializeCamera());
    }
  }

  // --- Permission -----------------------------------------------------------

  Future<void> _requestPermissionThenStart() async {
    final status = await Permission.camera.status;
    if (status.isGranted) {
      await _initializeCamera();
      return;
    }
    // NFR-LEG-06 and the APKPure listing both require saying why the camera is
    // needed before the OS prompt appears, with a privacy-policy link.
    final accepted = await _showRationale();
    if (!accepted) {
      _setPermissionDenied();
      return;
    }
    final result = await Permission.camera.request();
    if (result.isGranted) {
      await _initializeCamera();
    } else {
      _setPermissionDenied();
    }
  }

  Future<bool> _showRationale() async {
    if (!mounted) {
      return false;
    }
    final accepted = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('KusShoes cần quyền camera'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Camera chỉ dùng để quay video đôi giày của bạn trong lúc quét, '
              'rồi gửi lên dịch vụ dựng lưới 3D. KusShoes không quay khi bạn '
              'ở màn hình khác và không truy cập thư viện ảnh của bạn.',
            ),
            // Hidden until SC-33 ships a real legal page; a link to a 404
            // would be worse than no link (NFR-LEG-06).
            if (AppConfig.hasPrivacyPolicyUrl) ...[
              const SizedBox(height: 12),
              TextButton(
                onPressed: () => launchUrl(
                  Uri.parse(AppConfig.privacyPolicyUrl),
                  mode: LaunchMode.externalApplication,
                ),
                child: const Text('Xem Chính sách bảo mật'),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Để sau'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Cho phép'),
          ),
        ],
      ),
    );
    return accepted ?? false;
  }

  void _setPermissionDenied() {
    if (!mounted) {
      return;
    }
    setState(() {
      _permissionDenied = true;
      _error = 'Chưa có quyền camera nên không thể quét. Bạn có thể bật lại '
          'quyền trong Cài đặt của điện thoại.';
    });
  }

  // --- Camera ---------------------------------------------------------------

  Future<void> _initializeCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        _setError('Không tìm thấy camera trên thiết bị này.');
        return;
      }
      // The first entry is not guaranteed to be the rear lens on every device.
      final camera = cameras.firstWhere(
        (item) => item.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      final controller = await _initializeAtBestResolution(camera);
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _error = null;
        _permissionDenied = false;
      });
    } on CameraException catch (error) {
      if (error.code == 'CameraAccessDenied' ||
          error.code == 'CameraAccessDeniedWithoutPrompt' ||
          error.code == 'CameraAccessRestricted') {
        _setPermissionDenied();
        return;
      }
      _setError('Không khởi động được camera (${error.code}). '
          'Đóng các ứng dụng đang dùng camera rồi thử lại.');
    } catch (_) {
      _setError(
        'Không khởi động được camera. Thử lại hoặc mở lại ứng dụng.',
      );
    }
  }

  /// BR-34 asks for 1080p where the device supports it, with 720p as the floor.
  Future<CameraController> _initializeAtBestResolution(
    CameraDescription camera,
  ) async {
    for (final preset in [ResolutionPreset.veryHigh, ResolutionPreset.high]) {
      final controller = CameraController(camera, preset, enableAudio: false);
      try {
        await controller.initialize();
        return controller;
      } on CameraException {
        await controller.dispose();
        if (preset == ResolutionPreset.high) {
          rethrow;
        }
      }
    }
    throw CameraException('unavailable', 'No supported resolution preset.');
  }

  void _setError(String message) {
    if (!mounted) {
      return;
    }
    setState(() => _error = message);
  }

  // --- Recording ------------------------------------------------------------

  Future<void> _startRecording() async {
    final controller = _controller;
    if (controller == null || _isRecording) {
      return;
    }
    try {
      await controller.startVideoRecording();
    } on CameraException catch (error) {
      _setError('Không bắt đầu ghi được (${error.code}). Vui lòng thử lại.');
      return;
    }
    await WakelockPlus.enable();
    if (!mounted) {
      return;
    }
    setState(() {
      _isRecording = true;
      _seconds = 0;
      _error = null;
    });
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted) {
        return;
      }
      setState(() => _seconds += 1);
      if (_seconds >= maxPassDuration.inSeconds) {
        // Hard stop at the BR-34 ceiling.
        unawaited(_stopRecording(reachedCap: true));
      }
    });
  }

  Future<void> _stopRecording({bool reachedCap = false}) async {
    final controller = _controller;
    if (controller == null || !_isRecording || _isStopping) {
      return;
    }
    if (!reachedCap && _seconds < minPassDuration.inSeconds) {
      final remaining = minPassDuration.inSeconds - _seconds;
      _showSnack(
        'Quay thêm khoảng $remaining giây nữa để AI đủ dữ liệu dựng lưới 3D.',
      );
      return;
    }
    _isStopping = true;
    _timer?.cancel();
    try {
      final video = await controller.stopVideoRecording();
      await WakelockPlus.disable();
      if (!mounted) {
        return;
      }
      setState(() => _isRecording = false);

      if (await _rejectIfOverBudget(video)) {
        return;
      }
      if (_seconds < recommendedPassDuration.inSeconds) {
        _showSnack(
          'Vòng quét hơi ngắn ($_seconds giây). Chất lượng lưới 3D có thể thấp.',
        );
      }
      if (mounted) {
        _goToNextStep(video);
      }
    } on CameraException catch (error) {
      await WakelockPlus.disable();
      _setError('Không lưu được video (${error.code}). Hãy quét lại vòng này.');
      if (mounted) {
        setState(() => _isRecording = false);
      }
    } finally {
      _isStopping = false;
    }
  }

  /// Drops a recording that was cut short by the app being backgrounded.
  Future<void> _abandonRecording() async {
    _timer?.cancel();
    await WakelockPlus.disable();
    try {
      await _controller?.stopVideoRecording();
    } on CameraException {
      // Nothing to salvage.
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _isRecording = false;
      _seconds = 0;
      _error =
          'Lượt quay bị ngắt khi bạn rời ứng dụng. Hãy quay lại vòng quét này.';
    });
  }

  /// BR-34: both passes together must stay under 200MB.
  Future<bool> _rejectIfOverBudget(XFile video) async {
    var total = await File(video.path).length();
    final sideVideo = widget.sideVideoFile;
    if (sideVideo != null) {
      total += await File(sideVideo.path).length();
    }
    if (total <= maxJobBytes) {
      return false;
    }
    final megabytes = (total / (1024 * 1024)).round();
    _setError(
      'Video quá lớn ($megabytes MB, giới hạn 200MB cho một lượt quét). '
      'Hãy quay lại với thời lượng ngắn hơn.',
    );
    return true;
  }

  void _goToNextStep(XFile video) {
    if (widget.pass == ScanPass.sideOrbit) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => CameraScanScreen(
            api: widget.api,
            metadata: widget.metadata,
            pass: ScanPass.topOrbit,
            sideVideoFile: video,
          ),
        ),
      );
      return;
    }

    final sideVideoFile = widget.sideVideoFile;
    if (sideVideoFile == null) {
      _setError('Thiếu video vòng quét ngang. Hãy bắt đầu lại lượt quét.');
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => UploadProgressScreen(
          api: widget.api,
          metadata: widget.metadata,
          sideVideoFile: sideVideoFile,
          topVideoFile: video,
        ),
      ),
    );
  }

  void _showSnack(String message) {
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  // --- UI -------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.pass.title)),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    final error = _error;
    final controller = _controller;

    if (error != null && controller == null) {
      return _ErrorState(
        message: error,
        actionLabel: _permissionDenied ? 'Mở Cài đặt' : 'Thử lại',
        onAction:
            _permissionDenied ? openAppSettings : _requestPermissionThenStart,
      );
    }
    if (controller == null || !controller.value.isInitialized) {
      return const Center(child: CircularProgressIndicator());
    }

    final remaining = maxPassDuration.inSeconds - _seconds;
    return Stack(
      children: [
        Positioned.fill(child: CameraPreview(controller)),
        Positioned.fill(
          child: ScanGuideOverlay(
            seconds: _seconds,
            isRecording: _isRecording,
            passTitle: widget.pass.title,
            idleInstruction: widget.pass.idleInstruction,
            recordingInstruction: widget.pass.recordingInstruction,
          ),
        ),
        if (error != null)
          Positioned(
            left: 16,
            right: 16,
            top: 12,
            child: Material(
              color: Theme.of(context).colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  error,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                ),
              ),
            ),
          ),
        Positioned(
          left: 16,
          right: 16,
          bottom: 24,
          child: Column(
            children: [
              if (_isRecording)
                Text(
                  'Còn $remaining giây · tối đa ${maxPassDuration.inSeconds} giây',
                  style: const TextStyle(color: Colors.white),
                ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _isStopping
                    ? null
                    : (_isRecording ? _stopRecording : _startRecording),
                icon: Icon(
                  _isRecording ? Icons.stop : Icons.fiber_manual_record,
                ),
                label: Text(_isRecording ? 'Dừng ghi' : 'Bắt đầu ghi'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({
    required this.message,
    required this.actionLabel,
    required this.onAction,
  });

  final String message;
  final String actionLabel;
  final VoidCallback onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.videocam_off_outlined, size: 44),
            const SizedBox(height: 16),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 22),
            FilledButton(onPressed: onAction, child: Text(actionLabel)),
          ],
        ),
      ),
    );
  }
}
