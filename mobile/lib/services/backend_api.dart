import 'dart:math';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

import '../config/app_config.dart';
import '../models/account.dart';
import '../models/reconstruction_readiness.dart';
import '../models/kiri_status.dart';
import '../models/scan_metadata.dart';
import '../models/scan_upload_result.dart';
import 'api_exception.dart';
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

/// `POST /auth/login` can answer with tokens or with a 2FA challenge
/// (mandatory for Admin under BR-12), so the caller must branch.
class LoginOutcome {
  const LoginOutcome({
    required this.signedIn,
    this.mfaRequired = false,
    this.challengeToken,
    this.method,
  });

  final bool signedIn;
  final bool mfaRequired;
  final String? challengeToken;
  final String? method;
}

class BackendApi {
  BackendApi({
    Dio? dio,
    FlutterSecureStorage? secureStorage,
    TokenStorage? tokenStorage,
    String? kusshoesBaseUrl,
    String? computeBaseUrl,
    CookieJar? cookieJar,
  })  : _kusshoesBaseUrl = kusshoesBaseUrl ?? AppConfig.kusshoesBaseUrl,
        _computeBaseUrl = computeBaseUrl ?? AppConfig.computeBaseUrl,
        _tokenStorage = tokenStorage ?? TokenStorage(secureStorage),
        _injectedCookieJar = cookieJar,
        _dio = dio ?? Dio() {
    _dio.options.connectTimeout ??= const Duration(seconds: 20);
    _dio.options.receiveTimeout ??= const Duration(seconds: 60);
    _dio.interceptors.add(InterceptorsWrapper(onError: _onError));
  }

  /// The app shares one client so the in-memory access token, the rotated
  /// refresh cookie and the scan token stay consistent across screens.
  static BackendApi? _shared;

  static BackendApi get shared => _shared ??= BackendApi();

  @visibleForTesting
  static set shared(BackendApi api) => _shared = api;

  static const _accessTokenKey = 'kusshoes_access_token';

  /// Written by an earlier build that expected a refresh token in the response
  /// body. The backend only ever sets it as an httpOnly cookie, so the stored
  /// value was always null - purged on sign-out so nothing stale lingers.
  static const _legacyRefreshTokenKey = 'kusshoes_refresh_token';

  final Dio _dio;
  final TokenStorage _tokenStorage;
  final String _kusshoesBaseUrl;
  final CookieJar? _injectedCookieJar;

  /// Origin for scan-session/kiri calls. Starts at the compile-time default
  /// and is replaced by the real compute service URL after [beginScan].
  String _computeBaseUrl;

  String? _accessToken;

  /// Short-lived, project-scoped token minted by the compute service via
  /// `/api/control-plane/scan/exchange`. Kept in memory only — a fresh scan
  /// always re-bootstraps.
  String? _scanAccessToken;

  bool _cookiesReady = false;
  Future<bool>? _pendingRefresh;

  /// Flips to true once the session cannot be recovered (refresh rejected or
  /// the account was suspended), so the shell can return to sign-in.
  final ValueNotifier<bool> sessionExpired = ValueNotifier(false);

  Future<bool> hasStoredToken() async {
    _accessToken ??= await _tokenStorage.read(_accessTokenKey);
    return _accessToken != null;
  }

  // --- Auth -----------------------------------------------------------------

  Future<PendingRegistration> register({
    required String name,
    required String username,
    required String email,
    required String password,
  }) async {
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/auth/register',
      body: {
        'email': email,
        'username': username,
        'password': password,
        'confirm_password': password,
        'full_name': name,
      },
    );
    return PendingRegistration(
      userId: data['user_id'] as String,
      email: data['email'] as String,
    );
  }

  Future<void> verifyOtp({
    required String userId,
    required String otpCode,
  }) async {
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/auth/verify-otp',
      body: {'user_id': userId, 'otp_code': otpCode},
    );
    await _storeAccessToken(data);
  }

  Future<void> resendOtp({required String userId}) async {
    await _post(
      '$_kusshoesBaseUrl/api/v1/auth/resend-otp',
      body: {'user_id': userId},
    );
  }

  Future<LoginOutcome> login({
    required String email,
    required String password,
  }) async {
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/auth/login',
      body: {'email': email, 'password': password},
    );
    if (data['mfa_required'] == true) {
      return LoginOutcome(
        signedIn: false,
        mfaRequired: true,
        challengeToken: data['challenge_token'] as String?,
        method: data['method'] as String?,
      );
    }
    await _storeAccessToken(data);
    return const LoginOutcome(signedIn: true);
  }

  /// Completes a 2FA challenge returned by [login].
  Future<void> verifyTwoFactor({
    required String challengeToken,
    required String code,
  }) async {
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/auth/2fa/verify',
      body: {'challenge_token': challengeToken, 'code': code},
    );
    await _storeAccessToken(data);
  }

  Future<void> logout() async {
    if (_accessToken != null) {
      try {
        // The refresh token lives in the httpOnly cookie the jar replays, so
        // no body is needed for the server-side revoke.
        await _post(
          '$_kusshoesBaseUrl/api/v1/auth/logout',
          body: const <String, dynamic>{},
          authenticated: true,
        );
      } catch (_) {
        // Best-effort revoke; local state is cleared below either way.
      }
    }
    await _clearSession();
  }

  // --- Account ---------------------------------------------------------------

  /// `GET /api/v1/users/me`
  Future<UserProfile> getProfile() async {
    await _ensureAccessToken();
    return UserProfile.fromJson(
      await _get('$_kusshoesBaseUrl/api/v1/users/me', authenticated: true),
    );
  }

  /// `GET /api/v1/users/me/usage` — plan tier and per-cycle quota counters.
  Future<AccountUsage> getUsage() async {
    await _ensureAccessToken();
    return AccountUsage.fromJson(
      await _get('$_kusshoesBaseUrl/api/v1/users/me/usage', authenticated: true),
    );
  }

  /// `GET /api/v1/subscription`
  Future<SubscriptionInfo> getSubscription() async {
    await _ensureAccessToken();
    return SubscriptionInfo.fromJson(
      await _get('$_kusshoesBaseUrl/api/v1/subscription', authenticated: true),
    );
  }

  /// `GET /api/v1/projects` — one cursor page of the signed-in user's designs.
  Future<ProjectPage> listProjects({String? cursor, int limit = 20}) async {
    await _ensureAccessToken();
    final query = <String, String>{
      'limit': '$limit',
      if (cursor != null) 'cursor': cursor,
    };
    final suffix = query.entries
        .map((e) => '${e.key}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    return ProjectPage.fromJson(
      await _get(
        '$_kusshoesBaseUrl/api/v1/projects?$suffix',
        authenticated: true,
      ),
    );
  }

  // --- Scan flow ------------------------------------------------------------

  /// Bootstraps a KusShoes project for a new scan, then exchanges the returned
  /// compute grant for a project-scoped scan token. Must run before
  /// [createScanSession] / upload / kiri calls.
  ///
  /// [clientRequestId] keys the server's idempotency record, so a retry of a
  /// failed scan attempt MUST reuse the same value — a fresh id creates a
  /// second empty project (see [newScanRequestId]).
  Future<ScanGrant> beginScan({
    required String projectName,
    required String clientRequestId,
  }) async {
    await _ensureAccessToken();
    final bootstrap = await _post(
      '$_kusshoesBaseUrl/api/v1/mobile/scans/bootstrap',
      body: {
        'client_request_id': clientRequestId,
        'project_name': projectName,
      },
      authenticated: true,
    );
    _computeBaseUrl = bootstrap['compute_api_url'] as String;
    final computeGrant = bootstrap['compute_grant'] as String;

    final exchange = await _post(
      '$_computeBaseUrl/api/control-plane/scan/exchange',
      body: {'computeGrant': computeGrant},
    );
    _scanAccessToken = exchange['accessToken'] as String;
    return ScanGrant(
      projectId: exchange['projectId'] as String,
      projectName: exchange['projectName'] as String,
      webProjectUrl: exchange['webProjectUrl'] as String,
    );
  }

  /// A stable id for one scan attempt, including all of its retries.
  static String newScanRequestId() => _uuidV4();

  Future<String> createScanSession({required ScanMetadata metadata}) async {
    _ensureScanToken();
    final data = await _post(
      '$_computeBaseUrl/api/scan-sessions',
      body: {'metadata': metadata.toJson()},
      scanScoped: true,
    );
    return data['id'] as String;
  }

  Future<ReconstructionReadiness> getReconstructionReadiness() async {
    return ReconstructionReadiness.fromJson(
      await _get('$_computeBaseUrl/api/system/reconstruction-readiness'),
    );
  }

  Future<ScanUploadResult> uploadScanPass({
    required String scanSessionId,
    required String passType,
    required XFile videoFile,
    required void Function(int sent, int total) onProgress,
  }) async {
    _ensureScanToken();
    await _ensureCookieJar();
    try {
      // Streamed from disk rather than read into memory: a 60s 1080p pass can
      // run to tens of MB and BR-34 allows up to 200MB per job.
      final formData = FormData.fromMap({
        'video': await MultipartFile.fromFile(
          videoFile.path,
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
    } catch (error) {
      throw ApiException.from(error);
    }
  }

  Future<String> startProcessing({required String scanSessionId}) async {
    _ensureScanToken();
    final data = await _post(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/process',
      body: const <String, dynamic>{},
      scanScoped: true,
    );
    return data['status'] as String? ?? 'uploaded';
  }

  Future<KiriStatus> startKiriProcessing({
    required String scanSessionId,
  }) async {
    _ensureScanToken();
    return _kiriStatus(
      await _post(
        '$_computeBaseUrl/api/scan-sessions/$scanSessionId/kiri/process',
        body: const <String, dynamic>{},
        scanScoped: true,
      ),
    );
  }

  Future<KiriStatus> getKiriStatus({required String scanSessionId}) async {
    _ensureScanToken();
    return _kiriStatus(
      await _get(
        '$_computeBaseUrl/api/scan-sessions/$scanSessionId/kiri/status',
        scanScoped: true,
      ),
    );
  }

  Future<KiriStatus> configureCrop({
    required String scanSessionId,
    required CropBox cropBox,
  }) async {
    _ensureScanToken();
    return _kiriStatus(
      await _post(
        '$_computeBaseUrl/api/scan-sessions/$scanSessionId/crop',
        body: cropBox.toJson(),
        scanScoped: true,
      ),
    );
  }

  Future<KiriStatus> saveKiriProject({
    required String scanSessionId,
    required String projectName,
    required CropBox cropBox,
  }) async {
    _ensureScanToken();
    return _kiriStatus(
      await _post(
        '$_computeBaseUrl/api/scan-sessions/$scanSessionId/save-project',
        body: {'projectName': projectName, 'cropBox': cropBox.toJson()},
        scanScoped: true,
      ),
    );
  }

  KiriStatus _kiriStatus(Map<String, dynamic> payload) {
    if (payload.isEmpty) {
      throw const ApiException(
        message: 'Máy chủ không trả về trạng thái dựng 3D. Vui lòng thử lại.',
      );
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

  // --- Transport ------------------------------------------------------------

  Future<Map<String, dynamic>> _post(
    String url, {
    required Object body,
    bool authenticated = false,
    bool scanScoped = false,
  }) async {
    await _ensureCookieJar();
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        url,
        data: body,
        options: _optionsFor(
          authenticated: authenticated,
          scanScoped: scanScoped,
        ),
      );
      return response.data ?? const <String, dynamic>{};
    } catch (error) {
      throw ApiException.from(error);
    }
  }

  Future<Map<String, dynamic>> _get(
    String url, {
    bool authenticated = false,
    bool scanScoped = false,
  }) async {
    await _ensureCookieJar();
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        url,
        options: _optionsFor(
          authenticated: authenticated,
          scanScoped: scanScoped,
        ),
      );
      return response.data ?? const <String, dynamic>{};
    } catch (error) {
      throw ApiException.from(error);
    }
  }

  Options? _optionsFor({
    required bool authenticated,
    required bool scanScoped,
  }) {
    if (scanScoped) {
      return _scanAuthOptions();
    }
    return authenticated ? _kusshoesAuthOptions() : null;
  }

  /// Attaches the cookie manager on first use. `PersistCookieJar` keeps the
  /// rotated `kusshoes_refresh_token` cookie across app restarts — the backend
  /// only ever returns the refresh token in that httpOnly cookie, never in a
  /// response body, and each one is single-use.
  Future<void> _ensureCookieJar() async {
    if (_cookiesReady) {
      return;
    }
    _cookiesReady = true;
    if (_injectedCookieJar != null) {
      _dio.interceptors.add(CookieManager(_injectedCookieJar));
      return;
    }
    if (kIsWeb) {
      // The browser manages cookies itself.
      return;
    }
    try {
      final dir = await getApplicationSupportDirectory();
      _dio.interceptors.add(
        CookieManager(
          PersistCookieJar(
            storage: FileStorage('${dir.path}/.kusshoes-cookies'),
          ),
        ),
      );
    } catch (_) {
      // Fall back to an in-memory jar: refresh still works for this run.
      _dio.interceptors.add(CookieManager(CookieJar()));
    }
  }

  Future<void> _onError(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final request = error.requestOptions;
    final isKusshoesCall = request.uri.toString().startsWith(_kusshoesBaseUrl);
    final isRefreshCall = request.path.endsWith('/auth/refresh');
    final alreadyRetried = request.extra['kusshoes_retried'] == true;

    if (error.response?.statusCode != 401 ||
        !isKusshoesCall ||
        isRefreshCall ||
        alreadyRetried ||
        _accessToken == null) {
      return handler.next(error);
    }

    final refreshed = await _refreshAccessToken();
    if (!refreshed) {
      await _clearSession();
      sessionExpired.value = true;
      return handler.next(error);
    }

    try {
      request
        ..headers['Authorization'] = 'Bearer $_accessToken'
        ..extra['kusshoes_retried'] = true;
      return handler.resolve(await _dio.fetch<dynamic>(request));
    } on DioException catch (retryError) {
      return handler.next(retryError);
    }
  }

  /// Single-flight: concurrent 401s share one refresh round-trip so the
  /// single-use refresh cookie is not spent twice.
  Future<bool> _refreshAccessToken() {
    return _pendingRefresh ??= _performRefresh().whenComplete(() {
      _pendingRefresh = null;
    });
  }

  Future<bool> _performRefresh() async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '$_kusshoesBaseUrl/api/v1/auth/refresh',
        data: const <String, dynamic>{},
      );
      final accessToken = response.data?['access_token'] as String?;
      if (accessToken == null) {
        return false;
      }
      _accessToken = accessToken;
      await _tokenStorage.write(_accessTokenKey, accessToken);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<void> _storeAccessToken(Map<String, dynamic>? payload) async {
    final accessToken = payload?['access_token'] as String?;
    if (accessToken == null) {
      throw const ApiException(
        message: 'Máy chủ không trả về token đăng nhập. Vui lòng thử lại.',
      );
    }
    _accessToken = accessToken;
    sessionExpired.value = false;
    await _tokenStorage.write(_accessTokenKey, accessToken);
  }

  Future<void> _clearSession() async {
    _accessToken = null;
    _scanAccessToken = null;
    await _tokenStorage.delete(_accessTokenKey);
    await _tokenStorage.delete(_legacyRefreshTokenKey);
  }

  Future<void> _ensureAccessToken() async {
    _accessToken ??= await _tokenStorage.read(_accessTokenKey);
    if (_accessToken == null) {
      throw const ApiException(
        message: 'Bạn cần đăng nhập trước khi quét giày.',
        isAuthExpired: true,
      );
    }
  }

  void _ensureScanToken() {
    if (_scanAccessToken == null) {
      throw const ApiException(
        message: 'Phiên quét đã hết hạn. Hãy bắt đầu một lượt quét mới.',
      );
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
