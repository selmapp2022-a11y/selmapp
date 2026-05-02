import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorage {
  // Configure storage with platform-specific options
  // WebOptions is required for web platform to work properly
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
    webOptions: WebOptions(
      dbName: 'selm_secure_storage',
      publicKey: 'selm_public_key',
    ),
  );

  // Write a key-value pair to secure storage
  Future<void> write(String key, String value) async {
    try {
      await _storage.write(key: key, value: value);
      if (kDebugMode) {
        print('💾 SecureStorage: Wrote key "$key"');
      }
    } catch (e) {
      if (kDebugMode) {
        print('❌ SecureStorage: Failed to write "$key": $e');
      }
      // On web, storage errors are common - don't throw, just log
      if (!kIsWeb) {
        throw StorageException('Failed to write to secure storage: $e');
      }
    }
  }

  // Read a value from secure storage
  Future<String?> read(String key) async {
    try {
      final value = await _storage.read(key: key);
      if (kDebugMode) {
        print(
          '📖 SecureStorage: Read key "$key" = ${value != null ? "(has value)" : "null"}',
        );
      }
      return value;
    } catch (e) {
      if (kDebugMode) {
        print('❌ SecureStorage: Failed to read "$key": $e');
      }
      // On web, storage errors are common - return null instead of throwing
      if (!kIsWeb) {
        throw StorageException('Failed to read from secure storage: $e');
      }
      return null;
    }
  }

  // Delete a key from secure storage
  Future<void> delete(String key) async {
    try {
      await _storage.delete(key: key);
    } catch (e) {
      if (kDebugMode) {
        print('❌ SecureStorage: Failed to delete "$key": $e');
      }
      // On web, storage errors are common - don't throw, just log
      if (!kIsWeb) {
        throw StorageException('Failed to delete from secure storage: $e');
      }
    }
  }

  // Check if a key exists in secure storage
  Future<bool> containsKey(String key) async {
    try {
      return await _storage.containsKey(key: key);
    } catch (e) {
      if (kDebugMode) {
        print('❌ SecureStorage: Failed to check "$key": $e');
      }
      if (!kIsWeb) {
        throw StorageException('Failed to check key in secure storage: $e');
      }
      return false;
    }
  }

  // Get all keys from secure storage
  Future<Map<String, String>> readAll() async {
    try {
      return await _storage.readAll();
    } catch (e) {
      if (kDebugMode) {
        print('❌ SecureStorage: Failed to readAll: $e');
      }
      if (!kIsWeb) {
        throw StorageException('Failed to read all from secure storage: $e');
      }
      return {};
    }
  }

  // Clear all data from secure storage
  Future<void> deleteAll() async {
    try {
      await _storage.deleteAll();
    } catch (e) {
      if (kDebugMode) {
        print('❌ SecureStorage: Failed to deleteAll: $e');
      }
      if (!kIsWeb) {
        throw StorageException('Failed to clear secure storage: $e');
      }
    }
  }

  /// Clears the authentication/session-related keys from secure storage.
  ///
  /// This is intentionally conservative (only auth + profile keys) so we don't
  /// wipe user settings or other app caches.
  Future<void> clearSession() async {
    const keys = <String>[
      // Tokens (new + legacy)
      'access_token',
      'auth_token',
      'refresh_token',
      // Cached user data
      'user_data',
      'user_profile',
      // Onboarding state
      'onboarding_completed',
    ];

    for (final key in keys) {
      await delete(key);
    }
  }

  // Authentication token helpers
  Future<void> saveAuthTokens({
    required String accessToken,
    String? refreshToken,
  }) async {
    await write('access_token', accessToken);
    if (refreshToken != null) {
      await write('refresh_token', refreshToken);
    }
  }

  Future<String?> getAccessToken() async {
    return await read('access_token');
  }

  Future<String?> getRefreshToken() async {
    return await read('refresh_token');
  }

  Future<bool> isAuthenticated() async {
    final token = await getAccessToken();
    return token != null && token.isNotEmpty;
  }

  Future<void> clearAuthTokens() async {
    await delete('access_token');
    await delete('refresh_token');
  }

  // User profile helpers
  Future<void> saveUserProfile(String userProfileJson) async {
    await write('user_profile', userProfileJson);
  }

  Future<String?> getUserProfile() async {
    return await read('user_profile');
  }

  Future<void> clearUserProfile() async {
    await delete('user_profile');
  }

  // Onboarding helpers
  Future<void> markOnboardingComplete() async {
    await write('onboarding_completed', 'true');
  }

  Future<bool> isOnboardingComplete() async {
    final completed = await read('onboarding_completed');
    return completed == 'true';
  }

  Future<void> clearOnboardingStatus() async {
    await delete('onboarding_completed');
  }

  // Settings helpers
  Future<void> saveSetting(String key, String value) async {
    await write('setting_$key', value);
  }

  Future<String?> getSetting(String key) async {
    return await read('setting_$key');
  }

  Future<void> deleteSetting(String key) async {
    await delete('setting_$key');
  }
}

class StorageException implements Exception {
  final String message;

  StorageException(this.message);

  @override
  String toString() => 'StorageException: $message';
}
