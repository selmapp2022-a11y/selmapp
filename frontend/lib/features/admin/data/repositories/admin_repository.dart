import 'package:flutter/foundation.dart';

import '/core/network/api_client.dart';
import '../models/admin_models.dart';

/// Repository for all admin panel API calls.
class AdminRepository {
  final ApiClient _apiClient;

  AdminRepository(this._apiClient);

  // ── Dashboard ─────────────────────────────────────────────────────

  Future<AdminDashboard> getDashboard() async {
    try {
      final response = await _apiClient.get('/admin/dashboard');
      return AdminDashboard.fromJson(response.data);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.getDashboard error: $e');
      rethrow;
    }
  }

  Future<SystemStats> getSystemStats() async {
    try {
      final response = await _apiClient.get('/admin/stats');
      return SystemStats.fromJson(response.data);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.getSystemStats error: $e');
      rethrow;
    }
  }

  // ── Users ─────────────────────────────────────────────────────────

  Future<({List<AdminUserListItem> users, int total})> getUsers({
    int page = 1,
    int perPage = 20,
    String? search,
    bool? isActive,
    bool? isPremium,
    String? level,
    String sortBy = 'created_at',
    String sortOrder = 'desc',
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'page': page,
        'per_page': perPage,
        'sort_by': sortBy,
        'sort_order': sortOrder,
      };
      if (search != null && search.isNotEmpty) queryParams['search'] = search;
      if (isActive != null) queryParams['is_active'] = isActive;
      if (isPremium != null) queryParams['is_premium'] = isPremium;
      if (level != null) queryParams['level'] = level;

      final response = await _apiClient.get(
        '/admin/users',
        queryParameters: queryParams,
      );
      final data = response.data as Map<String, dynamic>;
      final users = (data['users'] as List<dynamic>)
          .map((e) => AdminUserListItem.fromJson(e))
          .toList();
      return (users: users, total: data['total'] as int);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.getUsers error: $e');
      rethrow;
    }
  }

  Future<AdminUserDetail> getUserDetail(int userId) async {
    try {
      final response = await _apiClient.get('/admin/users/$userId');
      return AdminUserDetail.fromJson(response.data);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.getUserDetail error: $e');
      rethrow;
    }
  }

  Future<AdminUserDetail> updateUser(
    int userId,
    Map<String, dynamic> updates,
  ) async {
    try {
      final response = await _apiClient.put(
        '/admin/users/$userId',
        data: updates,
      );
      return AdminUserDetail.fromJson(response.data);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.updateUser error: $e');
      rethrow;
    }
  }

  Future<void> deactivateUser(int userId) async {
    try {
      await _apiClient.post('/admin/users/$userId/deactivate');
    } catch (e) {
      if (kDebugMode) print('AdminRepository.deactivateUser error: $e');
      rethrow;
    }
  }

  Future<void> activateUser(int userId) async {
    try {
      await _apiClient.post('/admin/users/$userId/activate');
    } catch (e) {
      if (kDebugMode) print('AdminRepository.activateUser error: $e');
      rethrow;
    }
  }

  // ── Activity Reports ──────────────────────────────────────────────

  Future<({List<UserActivityReport> activities, int total})>
      getActivityReports({
    int page = 1,
    int perPage = 20,
    String sortBy = 'last_login',
    String sortOrder = 'desc',
  }) async {
    try {
      final response = await _apiClient.get(
        '/admin/activity-reports',
        queryParameters: {
          'page': page,
          'per_page': perPage,
          'sort_by': sortBy,
          'sort_order': sortOrder,
        },
      );
      final data = response.data as Map<String, dynamic>;
      final activities = (data['activities'] as List<dynamic>)
          .map((e) => UserActivityReport.fromJson(e))
          .toList();
      return (activities: activities, total: data['total'] as int);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.getActivityReports error: $e');
      rethrow;
    }
  }

  // ── Reports ───────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSystemReport({
    String period = 'weekly',
  }) async {
    try {
      final response = await _apiClient.get(
        '/admin/reports',
        queryParameters: {'period': period},
      );
      return response.data as Map<String, dynamic>;
    } catch (e) {
      if (kDebugMode) print('AdminRepository.getSystemReport error: $e');
      rethrow;
    }
  }

  // ── Settings ──────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getAllSettings() async {
    try {
      final response = await _apiClient.get('/admin/settings/all');
      return response.data as Map<String, dynamic>;
    } catch (e) {
      if (kDebugMode) print('AdminRepository.getAllSettings error: $e');
      rethrow;
    }
  }

  Future<void> updatePaymentSettings(Map<String, dynamic> settings) async {
    try {
      await _apiClient.put('/admin/settings/payment', data: settings);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.updatePaymentSettings error: $e');
      rethrow;
    }
  }

  Future<void> updateContentSettings(Map<String, dynamic> settings) async {
    try {
      await _apiClient.put('/admin/settings/content', data: settings);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.updateContentSettings error: $e');
      rethrow;
    }
  }

  Future<void> updateFeatureSettings(Map<String, dynamic> settings) async {
    try {
      await _apiClient.put('/admin/settings/features', data: settings);
    } catch (e) {
      if (kDebugMode) print('AdminRepository.updateFeatureSettings error: $e');
      rethrow;
    }
  }
}
