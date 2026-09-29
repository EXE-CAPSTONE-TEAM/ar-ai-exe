# Shoe Visual Customizer Mobile

Flutter scanner MVP.

## Responsibilities

- Record two guided shoe scan videos:
  - side orbit, 360 degrees around the shoe.
  - top-angle orbit, 30-45 degrees from above.
- Collect required scan metadata.
- Upload both videos and metadata to the FastAPI backend.
- Check backend reconstruction readiness before uploading, so missing COLMAP/OpenMVS/Blender or low resources are reported early.

The mobile app does not perform real-time 3D reconstruction and does not scan the bottom sole in the MVP.

## Run

Flutter is required locally.

```powershell
flutter pub get
flutter run --dart-define=BACKEND_BASE_URL=http://127.0.0.1:8000
```

For Android emulator, use the host bridge URL:

```powershell
flutter run --dart-define=BACKEND_BASE_URL=http://10.0.2.2:8000
```

## Physical Android device

For local LAN testing, do not use `127.0.0.1`. Use your laptop LAN IP:

```powershell
flutter run --dart-define=BACKEND_BASE_URL=http://192.168.1.20:8000
```

For VPS/production:

```powershell
flutter build apk --release --dart-define=BACKEND_BASE_URL=https://your-domain.example.com
```

The backend must set `WEB_APP_BASE_URL` to the same public web origin so the app can open `/design?scanId=...` after upload.

Full deployment guide: `docs/vps-android-deployment.md`.

## Release (Android APK)

`.github/workflows/mobile-release.yml` builds the signed APK on `ubuntu-latest`:

- push a tag `mobile-vX.Y.Z` → GitHub release `KusShoes Android vX.Y.Z` with `KusShoes-X.Y.Z.apk`,
  the stable-name copy `KusShoes-Android.apk` and `SHA256SUMS.txt`. It is **never** marked
  "latest" (that pointer belongs to the desktop app's download link and updater);
- pull requests touching `mobile/` → the same build as a dry run (APK kept as a workflow artifact).

`versionName` is the tag's `X.Y.Z`; `versionCode` is `X*10000 + Y*100 + Z`, so every new tag must be
higher than the last. Release builds default to production hosts (`lib/config/app_config.dart`),
so no `--dart-define` is needed.

Signing: repo secrets `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`,
`ANDROID_KEY_PASSWORD`. The workflow refuses to publish an APK whose certificate SHA-256 is not
`6cd7bf77…3dfd` (the release key), so a debug-signed build can never ship. APKPure (and Google
Play) only accept updates signed with the same key: losing it means users must uninstall and
reinstall, so keep an offline backup of the keystore.

APKPure: download `KusShoes-Android.apk` from the release and upload it in the APKPure developer
console for package `vn.kusshoes.mobile`.
