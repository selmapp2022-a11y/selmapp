import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../config/app_environment.dart';
import '../network/api_client.dart';
import '../storage/secure_storage.dart';

class AuthService {
  final ApiClient _apiClient;
  final SecureStorage _secureStorage;
  static const String _tokenKey = 'auth_token';
  static const String _refreshTokenKey = 'refresh_token';
  static const String _userDataKey = 'user_data';

  AuthService(this._apiClient, this._secureStorage);

  // Test connectivity to backend
  Future<bool> testConnectivity() async {
    if (kIsWeb) {
      if (kDebugMode) {
        print(
          '🌐 Web platform detected, skipping direct socket connectivity test.',
        );
      }
      return true;
    }

    final backend = Uri.parse(AppEnvironment.apiBaseUrl);
    final defaultPort = backend.hasPort
        ? backend.port
        : backend.scheme == 'https'
        ? 443
        : 8080;
    final addresses = <String>{
      backend.host,
      '10.0.2.2',
      '127.0.0.1',
      'localhost',
      '192.168.1.100',
    }.where((host) => host.isNotEmpty).toList();

    if (kDebugMode) {
      print(
        '🔍 Testing connectivity to backend (${AppEnvironment.apiBaseUrl})...',
      );
    }

    for (final address in addresses) {
      try {
        if (kDebugMode) {
          print('   Trying $address:$defaultPort...');
        }
        final socket = await Socket.connect(
          address,
          defaultPort,
          timeout: const Duration(seconds: 3),
        );
        await socket.close();
        if (kDebugMode) {
          print('✅ Backend connectivity test passed using $address');
        }
        return true;
      } catch (e) {
        if (kDebugMode) {
          print('   ❌ $address failed: $e');
        }
        continue;
      }
    }

    if (kDebugMode) {
      print('❌ Backend connectivity test failed on all addresses');
      print('💡 Make sure backend is running on ${AppEnvironment.apiBaseUrl}');
      print('💡 For Android emulator, 10.0.2.2 is typically used');
      print('💡 For physical device, use your computer\'s IP address');
    }
    return false;
  }

  // Register user
  Future<Map<String, dynamic>> register({
    required String email,
    required String password,
    required String fullName,
    String? phoneNumber,
  }) async {
    try {
      // Remove phone_number from request as it's not in the UserCreate schema
      final requestData = {
        'email': email,
        'password': password,
        'full_name': fullName,
        'username': email.split('@')[0], // Use email prefix as username
      };

      if (kDebugMode) {
        print(
          '🌐 Sending register request to: ${_apiClient.baseUrl}/auth/register',
        );
        print('📤 Request data: $requestData');
      }

      final response = await _apiClient.post(
        '/auth/register',
        data: requestData,
      );

      if (kDebugMode) {
        print('✅ Register response status: ${response.statusCode}');
        print('📥 Register response data: ${response.data}');
      }

      if (response.statusCode == 200) {
        final data = response.data;
        await _saveAuthData(data);
        return {'success': true, 'data': data};
      }
      return {'success': false, 'message': 'Registration failed'};
    } catch (e) {
      if (kDebugMode) {
        print('❌ Register error: $e');
        print('🔍 Error type: ${e.runtimeType}');
      }
      return {'success': false, 'message': _getErrorMessage(e)};
    }
  }

  // Login user
  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    try {
      if (kDebugMode) {
        print('🔐 AuthService: Starting login process...');
      }

      final formData = FormData.fromMap({
        'username': email,
        'password': password,
      });

      if (kDebugMode) {
        print(
          '📤 AuthService: Sending login request to: ${_apiClient.baseUrl}/auth/login',
        );
      }
      if (kDebugMode) {
        print('📋 AuthService: Login form data: ${formData.fields}');
      }

      final response = await _apiClient.post('/auth/login', data: formData);
      if (kDebugMode) {
        print('📥 AuthService: Login response status: ${response.statusCode}');
        print('📄 AuthService: Login response data: ${response.data}');
        print('🔍 AuthService: Response data type: ${response.data.runtimeType}');
        print(
          '🔍 AuthService: Response data keys: ${response.data?.keys?.toList() ?? "null"}',
        );
      }

      if (response.statusCode == 200) {
        final data = response.data;
        if (kDebugMode) {
          print('✅ AuthService: Login successful, saving auth data...');
          print('🔍 AuthService: Data to save: $data');
        }
        await _saveAuthData(data);

        // Fetch fresh user profile from server to get latest onboarding status
        // This ensures we always have the current onboarding_completed value
        await refreshUserData();

        return {'success': true, 'data': data};
      }
      if (kDebugMode) {
        print('❌ AuthService: Login failed with status ${response.statusCode}');
      }
      return {'success': false, 'message': 'Login failed'};
    } catch (e) {
      if (kDebugMode) {
        print('💥 AuthService: Login error: $e');
      }
      return {'success': false, 'message': _getErrorMessage(e)};
    }
  }

  // OAuth2 Login
  Future<Map<String, dynamic>> oauthLogin({
    required String provider, // 'google', 'github', 'facebook'
    required String accessToken,
  }) async {
    try {
      final response = await _apiClient.post(
        '/auth/oauth/$provider',
        data: {'access_token': accessToken},
      );

      if (response.statusCode == 200) {
        final data = response.data;
        await _saveAuthData(data);
        return {'success': true, 'data': data};
      }
      return {'success': false, 'message': 'OAuth login failed'};
    } catch (e) {
      return {'success': false, 'message': _getErrorMessage(e)};
    }
  }

  // Get current user profile
  Future<Map<String, dynamic>?> getCurrentUser() async {
    try {
      final token = await getToken();
      if (token == null) return null;

      final response = await _apiClient.get('/users/profile');

      if (response.statusCode == 200) {
        return response.data;
      }
      return null;
    } catch (e) {
      // Error getting current user - handled silently
      return null;
    }
  }

  // Refresh user data from the server and update local storage
  // This ensures we have the latest user state including onboarding_completed status
  Future<bool> refreshUserData() async {
    try {
      if (kDebugMode) {
        print('🔄 AuthService: Refreshing user data from server...');
      }
      final token = await getToken();
      if (token == null) {
        if (kDebugMode) {
          print('⚠️ AuthService: No token found, cannot refresh user data');
        }
        return false;
      }

      final response = await _apiClient.get('/users/profile');

      if (response.statusCode == 200 && response.data != null) {
        final userData = response.data as Map<String, dynamic>;
        if (kDebugMode) {
          print('✅ AuthService: Got fresh user data from server');
          print(
            '🔍 AuthService: onboarding_completed from server: ${userData['onboarding_completed']}',
          );
        }

        // Update local storage with fresh data
        final userDataJson = jsonEncode(userData);
        await _secureStorage.write(_userDataKey, userDataJson);
        if (kDebugMode) {
          print('💾 AuthService: Updated local user data with server data');
        }

        return true;
      }
      if (kDebugMode) {
        print(
          '❌ AuthService: Failed to refresh user data, status: ${response.statusCode}',
        );
      }
      return false;
    } on UnauthorizedException catch (e) {
      if (kDebugMode) {
        print('🔒 AuthService: Session invalid (401): $e');
        print('🚪 AuthService: Clearing local session and forcing logout...');
      }
      await logout();
      return false;
    } on ForbiddenException catch (e) {
      if (kDebugMode) {
        print('⛔ AuthService: Session forbidden (403): $e');
        print('🚪 AuthService: Clearing local session and forcing logout...');
      }
      await logout();
      return false;
    } on NotFoundException catch (e) {
      // On a wiped DB, /users/profile can legitimately return 404 (user missing).
      if (kDebugMode) {
        print('🧹 AuthService: User not found (404): $e');
        print('🚪 AuthService: Clearing local session and forcing logout...');
      }
      await logout();
      return false;
    } catch (e) {
      if (kDebugMode) {
        print('💥 AuthService: Error refreshing user data: $e');
      }
      return false;
    }
  }

  // Check if user is logged in
  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }

  // Get stored token
  Future<String?> getToken() async {
    // Prefer the canonical key used by ApiClient; fall back to legacy key.
    final accessToken = await _secureStorage.read('access_token');
    if (accessToken != null && accessToken.isNotEmpty) return accessToken;
    return await _secureStorage.read(_tokenKey);
  }

  // Get stored refresh token
  Future<String?> getRefreshToken() async {
    return await _secureStorage.read(_refreshTokenKey);
  }

  // Get stored user data
  Future<Map<String, dynamic>?> getUserData() async {
    if (kDebugMode) {
      print('🔍 AuthService: Reading user data from secure storage...');
    }

    // First check if secure storage is working by testing a simple write/read
    try {
      await _secureStorage.write('test_key', 'test_value');
      final testRead = await _secureStorage.read('test_key');
      if (kDebugMode) {
        print(
          '🧪 AuthService: Secure storage test - wrote: test_value, read: $testRead',
        );
        if (testRead != 'test_value') {
          print(
            '⚠️ AuthService: Secure storage test failed - storage may not be working properly',
          );
        }
      }
    } catch (e) {
      if (kDebugMode) {
        print('❌ AuthService: Secure storage test failed with error: $e');
      }
    }

    final userData = await _secureStorage.read(_userDataKey);
    if (kDebugMode) {
      print('📦 AuthService: Raw user data from storage: $userData');
    }

    if (userData != null) {
      try {
        final decodedData = jsonDecode(userData);
        if (kDebugMode) {
          print('✅ AuthService: Decoded user data: $decodedData');
        }
        return decodedData;
      } catch (e) {
        if (kDebugMode) {
          print('❌ AuthService: Error decoding user data: $e');
        }
        return null;
      }
    }
    if (kDebugMode) {
      print('⚠️ AuthService: No user data found in storage');
    }
    return null;
  }

  // Refresh access token
  Future<bool> refreshAccessToken() async {
    try {
      final refreshToken = await getRefreshToken();
      if (refreshToken == null) return false;

      final response = await _apiClient.post(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      if (response.statusCode == 200) {
        final data = response.data;
        await _saveAuthData(data);
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  // Logout
  Future<void> logout() async {
    await _secureStorage.clearSession();
  }

  // Forgot Password - Request password reset email
  Future<Map<String, dynamic>> forgotPassword({required String email}) async {
    try {
      if (kDebugMode) {
        print('🔐 AuthService: Requesting password reset for $email');
      }

      final response = await _apiClient.post(
        '/auth/forgot-password',
        data: {'email': email},
      );

      if (response.statusCode == 200) {
        return {'success': true, 'message': response.data['message']};
      }
      return {'success': false, 'message': 'Failed to send reset email'};
    } catch (e) {
      if (kDebugMode) {
        print('❌ AuthService: Forgot password error: $e');
      }
      return {'success': false, 'message': _getErrorMessage(e)};
    }
  }

  // Reset Password - Set new password with token
  Future<Map<String, dynamic>> resetPassword({
    required String token,
    required String newPassword,
  }) async {
    try {
      if (kDebugMode) {
        print('🔐 AuthService: Resetting password with token');
      }

      final response = await _apiClient.post(
        '/auth/reset-password',
        data: {
          'token': token,
          'new_password': newPassword,
        },
      );

      if (response.statusCode == 200) {
        return {'success': true, 'message': response.data['message']};
      }
      return {'success': false, 'message': 'Failed to reset password'};
    } catch (e) {
      if (kDebugMode) {
        print('❌ AuthService: Reset password error: $e');
      }
      return {'success': false, 'message': _getErrorMessage(e)};
    }
  }

  // Save authentication data
  Future<void> _saveAuthData(Map<String, dynamic> data) async {
    if (kDebugMode) {
      print('💾 AuthService: Saving auth data...');
    }
    if (kDebugMode) {
      print('📋 AuthService: Full response data: $data');
    }

    if (data.containsKey('access_token')) {
      await _secureStorage.write(_tokenKey, data['access_token']);
      if (kDebugMode) {
        print('✅ AuthService: Access token saved to key: $_tokenKey');

        // Verify the token was saved correctly
        final savedToken = await _secureStorage.read(_tokenKey);
        print(
          '🔍 AuthService: Verification - saved token: ${savedToken != null ? "${savedToken.substring(0, 20)}..." : "null"}',
        );
      }
      // Also store under 'access_token' so ApiClient can find it
      await _secureStorage.write('access_token', data['access_token']);
      // Keep legacy 'auth_token' in sync as well
      await _secureStorage.write('auth_token', data['access_token']);
    }
    if (data.containsKey('refresh_token')) {
      await _secureStorage.write(_refreshTokenKey, data['refresh_token']);
      if (kDebugMode) {
        print('✅ AuthService: Refresh token saved');
      }
    }
    if (data.containsKey('user')) {
      final userDataJson = jsonEncode(data['user']);
      await _secureStorage.write(_userDataKey, userDataJson);
      if (kDebugMode) {
        print('✅ AuthService: User data saved: $userDataJson');
      }
    } else {
      if (kDebugMode) {
        print('⚠️ AuthService: No user data found in response');
      }
    }
  }

  // Extract error message from Exception
  String _getErrorMessage(dynamic e) {
    if (e is Exception) {
      final errorString = e.toString();

      // Handle custom API client exceptions
      if (errorString.contains('NetworkException:')) {
        return errorString.replaceFirst('NetworkException: ', '');
      }
      if (errorString.contains('BadRequestException:')) {
        return errorString.replaceFirst('BadRequestException: ', '');
      }
      if (errorString.contains('UnauthorizedException:')) {
        return errorString.replaceFirst('UnauthorizedException: ', '');
      }
      if (errorString.contains('ValidationException:')) {
        return errorString.replaceFirst('ValidationException: ', '');
      }
      if (errorString.contains('ServerException:')) {
        return errorString.replaceFirst('ServerException: ', '');
      }

      return errorString;
    }

    return 'An unexpected error occurred. Please try again.';
  }
}
