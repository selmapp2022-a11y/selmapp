import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../config/app_environment.dart';
import '../storage/secure_storage.dart';
import '../services/auth_state_notifier.dart';

class ApiClient {
  late final Dio _dio;
  final SecureStorage _storage;
  final String _baseUrl;
  final AuthStateNotifier _authStateNotifier = AuthStateNotifier();

  ApiClient(this._storage) : _baseUrl = AppEnvironment.apiBaseUrlWithVersion {
    _dio = Dio(
      BaseOptions(
        baseUrl: _baseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 30),
        // sendTimeout removed from BaseOptions to avoid Web warning on GET requests
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    _setupInterceptors();
  }

  String get baseUrl => _baseUrl;

  void _setupInterceptors() {
    // Request interceptor to add authentication token
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Read token using unified strategy: prefer 'access_token', fallback to 'auth_token'
          String? token = await _storage.read('access_token');
          if (token == null) {
            if (kDebugMode) {
              print(
                '⚠️ FRONTEND AUTH: access_token not found, falling back to auth_token',
              );
            }
            token = await _storage.read('auth_token');
          }

          if (kDebugMode) {
            print(
              '🔑 FRONTEND AUTH: Token resolved: ${token != null ? "${token.substring(0, 20)}..." : "null"}',
            );
          }
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
            if (kDebugMode) {
              print('📤 FRONTEND AUTH: Added Authorization header');
            }
          } else {
            if (kDebugMode) {
              print(
                '⚠️ FRONTEND AUTH: No token found in storage (access_token/auth_token)',
              );
            }
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          final statusCode = error.response?.statusCode;
          final failedPath = error.requestOptions.path;
          
          // Handle 401 Unauthorized errors
          if (statusCode == 401) {
            // Avoid refresh loops: if the refresh endpoint itself is unauthorized,
            // just clear the session and notify.
            if (failedPath.endsWith('/auth/refresh')) {
              await _invalidateSession('Token refresh failed');
              handler.next(error);
              return;
            }

            final refreshToken = await _storage.read('refresh_token');
            if (refreshToken != null) {
              try {
                final response = await _dio.post(
                  '/auth/refresh',
                  data: {'refresh_token': refreshToken},
                );

                final newToken = response.data['access_token'];
                await _storage.write('access_token', newToken);
                await _storage.write('auth_token', newToken);

                // Retry the original request with new token
                final opts = error.requestOptions;
                opts.headers['Authorization'] = 'Bearer $newToken';
                final retryResponse = await _dio.fetch(opts);
                handler.resolve(retryResponse);
                return;
              } catch (e) {
                // Refresh failed, clear tokens and notify
                await _invalidateSession('Token refresh failed');
              }
            } else {
              // No refresh token available - treat as an invalid session.
              await _invalidateSession('No refresh token available');
            }
          }
          
          // Handle 404 on user profile endpoint (user deleted from DB)
          if (statusCode == 404 && failedPath.contains('/users/profile')) {
            if (kDebugMode) {
              print('🧹 ApiClient: User profile not found (404) - user may have been deleted');
            }
            await _invalidateSession('User not found in database');
          }
          
          // Handle 403 Forbidden on authenticated endpoints
          if (statusCode == 403 && !failedPath.startsWith('/auth/')) {
            if (kDebugMode) {
              print('⛔ ApiClient: Access forbidden (403) - session may be invalid');
            }
            await _invalidateSession('Access forbidden');
          }
          
          handler.next(error);
        },
      ),
    );

    // Logging interceptor for development
    _dio.interceptors.add(
      LogInterceptor(
        requestBody: true,
        responseBody: true,
        logPrint: (obj) {
          // Only log in debug mode
          // print(obj);
        },
      ),
    );
  }
  
  /// Clear the session and notify listeners that auth state has changed.
  Future<void> _invalidateSession(String reason) async {
    if (kDebugMode) {
      print('🚪 ApiClient: Invalidating session - $reason');
    }
    await _storage.clearSession();
    _authStateNotifier.notifySessionInvalidated(reason: reason);
  }

  // GET request
  Future<Response> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
  }) async {
    try {
      return await _retryRequest(() => _dio.get(
        path,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      ));
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  // POST request
  Future<Response> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
  }) async {
    try {
      if (kDebugMode) {
        print('🔗 Making POST request to: $baseUrl$path');
        // Only print data if it's small enough
        if (data.toString().length < 500) {
          print('📦 Request data: $data');
        }
      }
      
      options ??= Options();
      options.sendTimeout = const Duration(minutes: 2); // Set sendTimeout only for methods with body

      final response = await _retryRequest(() => _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      ));
      if (kDebugMode) {
        print('📨 Response status: ${response.statusCode}');
      }
      return response;
    } on DioException catch (e) {
      if (kDebugMode) {
        print('🚨 DioException: ${e.type} - ${e.message}');
      }
      throw _handleError(e);
    }
  }

  // Helper for retrying requests
  Future<Response> _retryRequest(Future<Response> Function() requestFn, {int maxRetries = 3}) async {
    int attempt = 0;
    while (true) {
      try {
        return await requestFn();
      } on DioException catch (e) {
        attempt++;
        // Retry on server errors (503) or timeouts
        bool shouldRetry = e.type == DioExceptionType.connectionTimeout || 
                           e.type == DioExceptionType.receiveTimeout ||
                           e.type == DioExceptionType.sendTimeout ||
                           (e.response?.statusCode == 503);
                           
        if (!shouldRetry || attempt >= maxRetries) {
          rethrow;
        }
        
        if (kDebugMode) {
          print('⚠️ Request failed (attempt $attempt), retrying in ${attempt * 1}s...');
        }
        await Future.delayed(Duration(seconds: attempt * 1));
      }
    }
  }

  // PUT request
  Future<Response> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      options ??= Options();
      options.sendTimeout = const Duration(minutes: 2);
      
      return await _retryRequest(() => _dio.put(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      ));
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  // DELETE request
  Future<Response> delete(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      return await _retryRequest(() => _dio.delete(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      ));
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  // PATCH request
  Future<Response> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) async {
    try {
      options ??= Options();
      options.sendTimeout = const Duration(minutes: 2);

      return await _retryRequest(() => _dio.patch(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
      ));
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  // Error handling
  Exception _handleError(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return NetworkException(
          'Connection timeout. Please check your internet connection.',
        );

      case DioExceptionType.badResponse:
        final statusCode = error.response?.statusCode;
        final message =
            error.response?.data?['detail'] ??
            error.response?.data?['message'] ??
            'Server error occurred';

        switch (statusCode) {
          case 400:
            return BadRequestException(message);
          case 401:
            return UnauthorizedException('Authentication failed');
          case 403:
            return ForbiddenException('Access denied');
          case 404:
            return NotFoundException('Resource not found');
          case 422:
            return ValidationException(message);
          case 500:
            return ServerException('Internal server error');
          default:
            return ServerException(message);
        }

      case DioExceptionType.cancel:
        return NetworkException('Request cancelled');

      case DioExceptionType.unknown:
      default:
        return NetworkException('Network error occurred. Please try again.');
    }
  }
}

// Custom exceptions
class NetworkException implements Exception {
  final String message;
  NetworkException(this.message);

  @override
  String toString() => 'NetworkException: $message';
}

class BadRequestException implements Exception {
  final String message;
  BadRequestException(this.message);

  @override
  String toString() => 'BadRequestException: $message';
}

class UnauthorizedException implements Exception {
  final String message;
  UnauthorizedException(this.message);

  @override
  String toString() => 'UnauthorizedException: $message';
}

class ForbiddenException implements Exception {
  final String message;
  ForbiddenException(this.message);

  @override
  String toString() => 'ForbiddenException: $message';
}

class NotFoundException implements Exception {
  final String message;
  NotFoundException(this.message);

  @override
  String toString() => 'NotFoundException: $message';
}

class ValidationException implements Exception {
  final String message;
  ValidationException(this.message);

  @override
  String toString() => 'ValidationException: $message';
}

class ServerException implements Exception {
  final String message;
  ServerException(this.message);

  @override
  String toString() => 'ServerException: $message';
}

// Assessment-specific exceptions
class AssessmentCancelledException implements Exception {
  final String message;
  AssessmentCancelledException(this.message);

  @override
  String toString() => 'AssessmentCancelledException: $message';
}

class AssessmentTimeoutException implements Exception {
  final String message;
  AssessmentTimeoutException(this.message);

  @override
  String toString() => 'AssessmentTimeoutException: $message';
}

class AssessmentGenerationException implements Exception {
  final String message;
  AssessmentGenerationException(this.message);

  @override
  String toString() => 'AssessmentGenerationException: $message';
}
