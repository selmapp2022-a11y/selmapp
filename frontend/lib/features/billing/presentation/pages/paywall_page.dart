import 'package:flutter/material.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../../data/services/purchase_service.dart';

/// SELM Pro paywall. Shown when a free-tier user taps "Upgrade to Pro"
/// (from Settings or any locked feature surface) and also serves as the
/// review screenshot for App Store Connect's IAP review information.
///
/// Brand
/// -----
/// Navy + Teal lockup matching the v1.0 (2026) brand. We deliberately
/// don't bring AppTheme constants in here so the file is portable to
/// any future theme migration — colours are inlined as compile-time
/// constants.
class PaywallPage extends StatefulWidget {
  const PaywallPage({super.key, this.onClose, this.onPurchased});

  /// Called when the user dismisses the paywall via the close button.
  /// If null, the page just pops the route.
  final VoidCallback? onClose;

  /// Called once a purchase has been confirmed AND the backend has
  /// flipped the user to premium. Hosts typically use this to refresh
  /// user data and pop back to the previous screen.
  final VoidCallback? onPurchased;

  @override
  State<PaywallPage> createState() => _PaywallPageState();
}

class _PaywallPageState extends State<PaywallPage> {
  static const _navy = Color(0xFF183048);
  static const _teal = Color(0xFF5EEAD4);
  static const _navyDeep = Color(0xFF0F1F30);
  static const _ink = Color(0xFF1A202C);
  static const _inkMuted = Color(0xFF718096);

  bool _loadingProducts = true;
  bool _purchasing = false;
  String? _selectedId = PurchaseService.yearlyId; // yearly is "best value" default
  String? _errorText;

  @override
  void initState() {
    super.initState();
    _loadProducts();
  }

  Future<void> _loadProducts() async {
    try {
      await PurchaseService.instance.init();
    } catch (e) {
      _errorText =
          'Could not connect to the App Store. Please check your internet connection and try again.';
    }
    if (!mounted) return;
    setState(() => _loadingProducts = false);
  }

  Future<void> _onSubscribe() async {
    final id = _selectedId;
    if (id == null || _purchasing) return;
    setState(() {
      _purchasing = true;
      _errorText = null;
    });
    try {
      final ok = await PurchaseService.instance.purchase(id);
      if (!mounted) return;
      if (ok) {
        widget.onPurchased?.call();
        Navigator.of(context).maybePop();
      } else {
        setState(() {
          _errorText =
              'Purchase was not completed. If you were charged, your subscription will activate within a minute — pull down to refresh, or contact support@selmapp.com.';
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorText = 'Something went wrong. Please try again in a moment.';
      });
    } finally {
      if (mounted) setState(() => _purchasing = false);
    }
  }

  Future<void> _onRestore() async {
    setState(() {
      _purchasing = true;
      _errorText = null;
    });
    try {
      await PurchaseService.instance.restore();
    } catch (_) {
      // Errors here are non-fatal — if there's nothing to restore we
      // just show nothing.
    } finally {
      if (mounted) setState(() => _purchasing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final products = PurchaseService.instance.products;
    final monthly = _findProduct(products, PurchaseService.monthlyId);
    final yearly = _findProduct(products, PurchaseService.yearlyId);

    return Scaffold(
      backgroundColor: _navy,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SizedBox(height: 8),
                    _buildHeroCopy(),
                    const SizedBox(height: 28),
                    _buildBenefits(),
                    const SizedBox(height: 28),
                    if (_loadingProducts)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 32),
                        child: Center(
                          child: CircularProgressIndicator(color: _teal),
                        ),
                      )
                    else ...[
                      _buildPlanCard(
                        product: yearly,
                        productId: PurchaseService.yearlyId,
                        title: 'Yearly',
                        savingsBadge: 'Save 40%',
                        priceCadence: '/year',
                        priceFallback: 'Yearly subscription',
                      ),
                      const SizedBox(height: 12),
                      _buildPlanCard(
                        product: monthly,
                        productId: PurchaseService.monthlyId,
                        title: 'Monthly',
                        savingsBadge: null,
                        priceCadence: '/month',
                        priceFallback: 'Monthly subscription',
                      ),
                    ],
                    if (_errorText != null) ...[
                      const SizedBox(height: 16),
                      _buildErrorBox(_errorText!),
                    ],
                    const SizedBox(height: 24),
                    _buildCtaButton(),
                    const SizedBox(height: 14),
                    _buildRestoreLine(),
                    const SizedBox(height: 18),
                    _buildLegalFootnote(),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Sub-builders ────────────────────────────────────────────────────
  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.close, color: Colors.white),
            onPressed: () {
              if (widget.onClose != null) {
                widget.onClose!();
              } else {
                Navigator.of(context).maybePop();
              }
            },
          ),
          const Spacer(),
          TextButton(
            onPressed: _purchasing ? null : _onRestore,
            child: const Text(
              'Restore',
              style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeroCopy() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: _teal.withOpacity(0.15),
            borderRadius: BorderRadius.circular(20),
          ),
          child: const Text(
            'SELM PRO',
            style: TextStyle(
              color: _teal,
              fontWeight: FontWeight.w800,
              fontSize: 12,
              letterSpacing: 1.5,
            ),
          ),
        ),
        const SizedBox(height: 14),
        const Text(
          'Unlock every skill,\nevery level.',
          style: TextStyle(
            color: Colors.white,
            fontSize: 30,
            fontWeight: FontWeight.w800,
            height: 1.15,
          ),
        ),
        const SizedBox(height: 10),
        const Text(
          'Try Pro free for 7 days. Cancel anytime in your Apple ID settings — no charge if you cancel before the trial ends.',
          style: TextStyle(
            color: Colors.white70,
            fontSize: 15,
            height: 1.45,
          ),
        ),
      ],
    );
  }

  Widget _buildBenefits() {
    const items = <String>[
      'Unlimited AI Speaking conversations',
      'Real-time pronunciation scoring',
      'IELTS Writing & Speaking practice',
      'Adaptive listening at every CEFR level',
      'No ads, no daily limits',
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: items
          .map(
            (t) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 2),
                    child: Icon(Icons.check_circle, color: _teal, size: 20),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      t,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          )
          .toList(),
    );
  }

  Widget _buildPlanCard({
    required ProductDetails? product,
    required String productId,
    required String title,
    required String? savingsBadge,
    required String priceCadence,
    required String priceFallback,
  }) {
    final selected = _selectedId == productId;
    final price = product?.price ?? priceFallback;
    return GestureDetector(
      onTap: () => setState(() => _selectedId = productId),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
        decoration: BoxDecoration(
          color: selected ? _teal.withOpacity(0.12) : _navyDeep,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected ? _teal : Colors.white.withOpacity(0.12),
            width: selected ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 22,
              height: 22,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: selected ? _teal : Colors.transparent,
                border: Border.all(
                  color: selected ? _teal : Colors.white54,
                  width: 2,
                ),
              ),
              child: selected
                  ? const Icon(Icons.check, color: _navy, size: 14)
                  : null,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (savingsBadge != null) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: _teal,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            savingsBadge,
                            style: const TextStyle(
                              color: _navy,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text.rich(
                    TextSpan(
                      children: [
                        const TextSpan(
                          text: '7-day free trial, then ',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 13,
                          ),
                        ),
                        TextSpan(
                          text: '$price$priceCadence',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCtaButton() {
    final enabled = !_purchasing && !_loadingProducts && _selectedId != null;
    return SizedBox(
      width: double.infinity,
      height: 56,
      child: ElevatedButton(
        onPressed: enabled ? _onSubscribe : null,
        style: ElevatedButton.styleFrom(
          backgroundColor: _teal,
          foregroundColor: _navy,
          disabledBackgroundColor: Colors.white24,
          disabledForegroundColor: Colors.white60,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
          ),
        ),
        child: _purchasing
            ? const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  color: _navy,
                  strokeWidth: 2.5,
                ),
              )
            : const Text('Start 7-day free trial'),
      ),
    );
  }

    // Auto-renewal disclosure required by Apple guideline 3.1.2(c).
  // Apple wants the customer to know — right where they tap to buy — that the
  // subscription auto-renews and how/where to cancel.
  Widget _buildAutoRenewDisclaimer() {
    return const Padding(
      padding: EdgeInsets.only(top: 12, left: 8, right: 8),
      child: Text(
        'Subscriptions auto-renew at the price shown above until cancelled. Cancel anytime in Settings > Apple ID > Subscriptions, at least 24 hours before renewal.',
        textAlign: TextAlign.center,
        style: TextStyle(
          color: Colors.white70,
          fontSize: 12,
          height: 1.4,
        ),
      ),
    );
  }

  Widget _buildRestoreLine() {
    return Center(
      child: TextButton(
        onPressed: _purchasing ? null : _onRestore,
        child: const Text(
          'Already subscribed? Restore purchases',
          style: TextStyle(color: Colors.white70, fontSize: 13),
        ),
      ),
    );
  }

  Widget _buildErrorBox(String msg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.red.shade50,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.red.shade200),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 2),
            child: Icon(Icons.error_outline, color: Color(0xFFB91C1C), size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              msg,
              style: const TextStyle(
                color: Color(0xFF7F1D1D),
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLegalFootnote() {
    return const Text(
      'Subscriptions automatically renew unless turned off at least 24 hours before the end of the current period. Your Apple ID account will be charged at the price shown above. Manage or cancel in your device Settings → Apple ID → Subscriptions. By subscribing you agree to our Terms of Service and Privacy Policy.',
      style: TextStyle(color: Colors.white54, fontSize: 11, height: 1.5),
    );
  }

  ProductDetails? _findProduct(List<ProductDetails> products, String id) {
    for (final p in products) {
      if (p.id == id) return p;
    }
    return null;
  }
}
