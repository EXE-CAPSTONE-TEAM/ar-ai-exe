import 'dart:convert';
import 'dart:typed_data';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/services/backend_api.dart';
import 'package:shoe_visual_customizer_mobile/services/token_storage.dart';

import 'relay_contract_test.dart' show MockDioAdapter;

class _MemoryTokenStorage extends TokenStorage {
  _MemoryTokenStorage(this.values);

  final Map<String, String> values;

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;

  @override
  Future<void> delete(String key) async => values.remove(key);
}

ResponseBody _json(Map<String, dynamic> body) => ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );

void main() {
  test('uploadProjectThumbnail: upload-url, presigned PUT, then confirm',
      () async {
    final apiCalls = <RequestOptions>[];
    final dio = Dio()
      ..httpClientAdapter = MockDioAdapter((options, _) async {
        apiCalls.add(options);
        if (options.path.endsWith('/assets/upload-url')) {
          return _json({
            'upload_url': 'https://storage.example.com/put-thumb',
            'asset_id': 'asset-1',
            'file_path': 'thumbnails/proj-1/x.webp',
          });
        }
        return _json({'id': 'asset-1', 'status': 'ready'});
      });

    RequestOptions? put;
    var putBytes = <int>[];
    final storageDio = Dio()
      ..httpClientAdapter = MockDioAdapter((options, stream) async {
        put = options;
        await for (final chunk in stream!) {
          putBytes.addAll(chunk);
        }
        return ResponseBody.fromString('', 200);
      });

    final api = BackendApi(
      dio: dio,
      storageDio: storageDio,
      kusshoesBaseUrl: 'https://api.example.com',
      cookieJar: CookieJar(),
      tokenStorage: _MemoryTokenStorage({'kusshoes_access_token': 'user-token'}),
    );
    final bytes = Uint8List.fromList(utf8.encode('RIFF....WEBPVP8 image'));

    await api.uploadProjectThumbnail(
      projectId: 'proj-1',
      bytes: bytes,
      contentType: 'image/webp',
    );

    expect(apiCalls, hasLength(2));
    expect(
      apiCalls[0].path,
      'https://api.example.com/api/v1/projects/proj-1/assets/upload-url',
    );
    expect(apiCalls[0].data, {
      'asset_type': 'thumbnail',
      'filename': 'thumbnail.webp',
      'content_type': 'image/webp',
    });
    expect(apiCalls[0].headers['Authorization'], 'Bearer user-token');

    expect(put!.method, 'PUT');
    expect(put!.path, 'https://storage.example.com/put-thumb');
    expect(put!.headers[Headers.contentTypeHeader], 'image/webp');
    // The presigned URL carries its own signature; no bearer token may leak to storage.
    expect(put!.headers.containsKey('Authorization'), isFalse);
    expect(putBytes, bytes);

    expect(
      apiCalls[1].path,
      'https://api.example.com/api/v1/projects/proj-1/assets/confirm',
    );
    expect(apiCalls[1].data, {'asset_id': 'asset-1', 'file_size_bytes': bytes.length});
  });

  test('thumbnailFromDataUrl decodes webp and png, rejects anything else', () {
    final webp = BackendApi.thumbnailFromDataUrl(
      'data:image/webp;base64,${base64Encode([1, 2, 3])}',
    );
    expect(webp!.contentType, 'image/webp');
    expect(webp.bytes, [1, 2, 3]);

    final png = BackendApi.thumbnailFromDataUrl(
      'data:image/png;base64,${base64Encode([4, 5])}',
    );
    expect(png!.contentType, 'image/png');

    expect(BackendApi.thumbnailFromDataUrl('data:text/html;base64,PGI+'), isNull);
    expect(BackendApi.thumbnailFromDataUrl('error:SecurityError'), isNull);
    expect(BackendApi.thumbnailFromDataUrl('data:image/png;base64,'), isNull);
  });
}
