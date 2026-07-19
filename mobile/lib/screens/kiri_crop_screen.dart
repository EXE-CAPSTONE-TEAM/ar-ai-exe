import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';

import '../models/kiri_status.dart';
import '../services/backend_api.dart';

class KiriCropScreen extends StatefulWidget {
  const KiriCropScreen({
    required this.api,
    required this.scanSessionId,
    required this.initialStatus,
    super.key,
  });

  final BackendApi api;
  final String scanSessionId;
  final KiriStatus initialStatus;

  @override
  State<KiriCropScreen> createState() => _KiriCropScreenState();
}

class _KiriCropScreenState extends State<KiriCropScreen> {
  BackendApi get _api => widget.api;
  final _projectNameController = TextEditingController(text: 'My shoe scan');
  Timer? _pollTimer;
  late KiriStatus _status;
  CropBox _cropBox = const CropBox();
  bool _polling = false;
  bool _saving = false;
  String? _localError;

  @override
  void initState() {
    super.initState();
    _status = widget.initialStatus;
    _cropBox = _status.cropBox ?? const CropBox();
    _schedulePollingIfNeeded();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _projectNameController.dispose();
    super.dispose();
  }

  void _schedulePollingIfNeeded() {
    if (_status.canCrop || _status.isReady || _status.isFailed) {
      return;
    }
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _poll());
    unawaited(_poll());
  }

  Future<void> _poll() async {
    if (_polling) return;
    _polling = true;
    try {
      final next = await _api.getKiriStatus(scanSessionId: widget.scanSessionId);
      if (!mounted) return;
      setState(() {
        _status = next;
        _localError = null;
        if (next.cropBox != null) _cropBox = next.cropBox!;
      });
      if (next.canCrop || next.isReady || next.isFailed) {
        _pollTimer?.cancel();
      }
    } catch (error) {
      if (mounted) setState(() => _localError = _message(error));
    } finally {
      _polling = false;
    }
  }

  Future<void> _saveProject() async {
    final projectName = _projectNameController.text.trim();
    if (projectName.isEmpty || _saving) return;
    setState(() {
      _saving = true;
      _localError = null;
    });
    try {
      await _api.configureCrop(
        scanSessionId: widget.scanSessionId,
        cropBox: _cropBox,
      );
      final next = await _api.saveKiriProject(
        scanSessionId: widget.scanSessionId,
        projectName: projectName,
        cropBox: _cropBox,
      );
      if (!mounted) return;
      setState(() => _status = next);
      _schedulePollingIfNeeded();
    } catch (error) {
      if (mounted) setState(() => _localError = _message(error));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Prepare 3D model'),
        actions: [
          if (_status.canCrop)
            IconButton(
              tooltip: 'Reset crop box',
              onPressed: () => setState(() => _cropBox = const CropBox()),
              icon: const Icon(Icons.restart_alt),
            ),
        ],
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_status.isReady) return _ReadyView(status: _status);
    if (!_status.canCrop) return _ProcessingView(status: _status, error: _localError, onRetry: _poll);

    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
            children: [
              AspectRatio(
                aspectRatio: 4 / 3,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: ColoredBox(
                    color: Theme.of(context).colorScheme.surfaceContainerLowest,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        if (_status.previewUrl case final previewUrl?)
                          ModelViewer(
                            src: previewUrl,
                            alt: 'Scanned shoe model',
                            ar: false,
                            autoRotate: false,
                            cameraControls: true,
                            backgroundColor: Colors.transparent,
                          )
                        else
                          const Center(child: CircularProgressIndicator()),
                        IgnorePointer(
                          child: CustomPaint(painter: _CropBoxPainter(_cropBox)),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text('Position', style: Theme.of(context).textTheme.titleMedium),
              _AxisSliders(
                value: _cropBox.center,
                minimum: -0.5,
                maximum: 0.5,
                onChanged: (value) => setState(() => _cropBox = _cropBox.copyWith(center: value)),
              ),
              const Divider(height: 32),
              Text('Crop size', style: Theme.of(context).textTheme.titleMedium),
              _AxisSliders(
                value: _cropBox.size,
                minimum: 0.05,
                maximum: 1,
                onChanged: (value) => setState(() => _cropBox = _cropBox.copyWith(size: value)),
              ),
              const Divider(height: 32),
              Text('Alignment', style: Theme.of(context).textTheme.titleMedium),
              _AxisSliders(
                value: _cropBox.rotation,
                minimum: -180,
                maximum: 180,
                divisions: 72,
                suffix: 'deg',
                onChanged: (value) => setState(() => _cropBox = _cropBox.copyWith(rotation: value)),
              ),
              const SizedBox(height: 18),
              TextField(
                controller: _projectNameController,
                maxLength: 160,
                decoration: const InputDecoration(
                  labelText: 'Project name',
                  prefixIcon: Icon(Icons.folder_outlined),
                ),
              ),
              if (_localError != null || _status.errorMessage != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    _localError ?? _status.errorMessage!,
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _saving ? null : _saveProject,
              icon: _saving
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.cloud_upload_outlined),
              label: Text(_saving ? 'Saving project' : 'Save project'),
            ),
          ),
        ),
      ],
    );
  }

  String _message(Object error) => error.toString().replaceFirst('Exception: ', '');
}

class _AxisSliders extends StatelessWidget {
  const _AxisSliders({
    required this.value,
    required this.minimum,
    required this.maximum,
    required this.onChanged,
    this.divisions = 100,
    this.suffix = '',
  });

  final CropAxis value;
  final double minimum;
  final double maximum;
  final int divisions;
  final String suffix;
  final ValueChanged<CropAxis> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _slider('X', value.x, (next) => onChanged(value.copyWith(x: next))),
        _slider('Y', value.y, (next) => onChanged(value.copyWith(y: next))),
        _slider('Z', value.z, (next) => onChanged(value.copyWith(z: next))),
      ],
    );
  }

  Widget _slider(String axis, double current, ValueChanged<double> onChanged) {
    return Row(
      children: [
        SizedBox(width: 20, child: Text(axis)),
        Expanded(
          child: Slider(
            value: current.clamp(minimum, maximum),
            min: minimum,
            max: maximum,
            divisions: divisions,
            label: '${current.toStringAsFixed(suffix.isEmpty ? 2 : 0)}$suffix',
            onChanged: onChanged,
          ),
        ),
        SizedBox(
          width: 58,
          child: Text(
            '${current.toStringAsFixed(suffix.isEmpty ? 2 : 0)}$suffix',
            textAlign: TextAlign.end,
          ),
        ),
      ],
    );
  }
}

class _ProcessingView extends StatelessWidget {
  const _ProcessingView({required this.status, required this.error, required this.onRetry});

  final KiriStatus status;
  final String? error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final message = error ?? status.errorMessage;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (!status.isFailed) ...[
              CircularProgressIndicator(value: status.progress == 0 ? null : status.progress / 100),
              const SizedBox(height: 20),
              Text('Creating your 3D model', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text('${status.progress}% complete'),
            ] else ...[
              Icon(Icons.error_outline, size: 44, color: Theme.of(context).colorScheme.error),
              const SizedBox(height: 12),
              Text('Model processing stopped', style: Theme.of(context).textTheme.titleLarge),
            ],
            if (message != null) ...[
              const SizedBox(height: 12),
              Text(message, textAlign: TextAlign.center),
            ],
            if (message != null) ...[
              const SizedBox(height: 18),
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Check again'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ReadyView extends StatelessWidget {
  const _ReadyView({required this.status});

  final KiriStatus status;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_done_outlined, size: 52, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 16),
            Text('Project saved', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            const Text(
              'Your 3D model is ready in the desktop app.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
              icon: const Icon(Icons.add_a_photo_outlined),
              label: const Text('Scan another product'),
            ),
          ],
        ),
      ),
    );
  }
}

class _CropBoxPainter extends CustomPainter {
  const _CropBoxPainter(this.cropBox);

  final CropBox cropBox;

  @override
  void paint(Canvas canvas, Size canvasSize) {
    final boxWidth = canvasSize.width * 0.72 * cropBox.size.x;
    final boxHeight = canvasSize.height * 0.72 * cropBox.size.y;
    final center = Offset(
      canvasSize.width * (0.5 + cropBox.center.x * 0.65),
      canvasSize.height * (0.5 - cropBox.center.y * 0.65),
    );
    final depth = 8 + 18 * cropBox.size.z;
    final paint = Paint()
      ..color = const Color(0xFFEAC54F)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(cropBox.rotation.z * math.pi / 180);
    final front = Rect.fromCenter(center: Offset.zero, width: boxWidth, height: boxHeight);
    final back = front.shift(Offset(depth, -depth));
    canvas.drawRect(front, paint);
    canvas.drawRect(back, paint);
    for (final point in [front.topLeft, front.topRight, front.bottomLeft, front.bottomRight]) {
      canvas.drawLine(point, point + Offset(depth, -depth), paint);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _CropBoxPainter oldDelegate) => oldDelegate.cropBox != cropBox;
}
