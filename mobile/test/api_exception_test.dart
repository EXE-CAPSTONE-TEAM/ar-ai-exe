import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:shoe_visual_customizer_mobile/services/api_exception.dart';

RequestOptions _options() => RequestOptions(path: '/api/v1/auth/login');

void main() {
  group('ApiException.from', () {
    test('prefers the backend message and code', () {
      final error = ApiException.from(
        DioException(
          requestOptions: _options(),
          response: Response(
            requestOptions: _options(),
            statusCode: 401,
            data: {
              'code': 'AUTH_INVALID_CREDENTIALS',
              'message': 'Email hoặc mật khẩu không đúng',
            },
          ),
        ),
      );

      expect(error.message, 'Email hoặc mật khẩu không đúng');
      expect(error.code, 'AUTH_INVALID_CREDENTIALS');
      expect(error.isAuthExpired, isTrue);
    });

    test('explains a connection failure instead of leaking a stack trace', () {
      final error = ApiException.from(
        DioException(
          requestOptions: _options(),
          type: DioExceptionType.connectionError,
          error: const SocketException('failed'),
        ),
      );

      expect(error.message, contains('Không kết nối được'));
      expect(error.message, isNot(contains('DioException')));
      expect(error.isAuthExpired, isFalse);
    });

    test('falls back on status when the body carries no message', () {
      final error = ApiException.from(
        DioException(
          requestOptions: _options(),
          response: Response(
            requestOptions: _options(),
            statusCode: 503,
            data: 'Service Unavailable',
          ),
        ),
      );

      expect(error.message, contains('Máy chủ đang gặp sự cố'));
      expect(error.statusCode, 503);
    });

    test('passes an ApiException through unchanged', () {
      const original = ApiException(message: 'Phiên quét đã hết hạn.');
      expect(ApiException.from(original), same(original));
    });
  });
}
