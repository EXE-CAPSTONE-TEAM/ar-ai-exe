import 'dart:convert';
import 'dart:math';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:crypto/crypto.dart';
import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';
import 'package:path_provider/path_provider.dart';

import '../config/app_config.dart';
import '../models/account.dart';
import '../models/project_models.dart';
import '../models/template_models.dart';
import '../models/reconstruction_readiness.dart';
import '../models/kiri_status.dart';
import '../models/scan_metadata.dart';
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

/// Opens [url] in a browser tab and resolves with the URL it finally redirects
/// to on [callbackUrlScheme]. Injected in tests.
typedef WebAuthenticator = Future<String> Function({
  required String url,
  required String callbackUrlScheme,
});

Future<String> _browserTabAuthenticator({
  required String url,
  required String callbackUrlScheme,
}) =>
    FlutterWebAuth2.authenticate(url: url, callbackUrlScheme: callbackUrlScheme);

class BackendApi {
  BackendApi({
    Dio? dio,
    Dio? storageDio,
    FlutterSecureStorage? secureStorage,
    TokenStorage? tokenStorage,
    String? kusshoesBaseUrl,
    String? computeBaseUrl,
    CookieJar? cookieJar,
    WebAuthenticator? webAuthenticator,
  })  : _webAuthenticator = webAuthenticator ?? _browserTabAuthenticator,
        _kusshoesBaseUrl = kusshoesBaseUrl ?? AppConfig.kusshoesBaseUrl,
        _computeBaseUrl = computeBaseUrl ?? AppConfig.computeBaseUrl,
        _tokenStorage = tokenStorage ?? TokenStorage(secureStorage),
        _injectedCookieJar = cookieJar,
        _dio = dio ?? Dio(),
        // Presigned storage URLs carry their own signature: requests to them go through a
        // client with no auth/cookie interceptors, so no bearer token or cookie can leak.
        _storageDio = storageDio ?? Dio() {
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

  @visibleForTesting
  void setScanTokenForTesting(String token) {
    _scanAccessToken = token;
  }

  static const _accessTokenKey = 'kusshoes_access_token';

  /// Written by an earlier build that expected a refresh token in the response
  /// body. The backend only ever sets it as an httpOnly cookie, so the stored
  /// value was always null - purged on sign-out so nothing stale lingers.
  static const _legacyRefreshTokenKey = 'kusshoes_refresh_token';

  final Dio _dio;
  final Dio _storageDio;
  final WebAuthenticator _webAuthenticator;
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

  /// Scheme of `MOBILE_GOOGLE_REDIRECT_URI` on KusShoes; the manifest's
  /// flutter_web_auth_2 CallbackActivity listens on it.
  static const googleCallbackScheme = 'vn.kusshoes.mobile';

  /// Same Google sign-in as the KusShoes web app, run in a browser tab (Google
  /// blocks embedded WebViews). The callback hands back a one-time code instead
  /// of tokens; only this instance holds the PKCE verifier that redeems it, and
  /// the exchange sets the refresh cookie on this client like `/auth/login`.
  Future<void> signInWithGoogle() async {
    final verifier = _newPkceVerifier();
    final startUrl = Uri.parse('$_kusshoesBaseUrl/api/v1/auth/google').replace(
      queryParameters: {
        'client': 'mobile',
        'code_challenge': _pkceS256(verifier),
      },
    );

    final String callback;
    try {
      callback = await _webAuthenticator(
        url: startUrl.toString(),
        callbackUrlScheme: googleCallbackScheme,
      );
    } on PlatformException catch (error) {
      if (error.code == 'CANCELED') {
        throw const ApiException(
          message: 'Bạn đã đóng trang đăng nhập Google.',
          code: 'GOOGLE_SIGN_IN_CANCELED',
        );
      }
      throw ApiException(
        message: 'Không mở được trang đăng nhập Google: ${error.message ?? error.code}',
        code: 'GOOGLE_SIGN_IN_UNAVAILABLE',
      );
    }

    final params = Uri.parse(callback).queryParameters;
    final errorCode = params['error'];
    if (errorCode != null) {
      throw ApiException(message: _googleSignInErrorMessage(errorCode), code: errorCode);
    }
    final code = params['code'];
    if (code == null || code.isEmpty) {
      throw const ApiException(
        message: 'Đăng nhập Google không hoàn tất. Vui lòng thử lại.',
        code: 'AUTH_OAUTH_FAILED',
      );
    }

    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/auth/google/mobile/exchange',
      body: {'code': code, 'code_verifier': verifier},
    );
    await _storeAccessToken(data);
  }

  static String _googleSignInErrorMessage(String code) {
    switch (code) {
      case 'AUTH_ACCOUNT_BANNED':
        return 'Tài khoản bị vô hiệu hóa. Vui lòng liên hệ quản trị viên.';
      case 'AUTH_GOOGLE_NO_EMAIL':
        return 'Không lấy được email từ tài khoản Google này.';
      case 'AUTH_OAUTH_STATE_INVALID':
        return 'Phiên đăng nhập Google đã hết hạn. Vui lòng thử lại.';
      default:
        return 'Đăng nhập Google thất bại. Vui lòng thử lại.';
    }
  }

  /// RFC 7636 verifier: 32 random bytes as unpadded base64url (43 chars).
  static String _newPkceVerifier() {
    final random = Random.secure();
    final bytes = List<int>.generate(32, (_) => random.nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }

  static String _pkceS256(String verifier) =>
      base64Url.encode(sha256.convert(ascii.encode(verifier)).bytes).replaceAll('=', '');

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

  Future<void> forgotPassword({required String email}) async {
    await _post(
      '$_kusshoesBaseUrl/api/v1/auth/forgot-password',
      body: {'email': email},
    );
  }

  Future<void> resetPassword({
    required String email,
    required String otpCode,
    required String newPassword,
  }) async {
    await _post(
      '$_kusshoesBaseUrl/api/v1/auth/reset-password',
      body: {
        'email': email,
        'otp_code': otpCode,
        'new_password': newPassword,
        'confirm_password': newPassword,
      },
    );
  }

  // --- Account & User Management ---------------------------------------------

  /// `GET /api/v1/users/me`
  Future<UserProfile> getProfile() async {
    await _ensureAccessToken();
    return UserProfile.fromJson(
      await _get('$_kusshoesBaseUrl/api/v1/users/me', authenticated: true),
    );
  }

  /// `PATCH /api/v1/users/me` — updates name and phone number.
  Future<UserProfile> updateProfile({
    String? firstName,
    String? lastName,
    String? phoneNumber,
  }) async {
    await _ensureAccessToken();
    final body = <String, dynamic>{
      if (firstName != null) 'first_name': firstName,
      if (lastName != null) 'last_name': lastName,
      if (phoneNumber != null) 'phone_number': phoneNumber,
    };
    final data = await _patch(
      '$_kusshoesBaseUrl/api/v1/users/me',
      body: body,
      authenticated: true,
    );
    return UserProfile.fromJson(data);
  }

  /// `PUT /api/v1/users/me/password` — changes current login password.
  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await _ensureAccessToken();
    await _put(
      '$_kusshoesBaseUrl/api/v1/users/me/password',
      body: {
        'current_password': currentPassword,
        'new_password': newPassword,
        'confirm_password': newPassword,
      },
      authenticated: true,
    );
  }

  /// `DELETE /api/v1/users/me` — permanent account deletion (App Store Guideline 5.1.1(v)).
  Future<void> deleteAccount({required String password}) async {
    await _ensureAccessToken();
    await _delete(
      '$_kusshoesBaseUrl/api/v1/users/me',
      body: {'password': password},
      authenticated: true,
    );
    await _clearSession();
  }

  /// `POST /api/v1/users/me/avatar` — requests presigned S3 PUT URL.
  Future<Map<String, String>> requestAvatarUpload({
    required String contentType,
    required int fileSize,
  }) async {
    await _ensureAccessToken();
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/users/me/avatar',
      body: {'content_type': contentType, 'file_size': fileSize},
      authenticated: true,
    );
    return {
      'upload_url': data['upload_url'] as String? ?? '',
      'avatar_path': data['avatar_path'] as String? ?? '',
    };
  }

  /// Uploads raw avatar bytes directly to MinIO/S3 presigned URL.
  Future<void> uploadAvatarBytes({
    required String uploadUrl,
    required List<int> bytes,
    required String contentType,
  }) async {
    try {
      await _dio.put<dynamic>(
        uploadUrl,
        data: Stream.fromIterable([bytes]),
        options: Options(
          headers: {
            'Content-Type': contentType,
            'Content-Length': bytes.length.toString(),
          },
        ),
      );
    } catch (error) {
      throw ApiException.from(error);
    }
  }

  /// `DELETE /api/v1/users/me/avatar` — removes custom avatar.
  Future<void> deleteAvatar() async {
    await _ensureAccessToken();
    await _delete('$_kusshoesBaseUrl/api/v1/users/me/avatar', authenticated: true);
  }

  /// `GET /api/v1/users/me/usage` — plan tier and per-cycle quota counters.
  Future<AccountUsage> getUsage() async {
    await _ensureAccessToken();
    return AccountUsage.fromJson(
      await _get('$_kusshoesBaseUrl/api/v1/users/me/usage', authenticated: true),
    );
  }

  // --- Billing & Subscriptions ----------------------------------------------

  /// `GET /api/v1/subscription`
  Future<SubscriptionInfo> getSubscription() async {
    await _ensureAccessToken();
    return SubscriptionInfo.fromJson(
      await _get('$_kusshoesBaseUrl/api/v1/subscription', authenticated: true),
    );
  }

  /// `GET /api/v1/plans` — dynamic plans and limits.
  Future<List<BillingPlan>> listPlans() async {
    final list = await _getList('$_kusshoesBaseUrl/api/v1/plans');
    return list
        .whereType<Map<String, dynamic>>()
        .map(BillingPlan.fromJson)
        .toList(growable: false);
  }

  /// `POST /api/v1/subscription/checkout` — creates gateway checkout link.
  Future<String> createCheckoutSession({
    required String tier,
    required String billingCycle,
    required String gateway,
    String? couponCode,
  }) async {
    await _ensureAccessToken();
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/subscription/checkout',
      body: {
        'tier': tier.toLowerCase(),
        'billing_cycle': billingCycle.toLowerCase(),
        'gateway': gateway.toLowerCase(),
        if (couponCode != null && couponCode.isNotEmpty)
          'coupon_code': couponCode,
      },
      authenticated: true,
    );
    return data['checkout_url'] as String? ?? '';
  }

  /// `GET /api/v1/subscription/invoices` — billing history.
  Future<List<InvoiceItem>> listInvoices({int limit = 20}) async {
    await _ensureAccessToken();
    final list = await _getList(
      '$_kusshoesBaseUrl/api/v1/subscription/invoices?limit=$limit',
      authenticated: true,
    );
    return list
        .whereType<Map<String, dynamic>>()
        .map(InvoiceItem.fromJson)
        .toList(growable: false);
  }

  /// `POST /api/v1/subscription/cancel`
  Future<void> cancelSubscription({bool immediate = false}) async {
    await _ensureAccessToken();
    await _post(
      '$_kusshoesBaseUrl/api/v1/subscription/cancel',
      body: {'immediate': immediate},
      authenticated: true,
    );
  }

  // --- Project Lifecycle & Full Trash ---------------------------------------

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

  /// `GET /api/v1/projects/{project_id}`
  Future<ProjectDetail> getProject(String projectId) async {
    await _ensureAccessToken();
    final data = await _get(
      '$_kusshoesBaseUrl/api/v1/projects/$projectId',
      authenticated: true,
    );
    return ProjectDetail.fromJson(data);
  }

  /// `POST /api/v1/projects` — creates a new standalone project.
  Future<ProjectSummary> createProject({
    required String name,
    String? description,
  }) async {
    await _ensureAccessToken();
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/projects',
      body: {
        'name': name,
        if (description != null) 'description': description,
      },
      authenticated: true,
    );
    return ProjectSummary.fromJson(data);
  }

  /// `PATCH /api/v1/projects/{project_id}` — renames project.
  Future<ProjectSummary> updateProject(
    String projectId, {
    String? name,
    String? description,
  }) async {
    await _ensureAccessToken();
    final data = await _patch(
      '$_kusshoesBaseUrl/api/v1/projects/$projectId',
      body: {
        if (name != null) 'name': name,
        if (description != null) 'description': description,
      },
      authenticated: true,
    );
    return ProjectSummary.fromJson(data);
  }

  /// `DELETE /api/v1/projects/{project_id}` — soft delete into trash.
  Future<void> deleteProject(String projectId) async {
    await _ensureAccessToken();
    await _delete(
      '$_kusshoesBaseUrl/api/v1/projects/$projectId',
      authenticated: true,
    );
  }

  /// `GET /api/v1/projects/trash` — lists soft-deleted projects.
  Future<ProjectTrashPage> listTrashProjects({
    String? cursor,
    int limit = 20,
  }) async {
    await _ensureAccessToken();
    final query = <String, String>{
      'limit': '$limit',
      if (cursor != null) 'cursor': cursor,
    };
    final suffix = query.entries
        .map((e) => '${e.key}=${Uri.encodeQueryComponent(e.value)}')
        .join('&');
    final data = await _get(
      '$_kusshoesBaseUrl/api/v1/projects/trash?$suffix',
      authenticated: true,
    );
    return ProjectTrashPage.fromJson(data);
  }

  /// `POST /api/v1/projects/{project_id}/restore` — restores from trash.
  Future<void> restoreProject(String projectId) async {
    await _ensureAccessToken();
    await _post(
      '$_kusshoesBaseUrl/api/v1/projects/$projectId/restore',
      body: const <String, dynamic>{},
      authenticated: true,
    );
  }

  /// `DELETE /api/v1/projects/{project_id}/permanent` — purges permanently.
  Future<void> permanentlyDeleteProject(String projectId) async {
    await _ensureAccessToken();
    await _delete(
      '$_kusshoesBaseUrl/api/v1/projects/$projectId/permanent',
      authenticated: true,
    );
  }

  // --- Templates ------------------------------------------------------------

  /// `GET /api/v1/templates` — public templates catalog.
  Future<List<ShoeTemplate>> listTemplates({String? category}) async {
    final query = category != null && category.isNotEmpty
        ? '?category=${Uri.encodeQueryComponent(category)}'
        : '';
    final list = await _getList('$_kusshoesBaseUrl/api/v1/templates$query');
    return list
        .whereType<Map<String, dynamic>>()
        .map(ShoeTemplate.fromJson)
        .toList(growable: false);
  }

  /// `POST /api/v1/projects/{project_id}/apply-template/{template_id}`
  Future<void> applyTemplate({
    required String projectId,
    required String templateId,
  }) async {
    await _ensureAccessToken();
    await _post(
      '$_kusshoesBaseUrl/api/v1/projects/$projectId/apply-template/$templateId',
      body: const <String, dynamic>{},
      authenticated: true,
    );
  }

  // --- Feedback & Exports ---------------------------------------------------

  /// `POST /api/v1/feedback` (SF-12)
  Future<void> submitFeedback({
    required int rating,
    String? comment,
    String? scanSessionId,
  }) async {
    await _ensureAccessToken();
    await _post(
      '$_kusshoesBaseUrl/api/v1/feedback',
      body: {
        'rating': rating,
        if (comment != null && comment.isNotEmpty) 'comment': comment,
        if (scanSessionId != null) 'scan_session_id': scanSessionId,
      },
      authenticated: true,
    );
  }

  /// `GET /api/v1/exports`
  Future<List<ExportItem>> listExports() async {
    await _ensureAccessToken();
    final list = await _getList(
      '$_kusshoesBaseUrl/api/v1/exports',
      authenticated: true,
    );
    return list
        .whereType<Map<String, dynamic>>()
        .map(ExportItem.fromJson)
        .toList(growable: false);
  }

  /// `POST /api/v1/exports/{export_id}/download-url`
  Future<String> getExportDownloadUrl(String exportId) async {
    await _ensureAccessToken();
    final data = await _post(
      '$_kusshoesBaseUrl/api/v1/exports/$exportId/download-url',
      body: const <String, dynamic>{},
      authenticated: true,
    );
    return data['download_url'] as String? ?? '';
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

  /// Requests a presigned PUT URL to upload the scan video directly to storage.
  /// POST {compute}/api/scan-sessions/{id}/video-upload-url
  /// Body: {"contentType": "video/mp4", "fileSizeBytes": <int>}
  /// Response: {"uploadUrl": "...", "key": "...", "expiresIn": ...}
  Future<Map<String, dynamic>> getVideoUploadUrl({
    required String scanSessionId,
    required int fileSizeBytes,
    String contentType = 'video/mp4',
  }) async {
    _ensureScanToken();
    return await _post(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/video-upload-url',
      body: {
        'contentType': contentType,
        'fileSizeBytes': fileSizeBytes,
      },
      scanScoped: true,
    );
  }

  /// Streams the video file directly to the presigned storage upload URL via HTTP PUT.
  /// Sends Header Content-Type: video/mp4 and NO Authorization header (storage rejects
  /// requests carrying both a bearer token and a signed URL).
  Future<void> uploadVideoToStorage({
    required String uploadUrl,
    required XFile videoFile,
    void Function(int sent, int total)? onProgress,
  }) async {
    final fileLength = await videoFile.length();
    final stream = videoFile.openRead();
    try {
      await _storageDio.put<void>(
        uploadUrl,
        data: stream,
        options: Options(
          headers: {
            Headers.contentTypeHeader: 'video/mp4',
            Headers.contentLengthHeader: fileLength,
          },
        ),
        onSendProgress: onProgress,
      );
    } catch (error) {
      throw ApiException.from(error);
    }
  }

  /// Confirms that the video file was uploaded to storage.
  /// POST {compute}/api/scan-sessions/{id}/video-uploaded
  /// Body: {"key": <key>}
  Future<Map<String, dynamic>> notifyVideoUploaded({
    required String scanSessionId,
    required String key,
  }) async {
    _ensureScanToken();
    return await _post(
      '$_computeBaseUrl/api/scan-sessions/$scanSessionId/video-uploaded',
      body: {'key': key},
      scanScoped: true,
    );
  }

  /// Orchestrates the 3-step presigned video upload:
  /// (1) POST video-upload-url -> {uploadUrl, key, expiresIn}
  /// (2) HTTP PUT streaming video file to uploadUrl (no Auth header)
  /// (3) POST video-uploaded -> {key}
  Future<void> uploadScanVideo({
    required String scanSessionId,
    required XFile videoFile,
    void Function(int sent, int total)? onProgress,
  }) async {
    final fileLength = await videoFile.length();
    final uploadInfo = await getVideoUploadUrl(
      scanSessionId: scanSessionId,
      fileSizeBytes: fileLength,
    );
    final uploadUrl = uploadInfo['uploadUrl'] as String;
    final key = uploadInfo['key'] as String;

    await uploadVideoToStorage(
      uploadUrl: uploadUrl,
      videoFile: videoFile,
      onProgress: onProgress,
    );

    await notifyVideoUploaded(
      scanSessionId: scanSessionId,
      key: key,
    );
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

  /// Saves the reconstructed KIRI scan to a project.
  /// POST {compute}/api/scan-sessions/{id}/save-project
  /// Body: {"projectName": <name>} only — no cropBox.
  Future<KiriStatus> saveKiriProject({
    required String scanSessionId,
    required String projectName,
  }) async {
    _ensureScanToken();
    return _kiriStatus(
      await _post(
        '$_computeBaseUrl/api/scan-sessions/$scanSessionId/save-project',
        body: {'projectName': projectName},
        scanScoped: true,
      ),
    );
  }

  /// Requests GET {compute}/api/scan-sessions/{id}/kiri/preview with redirects disabled.
  /// Returns the presigned Location URL from the 307 redirect.
  Future<String> getKiriPreviewLocationUrl({
    required String scanSessionId,
  }) async {
    _ensureScanToken();
    try {
      final response = await _dio.get<dynamic>(
        '$_computeBaseUrl/api/scan-sessions/$scanSessionId/kiri/preview',
        options: _scanAuthOptions().copyWith(
          followRedirects: false,
          validateStatus: (status) =>
              status != null &&
              ((status >= 200 && status < 300) ||
                  status == 307 ||
                  status == 302 ||
                  status == 303),
        ),
      );

      if (response.statusCode == 307 ||
          response.statusCode == 302 ||
          response.statusCode == 303) {
        final location = response.headers.value('location');
        if (location != null && location.isNotEmpty) {
          return location;
        }
      }

      if (response.data is Map<String, dynamic> &&
          response.data['url'] != null) {
        return response.data['url'] as String;
      }

      final directLocation = response.headers.value('location');
      if (directLocation != null && directLocation.isNotEmpty) {
        return directLocation;
      }

      throw const ApiException(message: 'Không lấy được đường dẫn xem trước model.');
    } on ApiException {
      rethrow;
    } catch (error) {
      throw ApiException.from(error);
    }
  }

  /// Downloads raw preview GLB model bytes:
  /// Follows the 307 redirect from /kiri/preview, then GETs the Location URL
  /// WITHOUT the Authorization header.
  Future<List<int>> getKiriPreviewBytes({
    required String scanSessionId,
  }) async {
    final locationUrl = await getKiriPreviewLocationUrl(
      scanSessionId: scanSessionId,
    );
    try {
      final response = await _storageDio.get<List<int>>(
        locationUrl,
        options: Options(
          responseType: ResponseType.bytes,
          headers: const <String, dynamic>{}, // NO Authorization header
        ),
      );
      return response.data ?? <int>[];
    } catch (error) {
      throw ApiException.from(error);
    }
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
      modelAssetId: status.modelAssetId,
      errorMessage: status.errorMessage,
    );
  }

  // --- Transport ------------------------------------------------------------

  Future<dynamic> _fetch(
    String url, {
    required String method,
    Object? body,
    bool authenticated = false,
    bool scanScoped = false,
  }) async {
    await _ensureCookieJar();
    try {
      final baseOptions = _optionsFor(
        authenticated: authenticated,
        scanScoped: scanScoped,
      );
      final options = (baseOptions ?? Options()).copyWith(method: method);
      final response = await _dio.request<dynamic>(
        url,
        data: body,
        options: options,
      );
      return response.data;
    } catch (error) {
      throw ApiException.from(error);
    }
  }

  Future<Map<String, dynamic>> _post(
    String url, {
    required Object body,
    bool authenticated = false,
    bool scanScoped = false,
  }) async {
    final data = await _fetch(
      url,
      method: 'POST',
      body: body,
      authenticated: authenticated,
      scanScoped: scanScoped,
    );
    return data is Map<String, dynamic> ? data : const <String, dynamic>{};
  }

  Future<Map<String, dynamic>> _get(
    String url, {
    bool authenticated = false,
    bool scanScoped = false,
  }) async {
    final data = await _fetch(
      url,
      method: 'GET',
      authenticated: authenticated,
      scanScoped: scanScoped,
    );
    return data is Map<String, dynamic> ? data : const <String, dynamic>{};
  }

  Future<List<dynamic>> _getList(
    String url, {
    bool authenticated = false,
    bool scanScoped = false,
  }) async {
    final data = await _fetch(
      url,
      method: 'GET',
      authenticated: authenticated,
      scanScoped: scanScoped,
    );
    return data is List ? data : const <dynamic>[];
  }

  Future<Map<String, dynamic>> _patch(
    String url, {
    required Object body,
    bool authenticated = false,
  }) async {
    final data = await _fetch(
      url,
      method: 'PATCH',
      body: body,
      authenticated: authenticated,
    );
    return data is Map<String, dynamic> ? data : const <String, dynamic>{};
  }

  Future<Map<String, dynamic>> _put(
    String url, {
    required Object body,
    bool authenticated = false,
  }) async {
    final data = await _fetch(
      url,
      method: 'PUT',
      body: body,
      authenticated: authenticated,
    );
    return data is Map<String, dynamic> ? data : const <String, dynamic>{};
  }

  Future<Map<String, dynamic>> _delete(
    String url, {
    Object? body,
    bool authenticated = false,
  }) async {
    final data = await _fetch(
      url,
      method: 'DELETE',
      body: body,
      authenticated: authenticated,
    );
    return data is Map<String, dynamic> ? data : const <String, dynamic>{};
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
