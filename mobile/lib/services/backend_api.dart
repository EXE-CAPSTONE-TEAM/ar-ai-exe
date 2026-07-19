import 'dart:math';

import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/reconstruction_readiness.dart';
import '../models/kiri_status.dart';
import '../models/scan_metadata.dart';
import '../models/scan_upload_result.dart';
import 'token_storage.dart';

/// Result of a claimed compute grant: a project-scoped scan token is now
/// active on this [BackendApi] instance and scan-session calls will work.
class ScanGrant {
  const ScanGrant({
    required this.projectId,
    required this.projectName,
    required this.webProjectUrl,
  });

  final String projectId;
  final String projectName;
  final String webProjectUrl;
}

/// A KusShoes account created but not yet OTP-verified.
class PendingRegistration {
  const PendingRegistration({required this.userId, required this.email});

  final String userId;
  final String email;
}

class BackendApi {
  BackendApi({
    Dio? dio,
    FlutterSecureStorage? secureStorage,
    TokenStorage? tokenStorage,
    String? kusshoesBaseUrl,
    String? computeBaseUrl,
  })  : _kusshoesBaseUrl = kusshoesBaseUrl ??
            const String.fromEnvironment(
              'KUSSHOES_BASE_URL',
              defaultValue: 'http://172.16.1.232:8000',
            ),
        _computeBaseUrl = computeBaseUrl ??
            const String.fromEnvironment(
              'COMPUTE_BASE_URL',
              defaultValue: 'http://172.16.1.232:8010',
            ),
        _tokenStorage = tokenStorage ?? TokenStorage(secureStorage),
        _dio = dio ?? Dio();

  static const _accessTokenKey = 'kusshoes_access_token';
  static const _refreshTokenKey = 'kusshoes_refresh_token';

  final Dio _dio;
  final TokenStorage _tokenStorage;
  final String _kusshoesBaseUrl;

  /// Origin for scan-session/kiri calls. Starts at the compile-time default
  /// and is replaced by the real compute service URL after [beginScan].
  String _computeBaseUrl;

  String? _accessToken;
  String? _refreshToken;

  /// Short-lived, project-scoped token minted by the compute service via
  /// `/api/control-plane/scan/exchange`. Kept in memory only — a fresh scan
  /// always re-bootstraps.
  String? _scanAccessToken;

  Future<bool> hasStoredToken() async {
    _accessToken ??= await _tokenStorage.read(_accessTokenKey);
    return _accessToken != null;
  }

  Future<PendingRegistration> register({
    required String name,
    required String username,
    required String email,
    required String password,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_kusshoesBaseUrl/api/v1/auth/register',
      data: {
        'email': email,
        'username': username,
        'password': password,
        'confirm_password': password,
        'full_name': name,
      },
    );
    final data = response.data!;
    return PendingRegistration(
      userId: data['user_id'] as String,
      email: data['email'] as String,
    );
  }

  Future<void> verifyOtp({
    required String userId,
    required String otpCode,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_kusshoesBaseUrl/api/v1/auth/verify-otp',
      data: {'user_id': userId, 'otp_code': otpCode},
    );
    await _storeKusshoesTokens(response.data);
  }

  Future<void> resendOtp({required String userId}) async {
    await _dio.post<void>(
      '$_kusshoesBaseUrl/api/v1/auth/resend-otp',
      data: {'user_id': userId},
    );
  }

  Future<void> login({required String email, required String password}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_kusshoesBaseUrl/api/v1/auth/login',
      data: {'email': email, 'password': password},
    );
    await _storeKusshoesTokens(response.data);
  }

  Future<void> logout() async {
    final refreshToken = _refreshToken;
    if (_accessToken != null && refreshToken != null) {
      try {
        await _dio.post<void>(
          '$_kusshoesBaseUrl/api/v1/auth/logout',
          data: {'refresh_token': refreshToken},
          options: _kusshoesAuthOptions(),
        );
      } catch (_) {
        // Best-effort server-side revoke; local state is cleared below either way.
      }
    }
    _accessToken = null;
    _refreshToken = null;
    _scanAccessToken = null;
    await _tokenStorage.delete(_accessTokenKey);
    await _tokenStorage.delete(_refreshTokenKey);
  }

  /// Bootstraps a KusShoes project for a new scan, then exchanges the
  /// returned compute grant for a project-scoped scan token. Must run
  /// before [createScanSession] / upload / kiri calls.
  Future<ScanGrant> beginScan({required String projectName}) async {
    await _ensureKusshoesToken();
    final bootstrap = await _dio.post<Map<String, dynamic>>(
      '$_kusshoesBaseUrl/api/v1/mobile/scans/bootstrap',
      data: {
        'client_request_id': _uuidV4(),
        'project_name': projectName,
      },
      options: _kusshoesAuthOptions(),
    );
    final bootstrapData = bootstrap.data!;
    _computeBaseUrl = bootstrapData['compute_api_url'] as String;
    final computeGrant = bootstrapData['compute_grant'] as String;

    final exchange = await _dio.post<Map<String, dynamic>>(
      '$_computeBaseUrl/api/control-plane/scan/exchange',
      data: {'computeGrant': computeGrant},
    );
    final exchangeData = exchange.data!;
    _scanAccessToken = exchangeData['accessToken'] as String;
    return ScanGrant(
      projectId: exchangeData['projectId'] as String,
      projectName: exchangeData['projectName'] as String,
      webProjectUrl: exchangeData['webProjectUrl'] as String,
    );
  }

  Future<String> createScanSession({required ScanMetadata metadata}) async {
    _ensureScanToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_computeBaseUrl/api/scan-sessions',
      data: {'metadata': metadata.toJson()},
      options: _scanAuthOptions(),
    );
    return response.data?['id'] as String;
  }

  Future<ReconstructionReadiness> getReconstructionReadiness() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_computeBaseUrl/api/system/reconstruction-readiness',
    );
    return ReconstructionReadiness.fromJson(
      response.data ?? const <String, dynamic>{},
    );
  }

  Future<ScanUploadResult> uploadScanPass({
    required String scanSessionId,
    required String passType,
    required XFile videoFile,
    required void Function(int sent, int total) onProgress,
  }) async {
    _ensureScanToken();

    final formData = FormData.fromMap({
      'video': MultipartFile.fromBytes(
        await videoFile.readAsBytes(),
        filename: '$passType.mp4',
      ),
    });

    final response = await _dio.post<Map<String, dynamic>>(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/videos/$passType',
      data: formData,
      options: _scanAuthOptions(contentType: 'multipart/form-data'),
      onSendProgress: onProgress,
    );

    return ScanUploadResult.fromJson(response.data!);
  }

  Future<String> startProcessing({required String scanSessionId}) async {
    _ensureScanToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/process',
      data: <String, dynamic>{},
      options: _scanAuthOptions(),
    );
    return response.data?['status'] as String? ?? 'uploaded';
  }

  Future<KiriStatus> startKiriProcessing({required String scanSessionId}) async {
    _ensureScanToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/kiri/process',
      data: const <String, dynamic>{},
      options: _scanAuthOptions(),
    );
    return _kiriStatus(response.data);
  }

  Future<KiriStatus> getKiriStatus({required String scanSessionId}) async {
    _ensureScanToken();
    final response = await _dio.get<Map<String, dynamic>>(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/kiri/status',
      options: _scanAuthOptions(),
    );
    return _kiriStatus(response.data);
  }

  Future<KiriStatus> configureCrop({
    required String scanSessionId,
    required CropBox cropBox,
  }) async {
    _ensureScanToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/crop',
      data: cropBox.toJson(),
      options: _scanAuthOptions(),
    );
    return _kiriStatus(response.data);
  }

  Future<KiriStatus> saveKiriProject({
    required String scanSessionId,
    required String projectName,
    required CropBox cropBox,
  }) async {
    _ensureScanToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/save-project',
      data: {
        'projectName': projectName,
        'cropBox': cropBox.toJson(),
      },
      options: _scanAuthOptions(),
    );
    return _kiriStatus(response.data);
  }

  KiriStatus _kiriStatus(Map<String, dynamic>? payload) {
    if (payload == null) {
      throw Exception('Backend did not return Kiri status.');
    }
    final status = KiriStatus.fromJson(payload);
    final previewUrl = status.previewUrl;
    if (previewUrl == null || Uri.parse(previewUrl).hasScheme) {
      return status;
    }
    return KiriStatus(
      scanSessionId: status.scanSessionId,
      projectId: status.projectId,
      status: status.status,
      providerStatus: status.providerStatus,
      progress: status.progress,
      previewUrl: '$_computeBaseUrl$previewUrl',
      cropBox: status.cropBox,
      modelAssetId: status.modelAssetId,
      errorMessage: status.errorMessage,
    );
  }

  Future<void> _storeKusshoesTokens(Map<String, dynamic>? payload) async {
    final accessToken = payload?['access_token'] as String?;
    final refreshToken = payload?['refresh_token'] as String?;
    if (accessToken == null) {
      throw Exception('Backend did not return an access token.');
    }
    _accessToken = accessToken;
    _refreshToken = refreshToken;
    await _tokenStorage.write(_accessTokenKey, accessToken);
    if (refreshToken != null) {
      await _tokenStorage.write(_refreshTokenKey, refreshToken);
    }
  }

  Future<void> _ensureKusshoesToken() async {
    _accessToken ??= await _tokenStorage.read(_accessTokenKey);
    if (_accessToken == null) {
      throw Exception('Sign in before starting a scan.');
    }
  }

  void _ensureScanToken() {
    if (_scanAccessToken == null) {
      throw Exception('Scan session expired. Start a new scan.');
    }
  }

  Options _kusshoesAuthOptions({String? contentType}) {
    return Options(
      contentType: contentType,
      headers: {'Authorization': 'Bearer $_accessToken'},
    );
  }

  Options _scanAuthOptions({String? contentType}) {
    return Options(
      contentType: contentType,
      headers: {'Authorization': 'Bearer $_scanAccessToken'},
    );
  }

  static String _uuidV4() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    String hex(int start, int end) => bytes
        .sublist(start, end)
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join();
    return '${hex(0, 4)}-${hex(4, 6)}-${hex(6, 8)}-${hex(8, 10)}-${hex(10, 16)}';
  }
}
