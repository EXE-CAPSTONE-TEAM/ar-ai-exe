// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  const TokenStorage([FlutterSecureStorage? _]);

  Future<String?> read(String key) async => html.window.localStorage[key];

  Future<void> write(String key, String value) async {
    html.window.localStorage[key] = value;
  }

  Future<void> delete(String key) async {
    html.window.localStorage.remove(key);
  }
}
