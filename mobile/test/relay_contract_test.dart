import 'dart:convert';
import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shoe_visual_customizer_mobile/services/backend_api.dart';

class MockDioAdapter implements HttpClientAdapter {
  MockDioAdapter(this.handler);

  final Future<ResponseBody> Function(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
  ) handler;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) =>
      handler(options, requestStream);

  @override
  void close({bool force = false}) {}
}

void main() {
  group('Ticket-12 Relay API contract', () {
    test('1. getVideoUploadUrl posts file size and content type with scan auth',
        () async {
      RequestOptions? recordedOptions;

      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options, stream) async {
        recordedOptions = options;
        return ResponseBody.fromString(
          jsonEncode({
            'uploadUrl': 'https://storage.example.com/put-video',
            'key': 'staging/video-123.mp4',
            'expiresIn': 900,
          }),
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        );
      });

      final api = BackendApi(
        dio: dio,
        computeBaseUrl: 'https://compute.example.com',
      );
      api.setScanTokenForTesting('scan-secret-token');

      final result = await api.getVideoUploadUrl(
        scanSessionId: 'session-1',
        fileSizeBytes: 5000000,
      );

      expect(recordedOptions, isNotNull);
      expect(recordedOptions!.method, 'POST');
      expect(
        recordedOptions!.path,
        'https://compute.example.com/api/scan-sessions/session-1/video-upload-url',
      );
      expect(
        recordedOptions!.headers['Authorization'],
        'Bearer scan-secret-token',
      );

      final body = recordedOptions!.data as Map<String, dynamic>;
      expect(body['contentType'], 'video/mp4');
      expect(body['fileSizeBytes'], 5000000);

      expect(result['uploadUrl'], 'https://storage.example.com/put-video');
      expect(result['key'], 'staging/video-123.mp4');
      expect(result['expiresIn'], 900);
    });

    test('2. uploadVideoToStorage PUTs streaming video with NO Authorization header',
        () async {
      RequestOptions? recordedOptions;

      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options, stream) async {
        recordedOptions = options;
        return ResponseBody.fromString('', 200);
      });

      final api = BackendApi(
        dio: dio,
        storageDio: dio,
        computeBaseUrl: 'https://compute.example.com',
      );
      api.setScanTokenForTesting('scan-secret-token');

      final fakeVideo = XFile.fromData(
        Uint8List.fromList([1, 2, 3, 4, 5, 6, 7, 8]),
        name: 'scan.mp4',
        mimeType: 'video/mp4',
      );

      await api.uploadVideoToStorage(
        uploadUrl: 'https://storage.example.com/put-video?signature=abc',
        videoFile: fakeVideo,
      );

      expect(recordedOptions, isNotNull);
      expect(recordedOptions!.method, 'PUT');
      expect(
        recordedOptions!.path,
        'https://storage.example.com/put-video?signature=abc',
      );
      expect(recordedOptions!.headers['Content-Type'], 'video/mp4');
      // Storage rejects requests carrying both bearer token and signed URL:
      expect(recordedOptions!.headers.containsKey('Authorization'), isFalse);
    });

    test('3. notifyVideoUploaded posts key with scan auth', () async {
      RequestOptions? recordedOptions;

      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options, stream) async {
        recordedOptions = options;
        return ResponseBody.fromString(
          jsonEncode({'status': 'uploaded'}),
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        );
      });

      final api = BackendApi(
        dio: dio,
        computeBaseUrl: 'https://compute.example.com',
      );
      api.setScanTokenForTesting('scan-secret-token');

      final result = await api.notifyVideoUploaded(
        scanSessionId: 'session-1',
        key: 'staging/video-123.mp4',
      );

      expect(recordedOptions, isNotNull);
      expect(recordedOptions!.method, 'POST');
      expect(
        recordedOptions!.path,
        'https://compute.example.com/api/scan-sessions/session-1/video-uploaded',
      );
      expect(
        recordedOptions!.headers['Authorization'],
        'Bearer scan-secret-token',
      );

      final body = recordedOptions!.data as Map<String, dynamic>;
      expect(body['key'], 'staging/video-123.mp4');
      expect(result['status'], 'uploaded');
    });

    test('4. uploadScanVideo orchestrates the complete 3-step sequence',
        () async {
      final calls = <String>[];

      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options, stream) async {
        calls.add('${options.method} ${options.path}');
        if (options.path.endsWith('/video-upload-url')) {
          return ResponseBody.fromString(
            jsonEncode({
              'uploadUrl': 'https://storage.example.com/presigned-put',
              'key': 'staging/scan.mp4',
              'expiresIn': 900,
            }),
            200,
            headers: {
              Headers.contentTypeHeader: [Headers.jsonContentType],
            },
          );
        } else if (options.path.contains('presigned-put')) {
          expect(options.headers.containsKey('Authorization'), isFalse);
          return ResponseBody.fromString('', 200);
        } else if (options.path.endsWith('/video-uploaded')) {
          return ResponseBody.fromString(
            jsonEncode({'status': 'uploaded'}),
            200,
            headers: {
              Headers.contentTypeHeader: [Headers.jsonContentType],
            },
          );
        }
        return ResponseBody.fromString('', 404);
      });

      final api = BackendApi(
        dio: dio,
        storageDio: dio,
        computeBaseUrl: 'https://compute.example.com',
      );
      api.setScanTokenForTesting('scan-secret-token');

      final fakeVideo = XFile.fromData(
        Uint8List.fromList([10, 20, 30, 40]),
        name: 'scan.mp4',
        mimeType: 'video/mp4',
      );

      await api.uploadScanVideo(
        scanSessionId: 'session-1',
        videoFile: fakeVideo,
      );

      expect(calls, [
        'POST https://compute.example.com/api/scan-sessions/session-1/video-upload-url',
        'PUT https://storage.example.com/presigned-put',
        'POST https://compute.example.com/api/scan-sessions/session-1/video-uploaded',
      ]);
    });

    test('5. saveKiriProject sends projectName ONLY — strictly no cropBox',
        () async {
      RequestOptions? recordedOptions;

      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options, stream) async {
        recordedOptions = options;
        return ResponseBody.fromString(
          jsonEncode({
            'scanSessionId': 'session-1',
            'status': 'saving',
            'progress': 100,
          }),
          200,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        );
      });

      final api = BackendApi(
        dio: dio,
        computeBaseUrl: 'https://compute.example.com',
      );
      api.setScanTokenForTesting('scan-secret-token');

      final result = await api.saveKiriProject(
        scanSessionId: 'session-1',
        projectName: 'Đôi giày chạy bộ',
      );

      expect(recordedOptions, isNotNull);
      expect(recordedOptions!.method, 'POST');
      expect(
        recordedOptions!.path,
        'https://compute.example.com/api/scan-sessions/session-1/save-project',
      );

      final body = recordedOptions!.data as Map<String, dynamic>;
      expect(body, {'projectName': 'Đôi giày chạy bộ'});
      expect(body.containsKey('cropBox'), isFalse);
      expect(result.status, 'saving');
    });

    test('6. getKiriPreviewLocationUrl handles 307 redirect without following it',
        () async {
      RequestOptions? recordedOptions;

      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options, stream) async {
        recordedOptions = options;
        return ResponseBody.fromString(
          '',
          307,
          headers: {
            'location': [
              'https://storage.example.com/models/raw.glb?X-Amz-Signature=xyz'
            ],
          },
        );
      });

      final api = BackendApi(
        dio: dio,
        computeBaseUrl: 'https://compute.example.com',
      );
      api.setScanTokenForTesting('scan-secret-token');

      final location =
          await api.getKiriPreviewLocationUrl(scanSessionId: 'session-1');

      expect(recordedOptions, isNotNull);
      expect(recordedOptions!.method, 'GET');
      expect(recordedOptions!.followRedirects, isFalse);
      expect(
        recordedOptions!.headers['Authorization'],
        'Bearer scan-secret-token',
      );
      expect(
        location,
        'https://storage.example.com/models/raw.glb?X-Amz-Signature=xyz',
      );
    });

    test('7. getKiriPreviewBytes GETs the Location URL with NO Authorization header',
        () async {
      final requests = <RequestOptions>[];

      final dio = Dio();
      dio.httpClientAdapter = MockDioAdapter((options, stream) async {
        requests.add(options);
        if (options.path.endsWith('/kiri/preview')) {
          return ResponseBody.fromString(
            '',
            307,
            headers: {
              'location': ['https://storage.example.com/models/raw.glb?signed=1'],
            },
          );
        } else if (options.path.contains('raw.glb')) {
          return ResponseBody.fromBytes(
            [0x67, 0x6C, 0x54, 0x46], // glTF magic
            200,
            headers: {
              Headers.contentTypeHeader: ['model/gltf-binary'],
            },
          );
        }
        return ResponseBody.fromString('', 404);
      });

      final api = BackendApi(
        dio: dio,
        storageDio: dio,
        computeBaseUrl: 'https://compute.example.com',
      );
      api.setScanTokenForTesting('scan-secret-token');

      final bytes =
          await api.getKiriPreviewBytes(scanSessionId: 'session-1');

      expect(requests, hasLength(2));
      // First request: /kiri/preview with auth
      expect(requests[0].followRedirects, isFalse);
      expect(requests[0].headers['Authorization'], 'Bearer scan-secret-token');

      // Second request: Location URL strictly WITHOUT Authorization header
      expect(requests[1].path, 'https://storage.example.com/models/raw.glb?signed=1');
      expect(requests[1].headers.containsKey('Authorization'), isFalse);

      expect(bytes, [0x67, 0x6C, 0x54, 0x46]);
    });
  });
}
