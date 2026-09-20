/// Build-time configuration for the KusShoes scanner.
///
/// Nothing here may default to a developer machine: a release APK built with
/// no `--dart-define` must point at production over TLS (NFR-SEC-01). For LAN
/// testing pass the hosts explicitly, e.g.
///
/// ```
/// flutter run \
///   --dart-define=KUSSHOES_BASE_URL=http://10.0.2.2:8000 \
///   --dart-define=COMPUTE_BASE_URL=http://10.0.2.2:8010 \
///   --dart-define=ALLOW_INSECURE_HTTP=true
/// ```
class AppConfig {
  const AppConfig._();

  static const kusshoesBaseUrl = String.fromEnvironment(
    'KUSSHOES_BASE_URL',
    defaultValue: 'https://api.kusshoes.vn',
  );

  /// Placeholder origin for `/api/system/*` probes made before a scan is
  /// bootstrapped. Once [BackendApi.beginScan] runs, the real compute origin
  /// comes from the bootstrap response's `compute_api_url`.
  static const computeBaseUrl = String.fromEnvironment(
    'COMPUTE_BASE_URL',
    defaultValue: 'https://compute.kusshoes.vn',
  );

  /// Public marketing site and Kus Studio web app.
  ///
  /// Only the root path is linked: the deployed site uses a hand-rolled
  /// history-API router with no SPA rewrite, so every sub-path (/pricing,
  /// /dashboard, ...) currently answers 404. Once a rewrite is in place,
  /// [webUrl] can be used to deep-link.
  static const webAppUrl = String.fromEnvironment(
    'KUSSHOES_WEB_URL',
    defaultValue: 'https://kusshoes.vercel.app',
  );

  /// Empty until SC-33 (legal pages) ships. NFR-LEG-06 requires a reachable
  /// privacy-policy URL before the Android listing goes up, so set this with
  /// --dart-define at that point; while it is empty the app hides the link
  /// rather than sending people to a page that does not exist.
  static const privacyPolicyUrl = String.fromEnvironment('KUSSHOES_PRIVACY_URL');

  static bool get hasPrivacyPolicyUrl => privacyPolicyUrl.isNotEmpty;

  /// Builds an absolute URL on the web app.
  static String webUrl([String path = '']) {
    final base = webAppUrl.replaceAll(RegExp(r'/+$'), '');
    if (path.isEmpty) {
      return base;
    }
    return path.startsWith('/') ? '$base$path' : '$base/$path';
  }

  /// Must be opted into explicitly; guards against a cleartext host slipping
  /// into a store build.
  static const allowInsecureHttp = bool.fromEnvironment('ALLOW_INSECURE_HTTP');

  /// Throws if a build is wired to cleartext without the explicit opt-in, so
  /// the mistake surfaces at startup instead of as a silent network failure
  /// behind the Android network-security config.
  static void assertTransportIsAllowed() {
    for (final url in [kusshoesBaseUrl, computeBaseUrl]) {
      if (Uri.parse(url).scheme == 'http' && !allowInsecureHttp) {
        throw StateError(
          'Cấu hình không hợp lệ: $url dùng http. Thêm '
          '--dart-define=ALLOW_INSECURE_HTTP=true cho build phát triển, '
          'hoặc trỏ sang https cho bản phát hành.',
        );
      }
    }
  }
}
