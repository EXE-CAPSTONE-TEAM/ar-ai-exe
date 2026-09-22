import 'package:flutter/material.dart';

import '../models/scan_metadata.dart';
import '../services/backend_api.dart';
import 'camera_scan_screen.dart';

/// Vietnamese display names for the wire values the compute service expects.
/// The API value stays the map key, so the request payload is unchanged.
const _sideLabels = {
  'left': 'Chiếc bên trái',
  'right': 'Chiếc bên phải',
  'both': 'Cả đôi',
};
const _typeLabels = {
  'sneaker': 'Sneaker',
  'running': 'Giày chạy bộ',
  'boot': 'Boot',
  'sandal': 'Sandal',
  'other': 'Loại khác',
};
const _materialLabels = {
  'canvas': 'Vải canvas',
  'leather': 'Da',
  'synthetic': 'Da tổng hợp',
  'mesh': 'Lưới (mesh)',
  'unknown': 'Không rõ',
};
const _conditionLabels = {
  'new': 'Mới',
  'used': 'Đã dùng',
  'worn': 'Cũ, sờn nhiều',
};
const _calibrationLabels = {
  'A4 paper': 'Tờ giấy A4',
  'ruler': 'Thước kẻ',
  'printed marker': 'Marker đã in',
  'none': 'Không dùng vật chuẩn',
};
const _lightingLabels = {
  'bright': 'Sáng rõ',
  'normal': 'Bình thường',
  'dim': 'Hơi tối',
};
const _backgroundLabels = {
  'plain': 'Nền trơn',
  'busy': 'Nền nhiều chi tiết',
  'outdoor': 'Ngoài trời',
};
const _goalLabels = {
  'change_color': 'Đổi màu theo vùng',
  'add_sticker': 'Dán sticker',
  'add_text': 'Thêm chữ / chữ ký',
  'draw_pattern': 'Vẽ tay hoạ tiết',
  'add_background_pattern': 'Thêm hoạ tiết nền',
};

class ScanSetupScreen extends StatefulWidget {
  const ScanSetupScreen({required this.api, super.key});

  final BackendApi api;

  @override
  State<ScanSetupScreen> createState() => _ScanSetupScreenState();
}

class _ScanSetupScreenState extends State<ScanSetupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _sizeController = TextEditingController(text: '42');
  final _lengthController = TextEditingController(text: '27.0');
  final _widthController = TextEditingController(text: '9.5');

  String _sizeSystem = 'EU';
  String _side = 'left';
  String _type = 'sneaker';
  String _material = 'canvas';
  String _condition = 'used';
  String _calibrationReference = 'A4 paper';
  String _lighting = 'bright';
  String _background = 'plain';
  final Set<String> _goals = {'change_color', 'add_sticker', 'add_text'};

  @override
  void dispose() {
    _sizeController.dispose();
    _lengthController.dispose();
    _widthController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Thông tin lượt quét')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _DropdownField(
                label: 'Hệ size',
                value: _sizeSystem,
                values: const ['EU', 'US', 'UK', 'CM'],
                onChanged: (value) => setState(() => _sizeSystem = value),
              ),
              _TextField(label: 'Size giày', controller: _sizeController),
              _DropdownField(
                label: 'Chiếc giày',
                value: _side,
                values: const ['left', 'right', 'both'],
                labels: _sideLabels,
                onChanged: (value) => setState(() => _side = value),
              ),
              _DropdownField(
                label: 'Kiểu giày',
                value: _type,
                values: const ['sneaker', 'running', 'boot', 'sandal', 'other'],
                labels: _typeLabels,
                onChanged: (value) => setState(() => _type = value),
              ),
              _DropdownField(
                label: 'Chất liệu',
                value: _material,
                values: const [
                  'canvas',
                  'leather',
                  'synthetic',
                  'mesh',
                  'unknown'
                ],
                labels: _materialLabels,
                onChanged: (value) => setState(() => _material = value),
              ),
              _DropdownField(
                label: 'Tình trạng',
                value: _condition,
                values: const ['new', 'used', 'worn'],
                labels: _conditionLabels,
                onChanged: (value) => setState(() => _condition = value),
              ),
              _TextField(
                label: 'Chiều dài (cm)',
                controller: _lengthController,
                numeric: true,
              ),
              _TextField(
                label: 'Chiều rộng (cm)',
                controller: _widthController,
                numeric: true,
              ),
              _DropdownField(
                label: 'Vật chuẩn để đo tỉ lệ',
                value: _calibrationReference,
                values: const ['A4 paper', 'ruler', 'printed marker', 'none'],
                labels: _calibrationLabels,
                onChanged: (value) =>
                    setState(() => _calibrationReference = value),
              ),
              _DropdownField(
                label: 'Điều kiện sáng',
                value: _lighting,
                values: const ['bright', 'normal', 'dim'],
                labels: _lightingLabels,
                onChanged: (value) => setState(() => _lighting = value),
              ),
              _DropdownField(
                label: 'Phông nền',
                value: _background,
                values: const ['plain', 'busy', 'outdoor'],
                labels: _backgroundLabels,
                onChanged: (value) => setState(() => _background = value),
              ),
              const SizedBox(height: 12),
              Text(
                'Bạn muốn tùy biến gì?',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              ...[
                'change_color',
                'add_sticker',
                'add_text',
                'draw_pattern',
                'add_background_pattern'
              ].map(_goalTile),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _continueToCamera,
                icon: const Icon(Icons.videocam_outlined),
                label: const Text('Tiếp tục tới camera'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _goalTile(String goal) {
    return CheckboxListTile(
      value: _goals.contains(goal),
      title: Text(_goalLabels[goal] ?? goal.replaceAll('_', ' ')),
      onChanged: (checked) {
        setState(() {
          if (checked ?? false) {
            _goals.add(goal);
          } else {
            _goals.remove(goal);
          }
        });
      },
    );
  }

  void _continueToCamera() {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    if (_calibrationReference == 'none') {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Đặt một vật chuẩn (giấy A4, thước kẻ) cạnh giày sẽ giúp AI ước '
            'lượng kích thước chính xác hơn.',
          ),
        ),
      );
    }

    final metadata = ScanMetadata(
      sizeSystem: _sizeSystem,
      size: _sizeController.text.trim(),
      side: _side,
      type: _type,
      material: _material,
      condition: _condition,
      lengthCm: double.parse(_lengthController.text),
      widthCm: double.parse(_widthController.text),
      calibrationReference: _calibrationReference,
      lighting: _lighting,
      background: _background,
      customizationGoal: _goals.toList(),
    );

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => CameraScanScreen(
          api: widget.api,
          metadata: metadata,
        ),
      ),
    );
  }
}

class _DropdownField extends StatelessWidget {
  const _DropdownField({
    required this.label,
    required this.value,
    required this.values,
    required this.onChanged,
    this.labels,
  });

  final String label;
  final String value;
  final List<String> values;
  final ValueChanged<String> onChanged;

  /// Optional display names; the API value is still what gets submitted.
  final Map<String, String>? labels;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DropdownButtonFormField<String>(
        initialValue: value,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
        items: values
            .map(
              (item) => DropdownMenuItem(
                value: item,
                child: Text(labels?[item] ?? item),
              ),
            )
            .toList(),
        onChanged: (value) {
          if (value != null) {
            onChanged(value);
          }
        },
      ),
    );
  }
}

class _TextField extends StatelessWidget {
  const _TextField({
    required this.label,
    required this.controller,
    this.numeric = false,
  });

  final String label;
  final TextEditingController controller;
  final bool numeric;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: controller,
        keyboardType: numeric ? TextInputType.number : TextInputType.text,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
        validator: (value) {
          if (value == null || value.trim().isEmpty) {
            return 'Vui lòng nhập thông tin này';
          }
          if (numeric && double.tryParse(value) == null) {
            return 'Nhập một con số';
          }
          return null;
        },
      ),
    );
  }
}
