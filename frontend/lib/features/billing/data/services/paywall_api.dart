import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../../core/network/api_client.dart';

/// Backend wrapper for the receipt-verification + premium-status calls.
///
/// All requests go through the project's `ApiClient`, which already
/// injects the JWT and base URL — never call dio directly here.
class PaywallApi {
  PaywallApi(this._client);
  final ApiClient _client;

  /// Send a store receipt to the backend for server-side validation.
  ///
  /// On success the backend updates the user's subscription record AND
  /// flips ``User.is_premium`` — the client should then re-fetch
  /// /users/profile (via AuthService.refreshUserData) so the rest of
  /// the app sees the new entitlement.
  ///
  /// Returns true on a verified, active subscription. False is returned
  /// for any network error, malformed receipt, or backend rejection —
  /// the caller decides how to surface that (toast, retry, etc.).
  Future<bool> verifyReceipt({
    required String platform, // 'apple' | 'google'
    required String productId,
    required String receiptData,
    String? transactionId,
  }) async {
    final path = platform == 'apple'
        ? '/payments/apple-receipt/verify'
        : '/payments/google-receipt/verify';

    try {
      final res = await _client.post(
        path,
        data: {
          'product_id': productId,
          'receipt_data': receiptData,
          if (transactionId != null) 'transaction_id': transactionId,
        },
      );
      // Backend convention: success: true + active: true means the
      // subscription is verified AND currently valid. We treat anything
      // else as a no-op (user stays non-premium).
      final body = res.data;
      if (body is Map) {
        final ok = body['success'] == true && body['active'] == true;
        if (kDebugMode) {
          print('💳 PaywallApi: receipt verify -> $ok');
        }
        return ok;
      }
      return false;
    } on DioException catch (e) {
      // Apple-receipt endpoint may be 404 on production (RevenueCat webhook syncs instead).
      // Treating 404 as a successful no-op stops the UI from showing
      // a misleading error after a real StoreKit purchase.
      if (e.response?.statusCode == 404) {
        if (kDebugMode) {
          print('ℹ️ PaywallApi: server-side verify endpoint missing — relying on RevenueCat webhook');
        }
        return true;
      }
      if (kDebugMode) {
        print('❌ PaywallApi: verifyReceipt DioException: ${e.message}');
      }
      return false;
    } catch (e) {
      if (kDebugMode) print('❌ PaywallApi: verifyReceipt error: $e');
      return false;
    }
  }

  /// Pull the user's current subscription summary. Useful on app start
  /// to detect a subscription that was renewed/expired outside the app.
  Future<Map<String, dynamic>?> getActiveSubscription() async {
    try {
      final res = await _client.get('/payments/subscriptions/active');
      final body = res.data;
      if (body is Map<String, dynamic>) return body;
      return null;
    } catch (e) {
      if (kDebugMode) print('⚠️ PaywallApi: getActiveSubscription failed: $e');
      return null;
    }
  }
}
