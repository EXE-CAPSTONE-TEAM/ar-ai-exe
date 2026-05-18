import 'dart:io';

import 'package:flutter/material.dart';

import '../models/scan_metadata.dart';
import '../services/backend_api.dart';
import 'scan_result_screen.dart';

class UploadProgressScreen extends StatefulWidget {
  const UploadProgressScreen({
    required this.metadata,
    required this.videoFile,
    super.key,
  });

  final ScanMetadata metadata;
  final File videoFile;

  @override
  State<UploadProgressScreen> createState() => _UploadProgressScreenState();
}

class _UploadProgressScreenState extends State<UploadProgressScreen> {
  final _api = BackendApi();
  double _progress = 0;
  String _message = 'Preparing upload';

  @override
  void initState() {
    super.initState();
    _upload();
  }

  Future<void> _upload() async {
    try {
      final scanSessionId = await _api.createScanSession();
      final result = await _api.uploadScan(
        scanSessionId: scanSessionId,
        videoFile: widget.videoFile,
        metadata: widget.metadata,
        onProgress: (sent, total) {
          if (total > 0) {
            setState(() {
              _progress = sent / total;
              _message = 'Uploading ${(_progress * 100).round()}%';
            });
          }
        },
      );
      if (!mounted) {
        return;
      }
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ScanResultScreen(
            scanSessionId: result.scanSessionId,
            status: result.status,
            processingStarted: result.processingStarted,
            webDesignUrl: result.webDesignUrl,
          ),
        ),
      );
    } catch (error) {
      setState(() => _message = 'Upload failed: $error');
    }
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
            ],
          ),
        ),
      ),
    );
  }
}
