import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../models/scan_metadata.dart';
import '../widgets/scan_guide_overlay.dart';
import 'upload_progress_screen.dart';

enum ScanPass {
  sideOrbit,
  topOrbit;

  String get apiValue => switch (this) {
        ScanPass.sideOrbit => 'side-orbit',
        ScanPass.topOrbit => 'top-orbit',
      };

  String get title => switch (this) {
        ScanPass.sideOrbit => 'Side orbit',
        ScanPass.topOrbit => 'Top-angle orbit',
      };

  String get idleInstruction => switch (this) {
        ScanPass.sideOrbit =>
          'Keep the phone level with the shoe side and orbit 360 degrees.',
        ScanPass.topOrbit =>
          'Hold the phone 30-45 degrees above the shoe and orbit 360 degrees.',
      };

  String get recordingInstruction => switch (this) {
        ScanPass.sideOrbit =>
          'Move slowly around the shoe side. Keep the shoe centered.',
        ScanPass.topOrbit =>
          'Keep the upper visible while orbiting. Avoid scanning the sole.',
      };
}

class CameraScanScreen extends StatefulWidget {
  const CameraScanScreen({
    required this.metadata,
    required this.pass,
    this.sideVideoFile,
    super.key,
  });

  final ScanMetadata metadata;
  final ScanPass pass;
  final XFile? sideVideoFile;

  @override
  State<CameraScanScreen> createState() => _CameraScanScreenState();
}

class _CameraScanScreenState extends State<CameraScanScreen> {
  CameraController? _controller;
  Timer? _timer;
  int _seconds = 0;
  bool _isRecording = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _initializeCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() => _error = 'No camera found on this device.');
        return;
      }
      final controller = CameraController(cameras.first, ResolutionPreset.high,
          enableAudio: false);
      await controller.initialize();
      setState(() => _controller = controller);
    } catch (error) {
      setState(() => _error = 'Camera initialization failed: $error');
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    return Scaffold(
      appBar: AppBar(title: Text(widget.pass.title)),
      body: SafeArea(
        child: _error != null
            ? Center(child: Text(_error!))
            : controller == null || !controller.value.isInitialized
                ? const Center(child: CircularProgressIndicator())
                : Stack(
                    children: [
                      Positioned.fill(child: CameraPreview(controller)),
                      Positioned.fill(
                        child: ScanGuideOverlay(
                          seconds: _seconds,
                          isRecording: _isRecording,
                          passTitle: widget.pass.title,
                          idleInstruction: widget.pass.idleInstruction,
                          recordingInstruction:
                              widget.pass.recordingInstruction,
                        ),
                      ),
                      Positioned(
                        left: 16,
                        right: 16,
                        bottom: 24,
                        child: FilledButton.icon(
                          onPressed:
                              _isRecording ? _stopRecording : _startRecording,
                          icon: Icon(_isRecording
                              ? Icons.stop
                              : Icons.fiber_manual_record),
                          label: Text(_isRecording
                              ? 'Stop recording'
                              : 'Start recording'),
                        ),
                      ),
                    ],
                  ),
      ),
    );
  }

  Future<void> _startRecording() async {
    final controller = _controller;
    if (controller == null || _isRecording) {
      return;
    }
    await controller.startVideoRecording();
    setState(() {
      _isRecording = true;
      _seconds = 0;
    });
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      setState(() => _seconds += 1);
    });
  }

  Future<void> _stopRecording() async {
    final controller = _controller;
    if (controller == null || !_isRecording) {
      return;
    }
    _timer?.cancel();
    final video = await controller.stopVideoRecording();
    setState(() => _isRecording = false);
    if (!mounted) {
      return;
    }
    if (widget.pass == ScanPass.sideOrbit) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => CameraScanScreen(
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
      setState(() => _error = 'Side orbit video is missing. Restart the scan.');
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => UploadProgressScreen(
          metadata: widget.metadata,
          sideVideoFile: sideVideoFile,
          topVideoFile: video,
        ),
      ),
    );
  }
}
