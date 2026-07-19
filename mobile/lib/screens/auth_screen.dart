import 'package:flutter/material.dart';

import '../app/app_shell.dart';
import '../services/backend_api.dart';
import 'otp_verify_screen.dart';

const _seededAdminEmail = 'admin@kusshoes.vn';
const _seededAdminPassword = 'Admin@12345';

class AuthScreen extends StatefulWidget {
  const AuthScreen({
    this.themeMode = ThemeMode.dark,
    this.onThemeModeChanged,
    super.key,
  });

  final ThemeMode themeMode;
  final ValueChanged<ThemeMode>? onThemeModeChanged;

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _api = BackendApi();
  final _nameController = TextEditingController();
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isRegister = false;
  bool _isBusy = false;
  String? _error;

  @override
  void dispose() {
    _nameController.dispose();
    _usernameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Shoe Scanner')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: false, label: Text('Login')),
                      ButtonSegment(value: true, label: Text('Register')),
                    ],
                    selected: {_isRegister},
                    onSelectionChanged: _isBusy
                        ? null
                        : (values) =>
                            setState(() => _isRegister = values.first),
                  ),
                  const SizedBox(height: 18),
                  if (_isRegister)
                    TextField(
                      controller: _nameController,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(labelText: 'Name'),
                    ),
                  if (_isRegister) const SizedBox(height: 12),
                  if (_isRegister)
                    TextField(
                      controller: _usernameController,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(labelText: 'Username'),
                    ),
                  if (_isRegister) const SizedBox(height: 12),
                  TextField(
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(labelText: 'Email'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Password'),
                  ),
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: _isBusy ? null : _submit,
                    icon: Icon(
                        _isRegister ? Icons.person_add_alt_1 : Icons.login),
                    label: Text(_isRegister ? 'Create account' : 'Login'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: _isBusy ? null : _seededAdminLogin,
                    icon: const Icon(Icons.science_outlined),
                    label: const Text('Use seeded admin (local)'),
                  ),
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

  Future<void> _submit() async {
    setState(() {
      _isBusy = true;
      _error = null;
    });
    try {
      if (_isRegister) {
        final pending = await _api.register(
          name: _nameController.text.trim(),
          username: _usernameController.text.trim(),
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
        _openOtpVerify(pending.userId, pending.email);
      } else {
        await _api.login(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
        _openScanner();
      }
    } catch (error) {
      setState(() => _error = 'Authentication failed: $error');
    } finally {
      if (mounted) {
        setState(() => _isBusy = false);
      }
    }
  }

  Future<void> _seededAdminLogin() async {
    setState(() {
      _isBusy = true;
      _error = null;
    });
    try {
      await _api.login(
        email: _seededAdminEmail,
        password: _seededAdminPassword,
      );
      _openScanner();
    } catch (error) {
      setState(() => _error = 'Seeded admin login failed: $error');
    } finally {
      if (mounted) {
        setState(() => _isBusy = false);
      }
    }
  }

  void _openScanner() {
    if (!mounted) {
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => AppShell(
          themeMode: widget.themeMode,
          onThemeModeChanged: widget.onThemeModeChanged ?? (_) {},
        ),
      ),
    );
  }

  void _openOtpVerify(String userId, String email) {
    if (!mounted) {
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => OtpVerifyScreen(
          api: _api,
          userId: userId,
          email: email,
          themeMode: widget.themeMode,
          onThemeModeChanged: widget.onThemeModeChanged,
        ),
      ),
    );
  }
}
