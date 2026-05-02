import 'package:flutter/foundation.dart';

class AppEnvironment {
  AppEnvironment._();

  /// Production API URL for the Selm backend
  static const String _productionBaseUrl = 'https://selmapp.com/api';
  
  static const String _apiVersion = '/v1';

  static final String apiBaseUrl = _resolveBaseUrl();
  static final String apiBaseUrlWithVersion = _buildVersionedBaseUrl();

  /// Whether the app is running in production/release mode
  static bool get isProduction => kReleaseMode;

  static String _buildVersionedBaseUrl() {
    return '$apiBaseUrl$_apiVersion';
  }

  static String _resolveBaseUrl() {
    String resolved;

    // Check for compile-time override first
    const override = String.fromEnvironment('API_BASE_URL');
    if (override.trim().isNotEmpty) {
      resolved = _normalize(override);
    } else if (kIsWeb) {
      resolved = _normalize(_resolveWebBaseUrl());
    } else {
      // Mobile/desktop default: use production backend even in debug builds.
      //
      // For local development, override at build/run time:
      // - Android emulator: --dart-define=API_BASE_URL=http://10.0.2.2:8080
      // - iOS simulator:   --dart-define=API_BASE_URL=http://localhost:8080
      resolved = _normalize(_productionBaseUrl);
    }

    if (kDebugMode) {
      print('🌐 AppEnvironment: API Base URL = $resolved');
      print('🔧 AppEnvironment: Release Mode = $kReleaseMode');
    }

    return resolved;
  }

  static String _resolveWebBaseUrl() {
    final uri = Uri.base;
    final scheme = uri.scheme.isNotEmpty ? uri.scheme : 'http';
    final host = uri.host.isNotEmpty ? uri.host : 'localhost';
    final isLocal =
        host == 'localhost' || host == '127.0.0.1' || host.endsWith('.local');
    
    // For production web, use the production URL
    if (!isLocal) {
      return _normalize(_productionBaseUrl);
    }

    final int? port;
    if (isLocal) {
      port = 8080;
    } else {
      port = uri.hasPort ? uri.port : null;
    }

    return Uri(
      scheme: scheme,
      host: host,
      port: port == 80 || port == 443 ? null : port,
    ).toString();
  }

  static String _normalize(String value) {
    var normalized = value.trim();
    if (normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    return normalized;
  }
}

