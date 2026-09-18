import 'package:flutter/material.dart';

import '../app/app_shell.dart';
import '../app/app_theme.dart';
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Brand Logo & Header
                  Center(
                    child: Container(
                      width: 64,
                      height: 64,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [AppTheme.orange, AppTheme.crimson],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: AppTheme.orange.withValues(alpha: 0.35),
                            blurRadius: 24,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        'K',
                        style: AppTheme.headingFont(
                          fontSize: 32,
                          fontWeight: FontWeight.w900,
                          color: Colors.black,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    'KusShoes',
                    textAlign: TextAlign.center,
                    style: AppTheme.headingFont(
                      fontSize: 28,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Tiếp tục thiết kế đôi giày cá nhân hóa bằng AI',
                    textAlign: TextAlign.center,
                    style: AppTheme.bodyFont(
                      fontSize: 14,
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.72),
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 28),

                  // Guest Mode Trial Button (BR-41 & User Decision)
                  Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          AppTheme.orange.withValues(alpha: 0.14),
                          AppTheme.crimson.withValues(alpha: 0.08),
                        ],
                      ),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: AppTheme.orange.withValues(alpha: 0.45),
                        width: 1.4,
                      ),
                    ),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: AppTheme.orange,
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: const Icon(Icons.flash_on, color: Colors.black, size: 20),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Dùng thử Chế độ Khách',
                                    style: AppTheme.headingFont(
                                      fontSize: 15,
                                      fontWeight: FontWeight.w800,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    'Trải nghiệm 1 lượt quét AI thật không cần đăng nhập',
                                    style: AppTheme.bodyFont(
                                      fontSize: 12,
                                      color: Theme.of(context)
                                          .colorScheme
                                          .onSurface
                                          .withValues(alpha: 0.7),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        FilledButton(
                          onPressed: _isBusy ? null : _continueAsGuest,
                          style: FilledButton.styleFrom(
                            backgroundColor: AppTheme.orange,
                            foregroundColor: Colors.black,
                            minimumSize: const Size.fromHeight(46),
                          ),
                          child: const Text('BẮT ĐẦU QUÉT THỬ NGHIỆM'),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  Row(
                    children: [
                      const Expanded(child: Divider(color: Colors.white12)),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Text(
                          'HOẶC ĐĂNG NHẬP',
                          style: AppTheme.monoFont(
                            fontSize: 11,
                            color: Colors.grey,
                            letterSpacing: 1.0,
                          ),
                        ),
                      ),
                      const Expanded(child: Divider(color: Colors.white12)),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // Login / Register Form Container
                  Card(
                    color: isDark ? AppTheme.darkCard : Colors.white,
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          SegmentedButton<bool>(
                            segments: const [
                              ButtonSegment(value: false, label: Text('Đăng nhập')),
                              ButtonSegment(value: true, label: Text('Đăng ký')),
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
                              decoration: const InputDecoration(labelText: 'Họ và tên'),
                            ),
                          if (_isRegister) const SizedBox(height: 12),
                          if (_isRegister)
                            TextField(
                              controller: _usernameController,
                              textInputAction: TextInputAction.next,
                              decoration: const InputDecoration(labelText: 'Tên người dùng'),
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
                            decoration: const InputDecoration(labelText: 'Mật khẩu'),
                          ),
                          const SizedBox(height: 20),
                          FilledButton.icon(
                            onPressed: _isBusy ? null : _submit,
                            icon: Icon(
                                _isRegister ? Icons.person_add_alt_1 : Icons.login),
                            label: Text(_isRegister ? 'Tạo tài khoản' : 'Đăng nhập'),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),

                  // Google OAuth button
                  OutlinedButton.icon(
                    onPressed: _isBusy ? null : () => _continueAsGuest(),
                    icon: const Icon(Icons.g_mobiledata, size: 28, color: AppTheme.orange),
                    label: const Text('Tiếp tục với Google / Gmail'),
                  ),
                  const SizedBox(height: 10),

                  // Seeded Admin for Dev Testing
                  TextButton.icon(
                    onPressed: _isBusy ? null : _seededAdminLogin,
                    icon: const Icon(Icons.science_outlined, size: 16),
                    label: const Text('Đăng nhập tài khoản Test nội bộ (Admin)'),
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.grey,
                      textStyle: AppTheme.monoFont(fontSize: 11),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 14),
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Theme.of(context).colorScheme.error),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _continueAsGuest() {
    _openScanner(isGuest: true);
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
        _openScanner(isGuest: false);
      }
    } catch (error) {
      setState(() => _error = 'Xác thực thất bại: $error');
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
      _openScanner(isGuest: false);
    } catch (error) {
      setState(() => _error = 'Đăng nhập admin thất bại: $error');
    } finally {
      if (mounted) {
        setState(() => _isBusy = false);
      }
    }
  }

  void _openScanner({bool isGuest = false}) {
    if (!mounted) {
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => AppShell(
          themeMode: widget.themeMode,
          onThemeModeChanged: widget.onThemeModeChanged ?? (_) {},
          isGuest: isGuest,
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
