# Shoe Visual Customizer Mobile

Flutter scanner MVP.

## Responsibilities

- Record guided shoe scan video.
- Collect required scan metadata.
- Upload video and metadata to the FastAPI backend.

The mobile app does not perform real-time 3D reconstruction.

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