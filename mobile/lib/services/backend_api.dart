import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/reconstruction_readiness.dart';
import '../models/kiri_status.dart';
import '../models/scan_metadata.dart';
import '../models/scan_upload_result.dart';
import 'token_storage.dart';

class BackendApi {
  BackendApi({
    Dio? dio,
    FlutterSecureStorage? secureStorage,
    TokenStorage? tokenStorage,
    String? baseUrl,
  })  : _baseUrl = baseUrl ??
            const String.fromEnvironment(
              'BACKEND_BASE_URL',
              defaultValue: 'http://172.16.1.232:8000',
            ),
        _tokenStorage = tokenStorage ?? TokenStorage(secureStorage),
        _dio = dio ?? Dio();

  static const _tokenKey = 'shoe_customizer_access_token';

  final Dio _dio;
  final TokenStorage _tokenStorage;
  final String _baseUrl;
  String? _accessToken;

  Future<bool> hasStoredToken() async {
    _accessToken ??= await _tokenStorage.read(_tokenKey);
    return _accessToken != null;
  }

  Future<void> register({
    required String name,
    required String email,
    required String password,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/auth/register',
      data: {
        'name': name,
        'email': email,
        'password': password,
      },
    );
    await _storeToken(response.data?['accessToken'] as String?);
  }

  Future<void> login({required String email, required String password}) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/auth/login',
      data: {
        'email': email,
        'password': password,
      },
    );
    await _storeToken(response.data?['accessToken'] as String?);
  }

  Future<void> demoLogin() async {
    final response =
        await _dio.post<Map<String, dynamic>>('$_baseUrl/api/auth/demo-login');
    await _storeToken(response.data?['accessToken'] as String?);
  }

  Future<void> logout() async {
    _accessToken = null;
    await _tokenStorage.delete(_tokenKey);
  }

  Future<String> createScanSession({required ScanMetadata metadata}) async {
    await _ensureToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/scan-sessions',
      data: {'metadata': metadata.toJson()},
      options: _authOptions(),
    );
    return response.data?['id'] as String;
  }

  Future<ReconstructionReadiness> getReconstructionReadiness() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '$_baseUrl/api/system/reconstruction-readiness',
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
    await _ensureToken();

    final formData = FormData.fromMap({
      'video': MultipartFile.fromBytes(
        await videoFile.readAsBytes(),
        filename: '$passType.mp4',
      ),
    });

    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/scan-sessions/$scanSessionId/videos/$passType',
      data: formData,
      options: _authOptions(contentType: 'multipart/form-data'),
      onSendProgress: onProgress,
    );

    return ScanUploadResult.fromJson(response.data!);
  }

  Future<String> startProcessing({required String scanSessionId}) async {
    await _ensureToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/scan-sessions/$scanSessionId/process',
      data: <String, dynamic>{},
      options: _authOptions(),
    );
    return response.data?['status'] as String? ?? 'uploaded';
  }

  Future<KiriStatus> startKiriProcessing({required String scanSessionId}) async {
    await _ensureToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/scan-sessions/$scanSessionId/kiri/process',
      data: const <String, dynamic>{},
      options: _authOptions(),
    );
    return _kiriStatus(response.data);
  }

  Future<KiriStatus> getKiriStatus({required String scanSessionId}) async {
    await _ensureToken();
    final response = await _dio.get<Map<String, dynamic>>(
      '$_baseUrl/api/scan-sessions/$scanSessionId/kiri/status',
      options: _authOptions(),
    );
    return _kiriStatus(response.data);
  }

  Future<KiriStatus> configureCrop({
    required String scanSessionId,
    required CropBox cropBox,
  }) async {
    await _ensureToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/scan-sessions/$scanSessionId/crop',
      data: cropBox.toJson(),
      options: _authOptions(),
    );
    return _kiriStatus(response.data);
  }

  Future<KiriStatus> saveKiriProject({
    required String scanSessionId,
    required String projectName,
    required CropBox cropBox,
  }) async {
    await _ensureToken();
    final response = await _dio.post<Map<String, dynamic>>(
      '$_baseUrl/api/scan-sessions/$scanSessionId/save-project',
      data: {
        'projectName': projectName,
        'cropBox': cropBox.toJson(),
      },
      options: _authOptions(),
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
      previewUrl: '$_baseUrl$previewUrl',
      cropBox: status.cropBox,
      modelAssetId: status.modelAssetId,
      errorMessage: status.errorMessage,
    );
  }

  Future<void> _storeToken(String? token) async {
    if (token == null) {
      throw Exception('Backend did not return an access token.');
    }

    _accessToken = token;
    await _tokenStorage.write(_tokenKey, token);
  }

  Future<void> _ensureToken() async {
    _accessToken ??= await _tokenStorage.read(_tokenKey);

    if (_accessToken == null) {
      throw Exception('Sign in before uploading a scan.');
    }
  }

  Options _authOptions({String? contentType}) {
    return Options(
      contentType: contentType,
      headers: {
        'Authorization': 'Bearer $_accessToken',
      },
    );
  }
}
