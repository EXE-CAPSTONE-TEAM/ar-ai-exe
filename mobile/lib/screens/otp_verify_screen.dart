import 'package:flutter/material.dart';

import '../services/backend_api.dart';
import '../app/app_shell.dart';

class OtpVerifyScreen extends StatefulWidget {
  const OtpVerifyScreen({
    required this.api,
    required this.userId,
    required this.email,
    this.themeMode = ThemeMode.dark,
    this.onThemeModeChanged,
    super.key,
  });

  final BackendApi api;
  final String userId;
  final String email;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode>? onThemeModeChanged;

  @override
  State<OtpVerifyScreen> createState() => _OtpVerifyScreenState();
}

class _OtpVerifyScreenState extends State<OtpVerifyScreen> {
  final _otpController = TextEditingController();
  bool _isBusy = false;
  String? _error;
  String? _info;

  @override
  void dispose() {
    _otpController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Verify email')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('Enter the 6-digit code sent to ${widget.email}'),
                  const SizedBox(height: 18),
                  TextField(
                    controller: _otpController,
                    keyboardType: TextInputType.number,
                    maxLength: 6,
                    decoration: const InputDecoration(labelText: 'OTP code'),
                  ),
                  FilledButton.icon(
                    onPressed: _isBusy ? null : _verify,
                    icon: const Icon(Icons.check_circle_outline),
                    label: const Text('Verify'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: _isBusy ? null : _resend,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Resend code'),
                  ),
                  if (_info != null) ...[
                    const SizedBox(height: 14),
                    Text(_info!),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: 14),
                    Text(_error!,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error)),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _verify() async {
    setState(() {
      _isBusy = true;
      _error = null;
    });
    try {
      await widget.api.verifyOtp(
        userId: widget.userId,
        otpCode: _otpController.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => AppShell(
            themeMode: widget.themeMode,
            onThemeModeChanged: widget.onThemeModeChanged ?? (_) {},
          ),
        ),
      );
    } catch (error) {
      setState(() => _error = 'Verification failed: $error');
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
  }

  Future<void> _resend() async {
    setState(() {
      _isBusy = true;
      _error = null;
      _info = null;
    });
    try {
      await widget.api.resendOtp(userId: widget.userId);
      setState(() => _info = 'A new code was sent.');
    } catch (error) {
      setState(() => _error = 'Resend failed: $error');
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
  }
}
