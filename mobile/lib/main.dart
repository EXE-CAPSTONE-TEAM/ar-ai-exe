import 'package:flutter/material.dart';

import 'screens/auth_screen.dart';
import 'screens/scan_setup_screen.dart';
import 'services/backend_api.dart';

void main() {
  runApp(const ShoeScannerApp());
}

class ShoeScannerApp extends StatelessWidget {
  const ShoeScannerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Shoe Scanner',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1F6F8B)),
        useMaterial3: true,
      ),
      home: const AuthGate(),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final _api = BackendApi();
  late final Future<bool> _hasToken = _api.hasStoredToken();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _hasToken,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        return snapshot.data! ? const ScanSetupScreen() : const AuthScreen();
      },
    );
  }
}