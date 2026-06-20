import 'package:flutter/material.dart';

import '../models/scan_metadata.dart';
import 'camera_scan_screen.dart';

class ScanSetupScreen extends StatefulWidget {
  const ScanSetupScreen({super.key});

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
      appBar: AppBar(title: const Text('Scan setup')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _DropdownField(
                label: 'Size system',
                value: _sizeSystem,
                values: const ['EU', 'US', 'UK', 'CM'],
                onChanged: (value) => setState(() => _sizeSystem = value),
              ),
              _TextField(label: 'Shoe size', controller: _sizeController),
              _DropdownField(
                label: 'Side',
                value: _side,
                values: const ['left', 'right', 'both'],
                onChanged: (value) => setState(() => _side = value),
              ),
              _DropdownField(
                label: 'Type',
                value: _type,
                values: const ['sneaker', 'running', 'boot', 'sandal', 'other'],
                onChanged: (value) => setState(() => _type = value),
              ),
              _DropdownField(
                label: 'Material',
                value: _material,
                values: const [
                  'canvas',
                  'leather',
                  'synthetic',
                  'mesh',
                  'unknown'
                ],
                onChanged: (value) => setState(() => _material = value),
              ),
              _DropdownField(
                label: 'Condition',
                value: _condition,
                values: const ['new', 'used', 'worn'],
                onChanged: (value) => setState(() => _condition = value),
              ),
              _TextField(
                  label: 'Length in cm',
                  controller: _lengthController,
                  numeric: true),
              _TextField(
                  label: 'Width in cm',
                  controller: _widthController,
                  numeric: true),
              _DropdownField(
                label: 'Calibration reference',
                value: _calibrationReference,
                values: const ['A4 paper', 'ruler', 'printed marker', 'none'],
                onChanged: (value) =>
                    setState(() => _calibrationReference = value),
              ),
              _DropdownField(
                label: 'Lighting',
                value: _lighting,
                values: const ['bright', 'normal', 'dim'],
                onChanged: (value) => setState(() => _lighting = value),
              ),
              _DropdownField(
                label: 'Background',
                value: _background,
                values: const ['plain', 'busy', 'outdoor'],
                onChanged: (value) => setState(() => _background = value),
              ),
              const SizedBox(height: 12),
              Text('Customization goal',
                  style: Theme.of(context).textTheme.titleMedium),
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
                label: const Text('Continue to camera'),
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
      title: Text(goal.replaceAll('_', ' ')),
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
            content:
                Text('A calibration reference improves scale confidence.')),
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
          metadata: metadata,
          pass: ScanPass.sideOrbit,
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
  });

  final String label;
  final String value;
  final List<String> values;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DropdownButtonFormField<String>(
        initialValue: value,
        decoration: InputDecoration(
            labelText: label, border: const OutlineInputBorder()),
        items: values
            .map((item) => DropdownMenuItem(value: item, child: Text(item)))
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
            labelText: label, border: const OutlineInputBorder()),
        validator: (value) {
          if (value == null || value.trim().isEmpty) {
            return 'Required';
          }
          if (numeric && double.tryParse(value) == null) {
            return 'Enter a number';
          }
          return null;
        },
      ),
    );
  }
}
