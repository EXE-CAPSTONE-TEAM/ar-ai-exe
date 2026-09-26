import 'dart:convert';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/services/api_exception.dart';
import 'package:shoe_visual_customizer_mobile/services/backend_api.dart';
import 'package:shoe_visual_customizer_mobile/services/token_storage.dart';

import 'relay_contract_test.dart' show MockDioAdapter;

class _MemoryTokenStorage extends TokenStorage {
  final values = <String, String>{};

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;

  @override
  Future<void> delete(String key) async => values.remove(key);
}

const _base = 'https://api.example.com';

String _s256(String verifier) =>
    base64Url.encode(sha256.convert(ascii.encode(verifier)).bytes).replaceAll('=', '');

void main() {
  group('signInWithGoogle', () {
    test('opens KusShoes Google sign-in with a PKCE challenge and exchanges the code',
        () async {
      String? openedUrl;
      String? callbackScheme;
      RequestOptions? exchange;

      final dio = Dio()
        ..httpClientAdapter = MockDioAdapter((options, _) async {
          exchange = options;
          return ResponseBody.fromString(
            jsonEncode({'access_token': 'acc.google', 'token_type': 'bearer'}),
            200,
            headers: {
              Headers.contentTypeHeader: [Headers.jsonContentType],
            },
          );
        });
      final storage = _MemoryTokenStorage();
      final api = BackendApi(
        dio: dio,
        kusshoesBaseUrl: _base,
        tokenStorage: storage,
        cookieJar: CookieJar(),
        webAuthenticator: ({required url, required callbackUrlScheme}) async {
          openedUrl = url;
          callbackScheme = callbackUrlScheme;
          return 'vn.kusshoes.mobile://auth/google?code=one-time-code';
        },
      );

      await api.signInWithGoogle();

      final start = Uri.parse(openedUrl!);
      expect(start.toString().split('?').first, '$_base/api/v1/auth/google');
      expect(start.queryParameters['client'], 'mobile');
      expect(callbackScheme, 'vn.kusshoes.mobile');

      expect(exchange!.method, 'POST');
      expect(exchange!.path, '$_base/api/v1/auth/google/mobile/exchange');
      final body = exchange!.data as Map<String, dynamic>;
      expect(body['code'], 'one-time-code');
      final verifier = body['code_verifier'] as String;
      expect(RegExp(r'^[A-Za-z0-9_-]{43,128}$').hasMatch(verifier), isTrue);
      // The server can only redeem the code with the verifier behind this challenge.
      expect(start.queryParameters['code_challenge'], _s256(verifier));

      expect(storage.values['kusshoes_access_token'], 'acc.google');
      expect(await api.hasStoredToken(), isTrue);
    });

    test('surfaces a server-side sign-in error without calling the exchange', () async {
      var exchangeCalls = 0;
      final dio = Dio()
        ..httpClientAdapter = MockDioAdapter((options, _) async {
          exchangeCalls++;
          return ResponseBody.fromString('{}', 200);
        });
      final api = BackendApi(
        dio: dio,
        kusshoesBaseUrl: _base,
        tokenStorage: _MemoryTokenStorage(),
        cookieJar: CookieJar(),
        webAuthenticator: ({required url, required callbackUrlScheme}) async =>
            'vn.kusshoes.mobile://auth/google?error=AUTH_ACCOUNT_BANNED',
      );

      await expectLater(
        api.signInWithGoogle(),
        throwsA(isA<ApiException>()
            .having((e) => e.code, 'code', 'AUTH_ACCOUNT_BANNED')),
      );
      expect(exchangeCalls, 0);
    });

    test('a closed browser tab reports a cancellation', () async {
      final api = BackendApi(
        dio: Dio(),
        kusshoesBaseUrl: _base,
        tokenStorage: _MemoryTokenStorage(),
        cookieJar: CookieJar(),
        webAuthenticator: ({required url, required callbackUrlScheme}) async =>
            throw PlatformException(code: 'CANCELED'),
      );

      await expectLater(
        api.signInWithGoogle(),
        throwsA(isA<ApiException>()
            .having((e) => e.code, 'code', 'GOOGLE_SIGN_IN_CANCELED')),
      );
    });
  });
}
