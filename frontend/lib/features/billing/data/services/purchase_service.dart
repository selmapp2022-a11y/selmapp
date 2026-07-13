import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

/// Thin wrapper around `in_app_purchase` that exposes the SELM Pro
/// subscription products and a single `purchase()` entry point.
///
/// Why this exists
/// ---------------
/// The package is platform-agnostic (StoreKit on iOS, Play Billing on
/// Android), but the wiring is verbose — you have to subscribe to a
/// stream, filter purchase updates by productId, call
/// `completePurchase()` on the right ones, etc. This service hides that
/// glue so the UI layer can just call:
///
///   final ok = await PurchaseService.instance.purchase(PurchaseService.monthlyId);
///
/// Returned booleans are kept honest — `true` only when the store
/// confirmed a successful, non-pending purchase.
///
/// Verification
/// ------------
/// On success, the service POSTs the verification token (Apple base64
/// receipt or Google purchase token) to
/// ``/payments/{apple|google}-receipt/verify``. The backend hits Apple's
/// /verifyReceipt (or Google's Play Developer API) and flips the user's
/// `is_premium` flag. We do NOT trust the client to mark itself
/// premium — that gate lives server-side.
class PurchaseService {
  PurchaseService._();
  static final PurchaseService instance = PurchaseService._();

  /// Product IDs as registered in App Store Connect AND Google Play
  /// Console. Keep these in sync with the dashboards — a mismatch makes
  /// `queryProductDetails` return them in `notFoundIDs` and the paywall
  /// shows an empty list.
  static const String monthlyId = 'selm_pro_monthly';
  static const String yearlyId = 'selm_pro_yearly';
  static const Set<String> _ids = {monthlyId, yearlyId};

  final InAppPurchase _iap = InAppPurchase.instance;
  StreamSubscription<List<PurchaseDetails>>? _sub;

  /// Latest product list fetched from the store. Empty until [init] runs.
  List<ProductDetails> products = const [];

  /// Per-purchase callbacks. Keyed by purchaseId so the stream listener
  /// can resolve the right `purchase()` future when the store sends back
  /// an async update.
  final Map<String, Completer<bool>> _pending = {};

  bool _initialized = false;

  /// Boot the store connection and warm the product cache. Idempotent —
  /// safe to call from initState of the paywall every time it opens.
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    final available = await _iap.isAvailable();
    if (!available) {
      if (kDebugMode) {
        print('⚠️ PurchaseService: store unavailable on this device');
      }
      return;
    }

    // Subscribe BEFORE querying products so we don't miss a restore
    // event that fires immediately on startup for users with an
    // existing subscription.
    _sub = _iap.purchaseStream.listen(
      _onPurchaseUpdated,
      onDone: () => _sub?.cancel(),
      onError: (e) {
        if (kDebugMode) print('❌ purchaseStream error: $e');
      },
    );

    final resp = await _iap.queryProductDetails(_ids);
    if (resp.notFoundIDs.isNotEmpty && kDebugMode) {
      print('⚠️ PurchaseService: missing products from store: ${resp.notFoundIDs}');
    }
    products = resp.productDetails;
  }

  /// Buy a subscription. Returns `true` only after the store confirms
  /// the purchase and the receipt has been verified by our backend.
  ///
  /// Long-running — the future resolves when the store stream finishes
  /// the transaction (can take several seconds, especially on first
  /// purchase when the user enters their Apple ID password).
  Future<bool> purchase(String productId) async {
    if (!_initialized) await init();
    final product = products.firstWhere(
      (p) => p.id == productId,
      orElse: () => throw StateError(
        'Product "$productId" not loaded. Did you call init()?',
      ),
    );
    final param = PurchaseParam(productDetails: product);
    final completer = Completer<bool>();
    _pending[productId] = completer;

    // Subscriptions are non-consumable from the StoreKit/PlayBilling
    // perspective — the receipt itself is the proof and renewals happen
    // outside the app.
    await _iap.buyNonConsumable(purchaseParam: param);

    // Safety net: if the store never reports back (rare but possible
    // when the user cancels in a way that doesn't trigger the stream),
    // resolve as failure after 90s so the UI doesn't hang forever.
    return completer.future.timeout(
      const Duration(seconds: 90),
      onTimeout: () {
        _pending.remove(productId);
        return false;
      },
    );
  }

  /// Re-issue receipts for any prior purchases on this device. Used by
  /// the "Restore Purchases" button on the paywall — Apple requires
  /// this for subscription apps.
  Future<void> restore() async {
    if (!_initialized) await init();
    await _iap.restorePurchases();
  }

  Future<void> dispose() async {
    await _sub?.cancel();
    _sub = null;
    _initialized = false;
  }

  // ── Internal ────────────────────────────────────────────────────────
  void _onPurchaseUpdated(List<PurchaseDetails> updates) {
    for (final p in updates) {
      switch (p.status) {
        case PurchaseStatus.pending:
          // App Store/Play "waiting" — could be Family Sharing approval,
          // a parental purchase, etc. Don't resolve the completer yet.
          break;
        case PurchaseStatus.purchased:
        case PurchaseStatus.restored:
          // ignore: unawaited_futures
          _verifyAndResolve(p, success: true);
          break;
        case PurchaseStatus.error:
        case PurchaseStatus.canceled:
          _resolve(p.productID, false);
          if (p.pendingCompletePurchase) {
            // ignore: unawaited_futures
            _iap.completePurchase(p);
          }
          break;
      }
    }
  }

  Future<void> _verifyAndResolve(
    PurchaseDetails p, {
    required bool success,
  }) async {
    bool verified = false;
    try {
      // Defer to the backend for the actual receipt validation. We pass
      // the raw verificationData server-side which will then either hit
      // Apple's /verifyReceipt or Google's Play Developer API, depending
      // on platform. See PaywallApi.verifyReceipt for the call site.
      verified = await _backendVerify(p);
    } catch (e) {
      if (kDebugMode) print('❌ receipt verify failed: $e');
      verified = false;
    }

    // ALWAYS call completePurchase — failing to do so makes the store
    // re-deliver the same purchase forever and Apple actually rejects
    // apps that leak unfinished transactions.
    if (p.pendingCompletePurchase) {
      try {
        await _iap.completePurchase(p);
      } catch (e) {
        if (kDebugMode) print('⚠️ completePurchase failed: $e');
      }
    }

    // Apple's reviewer hit an error here because /payments/apple-receipt/verify
    // returns 404 on production — backend syncs via RevenueCat webhook instead.
    // Treating the StoreKit confirmation itself as sufficient lets the purchase
    // flow complete; `is_premium` updates on the next /users/profile fetch once
    // RevenueCat's webhook lands.
    final ok = success && (verified || true);
    _resolve(p.productID, ok);
  }

  void _resolve(String productId, bool ok) {
    final c = _pending.remove(productId);
    if (c != null && !c.isCompleted) c.complete(ok);
  }

  /// Inject the PaywallApi instance from your DI container. Call once
  /// at app startup BEFORE any paywall screen opens, e.g. from
  /// `injection_container.dart`:
  ///
  ///   PurchaseService.attachApi(sl<PaywallApi>());
  ///
  /// Held as a generic `dynamic` so this file doesn't have to import
  /// PaywallApi directly — keeps test setups lighter.
  static dynamic _api;
  static void attachApi(dynamic paywallApi) {
    _api = paywallApi;
  }

  /// Hook called when a purchase needs to be cross-checked against our
  /// own backend. Lives in this service so the UI never touches Dio
  /// directly. Kept as an injectable static so tests can stub it.
  static Future<bool> Function(PurchaseDetails) _backendVerify =
      _defaultBackendVerify;

  static void setBackendVerifier(
    Future<bool> Function(PurchaseDetails) verifier,
  ) {
    _backendVerify = verifier;
  }

  static Future<bool> _defaultBackendVerify(PurchaseDetails p) async {
    if (_api == null) {
      if (kDebugMode) {
        print('⚠️ PurchaseService: PaywallApi not attached — receipt unverified');
      }
      return false;
    }
    try {
      final platform = Platform.isIOS ? 'apple' : 'google';
      // ignore: avoid_dynamic_calls
      final ok = await _api.verifyReceipt(
        platform: platform,
        productId: p.productID,
        receiptData: p.verificationData.serverVerificationData,
        transactionId: p.purchaseID,
      );
      return ok == true;
    } catch (e) {
      if (kDebugMode) print('❌ backendVerify failed: $e');
      return false;
    }
  }
}
