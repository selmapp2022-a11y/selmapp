import 'dart:ui';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../theme/app_theme.dart';

/// Simplified 3-tab navigation bar: Home (Coach Center), Progress, Profile
class AppBottomNavBar extends StatelessWidget {
  final int currentIndex;
  final bool useDarkTheme;

  const AppBottomNavBar({
    super.key,
    required this.currentIndex,
    this.useDarkTheme = true,
  });

  /// Detects if the app is running in a mobile browser based on screen dimensions
  bool _isMobileWeb(BuildContext context) {
    if (!kIsWeb) return false;
    final screenWidth = MediaQuery.of(context).size.width;
    // Consider it mobile if width is less than tablet breakpoint (600px)
    return screenWidth < 600;
  }

  /// Calculate extra bottom padding for mobile web browsers
  /// Mobile browsers typically have a navigation bar between 50-80px
  double _getWebMobileBottomPadding(BuildContext context) {
    if (!_isMobileWeb(context)) {
      return kIsWeb ? 8.0 : 0.0; // Small extra padding for desktop web
    }
    
    // Get system safe area
    final viewPadding = MediaQuery.of(context).viewPadding.bottom;
    
    // If the system already provides safe area padding, respect it
    if (viewPadding > 0) {
      // System has safe area - add a smaller extra buffer for web
      return 8.0;
    }
    
    // No system safe area detected - we're likely on a mobile browser
    // Add substantial padding to clear the browser's bottom navigation
    return 24.0;
  }

  @override
  Widget build(BuildContext context) {
    if (useDarkTheme) {
      return _buildDarkNavBar(context);
    }
    return _buildLightNavBar(context);
  }

  Widget _buildDarkNavBar(BuildContext context) {
    // Calculate the padding needed for mobile web
    final webMobilePadding = _getWebMobileBottomPadding(context);
    
    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          // Use dynamic height based on safe area + content
          decoration: BoxDecoration(
            color: const Color(0xFF0F172A).withValues(alpha: 0.95),
            border: Border(
              top: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
            ),
          ),
          child: SafeArea(
            top: false,
            // Use minimum to ensure we have enough padding even when SafeArea doesn't provide it
            minimum: EdgeInsets.only(bottom: webMobilePadding),
            child: Padding(
              padding: const EdgeInsets.only(top: 8, bottom: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _buildNavItem(context, 0, Icons.auto_awesome_outlined, Icons.auto_awesome, 'Coach'),
                  _buildNavItem(context, 1, Icons.insights_outlined, Icons.insights, 'Progress'),
                  _buildNavItem(context, 2, Icons.person_outlined, Icons.person, 'Profile'),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(BuildContext context, int index, IconData icon, IconData activeIcon, String label) {
    final isSelected = currentIndex == index;
    
    return GestureDetector(
      onTap: () => _onTap(context, index),
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                gradient: isSelected ? AppTheme.primaryGradient : null,
                color: isSelected ? null : Colors.transparent,
                borderRadius: BorderRadius.circular(14),
                boxShadow: isSelected
                    ? [
                        BoxShadow(
                          color: AppTheme.primaryColor.withValues(alpha: 0.4),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ]
                    : null,
              ),
              child: Icon(
                isSelected ? activeIcon : icon,
                color: isSelected ? Colors.white : Colors.white.withValues(alpha: 0.6),
                size: 22,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? Colors.white : Colors.white.withValues(alpha: 0.6),
                fontSize: 10,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLightNavBar(BuildContext context) {
    // Calculate the padding needed for mobile web
    final webMobilePadding = _getWebMobileBottomPadding(context);
    
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        // Use minimum to ensure we have enough padding even when SafeArea doesn't provide it
        minimum: EdgeInsets.only(bottom: webMobilePadding),
        child: Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildLightNavItem(context, 0, Icons.auto_awesome_outlined, Icons.auto_awesome, 'Coach'),
              _buildLightNavItem(context, 1, Icons.insights_outlined, Icons.insights, 'Progress'),
              _buildLightNavItem(context, 2, Icons.person_outlined, Icons.person, 'Profile'),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLightNavItem(BuildContext context, int index, IconData icon, IconData activeIcon, String label) {
    final isSelected = currentIndex == index;
    
    return GestureDetector(
      onTap: () => _onTap(context, index),
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: isSelected ? AppTheme.primaryColor.withValues(alpha: 0.15) : Colors.transparent,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(
                isSelected ? activeIcon : icon,
                color: isSelected ? AppTheme.primaryColor : Colors.grey,
                size: 22,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? AppTheme.primaryColor : Colors.grey,
                fontSize: 10,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _onTap(BuildContext context, int index) {
    // If tapping on current tab, trigger refresh by re-navigating
    if (index == currentIndex) {
      // Force refresh by re-navigating with a unique timestamp
      _navigateToIndex(context, index, forceRefresh: true);
      return;
    }

    _navigateToIndex(context, index);
  }

  void _navigateToIndex(BuildContext context, int index, {bool forceRefresh = false}) {
    // Add timestamp to force widget rebuild when needed
    final refreshParam = forceRefresh ? '?refresh=${DateTime.now().millisecondsSinceEpoch}' : '';
    
    switch (index) {
      case 0:
        context.go('/home$refreshParam');
        break;
      case 1:
        context.go('/progress$refreshParam');
        break;
      case 2:
        context.go('/profile$refreshParam');
        break;
    }
  }
}
