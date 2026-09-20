import 'dart:io';

import 'package:dio/dio.dart';

/// A failure the UI can show directly.
///
/// The KusShoes backend already answers with `{"code", "message"}` in
/// Vietnamese, so [message] prefers the server's own wording and only falls
/// back to a local string for transport-level problems the server never saw
/// (NFR-USA-05: every error names a cause and a next step).
class ApiException implements Exception {
  const ApiException({
    required this.message,
    this.code,
    this.statusCode,
    this.isAuthExpired = false,
  });

  final String message;
  final String? code;
  final int? statusCode;

  /// The session is gone for good — refresh already failed. Callers should
  /// send the user back to sign-in rather than offering a retry.
  final bool isAuthExpired;

  factory ApiException.from(Object error) {
    if (error is ApiException) {
      return error;
    }
    if (error is! DioException) {
      return ApiException(message: 'Đã xảy ra lỗi không mong muốn. $error');
    }

    final response = error.response;
    final body = response?.data;
    final status = response?.statusCode;

    if (body is Map) {
      final message = body['message'];
      final code = body['code'];
      if (message is String && message.isNotEmpty) {
        return ApiException(
          message: message,
          code: code is String ? code : null,
          statusCode: status,
          isAuthExpired: status == 401,
        );
      }
    }

    return ApiException(
      message: _transportMessage(error, status),
      statusCode: status,
      isAuthExpired: status == 401,
    );
  }

  static String _transportMessage(DioException error, int? status) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'Kết nối quá chậm hoặc bị ngắt. Kiểm tra mạng rồi thử lại.';
      case DioExceptionType.connectionError:
        return 'Không kết nối được tới máy chủ KusShoes. Kiểm tra mạng rồi thử lại.';
      case DioExceptionType.cancel:
        return 'Yêu cầu đã bị hủy.';
      case DioExceptionType.badCertificate:
        return 'Chứng chỉ bảo mật của máy chủ không hợp lệ. Không thể tiếp tục.';
      case DioExceptionType.badResponse:
      case DioExceptionType.unknown:
        break;
    }
    if (error.error is SocketException) {
      return 'Không có kết nối mạng. Bật Wi-Fi hoặc dữ liệu di động rồi thử lại.';
    }
    return switch (status ?? 0) {
      401 => 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
      403 => 'Tài khoản của bạn không có quyền thực hiện việc này.',
      404 => 'Không tìm thấy dữ liệu yêu cầu.',
      409 => 'Dữ liệu đang được xử lý ở nơi khác. Thử lại sau vài giây.',
      413 => 'Tệp quá lớn. Quay video ngắn hơn rồi thử lại.',
      429 => 'Bạn thao tác quá nhanh. Đợi một chút rồi thử lại.',
      >= 500 => 'Máy chủ đang gặp sự cố. Vui lòng thử lại sau ít phút.',
      _ => 'Yêu cầu không thành công. Vui lòng thử lại.',
    };
  }

  @override
  String toString() => message;
}
