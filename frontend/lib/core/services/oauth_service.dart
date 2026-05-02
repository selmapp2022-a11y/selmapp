import 'package:flutter/foundation.dart';
import 'package:url_launcher/url_launcher.dart';

import '../network/api_client.dart';
import '../storage/secure_storage.dart';

class OAuthService {
  static const String _oauthStateKey = 'oauth_state';
  static const String _oauthProviderKey = 'oauth_provider';

  final ApiClient _apiClient;
  final SecureStorage _storage;

  OAuthService(this._apiClient, this._storage);

  // Login with Google
  Future<Map<String, dynamic>> loginWithGoogle() async {
    return _startOAuthFlow('google');
  }

  // Login with GitHub
  Future<Map<String, dynamic>> loginWithGitHub() async {
    return _startOAuthFlow('github');
  }

  // Login with Facebook
  Future<Map<String, dynamic>> loginWithFacebook() async {
    return _startOAuthFlow('facebook');
  }

  Future<Map<String, dynamic>> _startOAuthFlow(String provider) async {
    try {
      // Ask backend for provider authorization URL + generated state
      final response = await _apiClient.get('/auth/oauth/$provider/authorize');
      final data = response.data;

      if (data is! Map) {
        return {
          'success': false,
          'message': 'Invalid OAuth response from server',
        };
      }

      final authUrl = data['auth_url']?.toString();
      final state = data['state']?.toString();

      if (authUrl == null || authUrl.isEmpty || state == null || state.isEmpty) {
        return {
          'success': false,
          'message': 'Invalid OAuth response from server',
        };
      }

      // Persist provider + state so we can validate on redirect back
      await _storage.write(_oauthProviderKey, provider);
      await _storage.write(_oauthStateKey, state);

      final uri = Uri.parse(authUrl);
      final launched = await launchUrl(
        uri,
        mode: kIsWeb ? LaunchMode.platformDefault : LaunchMode.externalApplication,
        // On web, keep the flow in the same tab so the user returns to the app naturally.
        webOnlyWindowName: kIsWeb ? '_self' : null,
      );

      if (!launched) {
        return {
          'success': false,
          'message': 'Could not launch OAuth URL',
        };
      }

      return {
        'success': true,
        'provider': provider,
        'message': 'OAuth flow initiated',
      };
    } catch (e) {
      if (kDebugMode) {
        print('❌ OAuth start error ($provider): $e');
      }
      return {
        'success': false,
        'message': 'OAuth error: ${e.toString()}',
      };
    }
  }

  /// Completes OAuth2 login after the provider redirects back to the web app.
  ///
  /// Expected flow (web):
  /// - frontend calls `/api/v1/auth/oauth/{provider}/authorize`
  /// - backend returns `auth_url` and `state`
  /// - frontend redirects user to `auth_url`
  /// - provider redirects back to `OAUTH_REDIRECT_URI` with `code` and `state`
  /// - frontend calls `/api/v1/auth/oauth/login` to exchange `code` for JWT tokens
  Future<bool> completeOAuthFromRedirect({
    required String code,
    String? state,
  }) async {
    try {
      final provider = await _storage.read(_oauthProviderKey);
      final storedState = await _storage.read(_oauthStateKey);

      if (provider == null || provider.isEmpty) {
        if (kDebugMode) {
          print('❌ OAuth complete: missing provider in storage');
        }
        return false;
      }

      // Validate state when we have both values
      if (state != null &&
          state.isNotEmpty &&
          storedState != null &&
          storedState.isNotEmpty &&
          storedState != state) {
        if (kDebugMode) {
          print('❌ OAuth complete: invalid state (possible CSRF)');
        }
        return false;
      }

      final response = await _apiClient.post(
        '/auth/oauth/login',
        data: {
          'provider': provider,
          'code': code,
          if (state != null && state.isNotEmpty) 'state': state,
        },
      );

      final data = response.data;
      if (data is! Map) return false;

      final accessToken = data['access_token']?.toString();
      final refreshToken = data['refresh_token']?.toString();

      if (accessToken == null || accessToken.isEmpty) return false;

      // Keep both keys in sync (ApiClient + AuthService use them)
      await _storage.write('access_token', accessToken);
      await _storage.write('auth_token', accessToken);

      if (refreshToken != null && refreshToken.isNotEmpty) {
        await _storage.write('refresh_token', refreshToken);
      }

      // Cleanup transient OAuth state
      await _storage.delete(_oauthStateKey);
      await _storage.delete(_oauthProviderKey);

      return true;
    } catch (e) {
      if (kDebugMode) {
        print('❌ OAuth complete error: $e');
      }
      return false;
    }
  }

  /// Store tokens received from backend redirect (when backend handles code exchange).
  ///
  /// This is used when the backend exchanges the OAuth code for tokens and
  /// redirects back to the frontend with tokens in the URL query params.
  Future<void> storeTokensFromRedirect({
    required String accessToken,
    String? refreshToken,
  }) async {
    // Keep both keys in sync (ApiClient + AuthService use them)
    await _storage.write('access_token', accessToken);
    await _storage.write('auth_token', accessToken);

    if (refreshToken != null && refreshToken.isNotEmpty) {
      await _storage.write('refresh_token', refreshToken);
    }

    // Cleanup transient OAuth state
    await _storage.delete(_oauthStateKey);
    await _storage.delete(_oauthProviderKey);

    if (kDebugMode) {
      print('✅ OAuth tokens stored from backend redirect');
    }
  }

  // Check if OAuth provider is available on the current platform
  bool isProviderAvailable(String provider) {
    switch (provider.toLowerCase()) {
      case 'google':
        return true; // Available on all platforms
      case 'github':
        return true; // Available on all platforms
      case 'facebook':
        return true; // Available on all platforms
      default:
        return false;
    }
  }

  // Get provider display name
  String getProviderDisplayName(String provider) {
    switch (provider.toLowerCase()) {
      case 'google':
        return 'Google';
      case 'github':
        return 'GitHub';
      case 'facebook':
        return 'Facebook';
      default:
        return provider;
    }
  }

  // Get provider icon (you would use actual icons in your app)
  String getProviderIcon(String provider) {
    switch (provider.toLowerCase()) {
      case 'google':
        return '🌐'; // Replace with actual Google icon
      case 'github':
        return '🐱'; // Replace with actual GitHub icon
      case 'facebook':
        return '📘'; // Replace with actual Facebook icon
      default:
        return '🔐';
    }
  }
}
