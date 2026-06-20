import 'package:flutter/material.dart';

import 'app/app_shell.dart';
import 'app/app_theme.dart';
import 'screens/auth_screen.dart';
import 'services/backend_api.dart';

void main() {
  runApp(const ShoeScannerApp());
}

class ShoeScannerApp extends StatefulWidget {
  const ShoeScannerApp({super.key});

  @override
  State<ShoeScannerApp> createState() => _ShoeScannerAppState();
}

class _ShoeScannerAppState extends State<ShoeScannerApp> {
  ThemeMode _themeMode = ThemeMode.dark;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Shoe Scanner',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: _themeMode,
      home: AuthGate(
        themeMode: _themeMode,
        onThemeModeChanged: (mode) => setState(() => _themeMode = mode),
      ),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({
    required this.themeMode,
    required this.onThemeModeChanged,
    super.key,
  });

  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  static const _previewMobileUi = bool.fromEnvironment('PREVIEW_MOBILE_UI');

  final _api = BackendApi();
  late final Future<bool> _hasToken = _api.hasStoredToken();

  @override
  Widget build(BuildContext context) {
    if (_previewMobileUi) {
      return AppShell(
        themeMode: widget.themeMode,
        onThemeModeChanged: widget.onThemeModeChanged,
      );
    }

    return FutureBuilder<bool>(
      future: _hasToken,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Scaffold(
              body: Center(child: CircularProgressIndicator()));
        }
        return snapshot.data!
            ? AppShell(
                themeMode: widget.themeMode,
                onThemeModeChanged: widget.onThemeModeChanged,
              )
            : AuthScreen(
                themeMode: widget.themeMode,
                onThemeModeChanged: widget.onThemeModeChanged,
              );
      },
    );
  }
}
