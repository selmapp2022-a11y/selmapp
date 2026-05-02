# SelmApp Frontend

Flutter client for the SelmApp English learning platform. The app targets web, Android, and iOS with a shared codebase under `lib/`.

## Prerequisites

- Flutter SDK `3.8.1` (see `pubspec.yaml`).
- Running backend API (FastAPI) on `http://localhost:8080` by default. Start it with `python backend/main.py` or an equivalent Uvicorn command.
- Dart `--dart-define` support (built into `flutter` CLI) for overriding runtime configuration.

## API base URL (AppEnvironment)

`AppEnvironment.apiBaseUrl` centralizes how the client decides which backend host to call:

1. `--dart-define=API_BASE_URL=<url>` always wins. Use this for staging/production (e.g., DigitalOcean) or when a physical device needs to reach your computer over LAN.
2. Web builds (`flutter run -d chrome`) fall back to the browser origin. If the origin is `localhost`, the port is forced to `8080` so the SPA can talk to the local FastAPI server.
3. Android emulators default to `http://10.0.2.2:8080` (the Android Virtual Device loopback to your host).
4. iOS simulator, macOS, Windows, Linux default to `http://localhost:8080`.
5. Physical Android/iOS devices should be launched with an explicit `API_BASE_URL` that points to your computer’s LAN IP (e.g., `http://192.168.1.50:8080`).

The networking layer automatically appends `/api/v1`, so the base URL you provide should only contain the scheme, host, and (optional) port.

The backend already allows `*` CORS origins in development, so no extra configuration is required for local testing.

## Running the app

### Web (Chrome or Edge)

```bash
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8080
```

Use your public API URL for staging/production:

```bash
flutter build web --release --dart-define=API_BASE_URL=https://api.example.com
```

### Android emulator

```bash
flutter emulators --launch <emulator_id>
flutter run -d <emulator_id>
```

No extra flags are necessary—the default base URL already targets `http://10.0.2.2:8080`.

### Physical Android device

```bash
flutter run -d <device_id> --dart-define=API_BASE_URL=http://<your-computer-ip>:8080
```

Make sure your computer and device share the same network and the backend is reachable on that IP.

### iOS simulator / macOS

```bash
flutter run -d ios
```

The simulator uses `http://localhost:8080` automatically. For a physical iOS device replace `localhost` with your computer’s IP via `--dart-define` as shown for Android.

## Distributing builds

- **Web**: `flutter build web --release --dart-define=API_BASE_URL=https://api.yourdomain.com` then upload `build/web` to your hosting provider (e.g., DigitalOcean Spaces/App Platform).
- **Android**: `flutter build apk --release --dart-define=API_BASE_URL=https://api.yourdomain.com` (or `appbundle` for Play Store).
- **iOS**: `flutter build ipa --release --dart-define=API_BASE_URL=https://api.yourdomain.com`.

Remember to keep the backend URL in sync with your deployment target. The same binary can be reused across environments by changing only the `API_BASE_URL` flag at build/run time.
