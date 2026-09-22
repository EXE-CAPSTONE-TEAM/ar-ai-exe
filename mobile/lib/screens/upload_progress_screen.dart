import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../models/scan_metadata.dart';
import '../services/api_exception.dart';
import '../services/backend_api.dart';
import 'scan_result_screen.dart';

class UploadProgressScreen extends StatefulWidget {
  const UploadProgressScreen({
    required this.api,
    required this.metadata,
    required this.videoFile,
    this.sideVideoFile,
    this.topVideoFile,
    super.key,
  });

  final BackendApi api;
  final ScanMetadata metadata;
  final XFile videoFile;
  final XFile? sideVideoFile;
  final XFile? topVideoFile;

  @override
  State<UploadProgressScreen> createState() => _UploadProgressScreenState();
}

class _UploadProgressScreenState extends State<UploadProgressScreen> {
  BackendApi get _api => widget.api;

  /// One id for this scan attempt and every retry of it. `scans/bootstrap` is
  /// idempotent on this value, so reusing it makes a retry resume the same
  /// project instead of creating another empty one (and burning another scan).
  final String _clientRequestId = BackendApi.newScanRequestId();

  /// Kept across retries so a re-upload reuses the session already created on
  /// the compute service.
  String? _scanSessionId;

  double _progress = 0;
  int _step = 0;
  String _message = 'Đang chuẩn bị tải lên';
  bool _failed = false;
  bool _uploading = false;

  /// Set when the session is gone for good: a retry cannot help.
  bool _needsSignIn = false;

  @override
  void initState() {
    super.initState();
    _upload();
  }

  Future<void> _upload() async {
    if (_uploading) {
      return;
    }
    setState(() {
      _failed = false;
      _needsSignIn = false;
      _uploading = true;
      _progress = 0;
      _step = 0;
      _message = 'Đang tạo dự án';
    });
    try {
      await _api.beginScan(
        projectName: '${widget.metadata.type} scan',
        clientRequestId: _clientRequestId,
      );

      _safeSetState(() => _message = 'Đang tạo phiên quét');
      final scanSessionId = _scanSessionId ??=
          await _api.createScanSession(metadata: widget.metadata);

      _safeSetState(() {
        _step = 1;
        _message = _stepLabel(1);
      });
      await _api.uploadScanPass(
        scanSessionId: scanSessionId,
        passType: 'single-video',
        videoFile: widget.videoFile,
        onProgress: _updateProgress,
      );

      _safeSetState(() {
        _step = 2;
        _progress = 0;
        _message = _stepLabel(2);
      });
      final kiriStatus =
          await _api.startKiriProcessing(scanSessionId: scanSessionId);
      if (!mounted) {
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ScanResultScreen(
            scanSessionId: scanSessionId,
            status: kiriStatus.status,
            processingStarted: true,
            webDesignUrl: AppConfig.webUrl('/design/$scanSessionId'),
          ),
        ),
      );
    } on ApiException catch (error) {
      _safeSetState(() {
        _failed = true;
        _needsSignIn = error.isAuthExpired;
        _message = error.message;
      });
    } catch (error) {
      _safeSetState(() {
        _failed = true;
        _message = 'Tải lên thất bại. $error';
      });
    } finally {
      _safeSetState(() => _uploading = false);
    }
  }

  void _updateProgress(int sent, int total) {
    if (total <= 0) {
      return;
    }
    _safeSetState(() {
      _progress = sent / total;
      _message = '${_stepLabel(_step)} ${(_progress * 100).round()}%';
    });
  }

  String _stepLabel(int step) {
    return switch (step) {
      1 => 'Đang tải video 360° lên',
      2 => 'Đang gửi tới dịch vụ dựng 3D AI (KIRI Engine)',
      _ => 'Đang chuẩn bị tải lên',
    };
  }

  void _safeSetState(VoidCallback update) {
    if (!mounted) {
      return;
    }
    setState(update);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Tải lượt quét lên')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              LinearProgressIndicator(value: _progress == 0 ? null : _progress),
              const SizedBox(height: 16),
              Text(_message, textAlign: TextAlign.center),
              const SizedBox(height: 8),
              Text(
                _step == 0 ? 'Đang chuẩn bị' : 'Bước $_step / 2',
                textAlign: TextAlign.center,
              ),
              if (_failed) ...[
                const SizedBox(height: 18),
                if (_needsSignIn)
                  OutlinedButton.icon(
                    onPressed: () =>
                        Navigator.of(context).popUntil((route) => route.isFirst),
                    icon: const Icon(Icons.login),
                    label: const Text('Đăng nhập lại'),
                  )
                else
                  OutlinedButton.icon(
                    onPressed: _uploading ? null : _upload,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Thử tải lên lại'),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
