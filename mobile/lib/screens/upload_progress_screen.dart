import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';

import '../models/scan_metadata.dart';
import '../services/backend_api.dart';
import 'scan_result_screen.dart';

class UploadProgressScreen extends StatefulWidget {
  const UploadProgressScreen({
    required this.metadata,
    required this.sideVideoFile,
    required this.topVideoFile,
    super.key,
  });

  final ScanMetadata metadata;
  final XFile sideVideoFile;
  final XFile topVideoFile;

  @override
  State<UploadProgressScreen> createState() => _UploadProgressScreenState();
}

class _UploadProgressScreenState extends State<UploadProgressScreen> {
  final _api = BackendApi();
  double _progress = 0;
  int _step = 0;
  String _message = 'Preparing upload';
  bool _failed = false;
  bool _uploading = false;

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
      _uploading = true;
      _progress = 0;
      _step = 0;
      _message = 'Creating scan session';
    });
    try {
      final scanSessionId =
          await _api.createScanSession(metadata: widget.metadata);
      _safeSetState(() {
        _step = 1;
        _message = 'Uploading side orbit';
      });
      await _api.uploadScanPass(
        scanSessionId: scanSessionId,
        passType: 'side-orbit',
        videoFile: widget.sideVideoFile,
        onProgress: _updateProgress,
      );
      _safeSetState(() {
        _step = 2;
        _progress = 0;
        _message = 'Uploading top-angle orbit';
      });
      final result = await _api.uploadScanPass(
        scanSessionId: scanSessionId,
        passType: 'top-orbit',
        videoFile: widget.topVideoFile,
        onProgress: _updateProgress,
      );
      _safeSetState(() {
        _step = 3;
        _progress = 0;
        _message = 'Starting reconstruction';
      });
      final processingStatus =
          await _api.startProcessing(scanSessionId: scanSessionId);
      final processingStarted = processingStatus != 'toolchain_unavailable' &&
          processingStatus != 'failed';
      if (!mounted) {
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ScanResultScreen(
            scanSessionId: result.scanSessionId,
            status: processingStatus,
            processingStarted: processingStarted,
            webDesignUrl: result.webDesignUrl,
          ),
        ),
      );
    } catch (error) {
      _safeSetState(() {
        _failed = true;
        _message = 'Upload failed: $error';
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
      _message = '${_stepLabel()} ${(_progress * 100).round()}%';
    });
  }

  String _stepLabel() {
    return switch (_step) {
      1 => 'Uploading side orbit',
      2 => 'Uploading top-angle orbit',
      3 => 'Starting reconstruction',
      _ => 'Preparing upload',
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
      appBar: AppBar(title: const Text('Upload scan')),
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
              Text(_step == 0 ? 'Preparing' : 'Step $_step of 3',
                  textAlign: TextAlign.center),
              if (_failed) ...[
                const SizedBox(height: 18),
                OutlinedButton.icon(
                  onPressed: _uploading ? null : _upload,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry upload'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
