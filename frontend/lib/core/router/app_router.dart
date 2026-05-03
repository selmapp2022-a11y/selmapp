import 'dart:async';

import 'package:go_router/go_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

// Conditional web import for URL manipulation
import 'url_cleaner_stub.dart' if (dart.library.html) 'url_cleaner_web.dart' as url_cleaner;

import '../../features/home/presentation/pages/home_page.dart';
import '../../features/auth/presentation/pages/welcome_page.dart';
import '../../features/auth/presentation/pages/innovative_welcome_page.dart';
import '../../features/auth/presentation/pages/login_page.dart';
import '../../features/auth/presentation/pages/register_page.dart';
import '../../features/auth/presentation/pages/forgot_password_page.dart';
import '../../features/auth/presentation/pages/reset_password_page.dart';
import '../../features/profile/presentation/pages/profile_page.dart';
import '../../features/exercises/presentation/pages/exercises_page.dart';
import '../../features/progress/presentation/pages/progress_page.dart';
import '../../features/practice/presentation/pages/direct_skill_practice_page.dart';
import '../../features/onboarding/presentation/pages/onboarding_profile_page.dart';
import '../../features/onboarding/presentation/pages/onboarding_assessment_page.dart';
import '../../features/settings/presentation/pages/privacy_policy_page.dart';
import '../../features/settings/presentation/pages/terms_of_service_page.dart';
import '../../features/settings/presentation/pages/contact_support_page.dart';
import '../../features/admin/presentation/pages/admin_dashboard_page.dart';
import '../../features/admin/presentation/pages/admin_users_page.dart';
import '../../features/admin/presentation/pages/admin_reports_page.dart';
import '../../features/admin/presentation/pages/admin_settings_page.dart';
import '../di/injection_container.dart' as di;
import '../services/auth_service.dart';
import '../services/oauth_service.dart';
import '../services/auth_state_notifier.dart';

class AppRouter {
  // Cache to avoid repeated API calls within short time window
  static DateTime? _lastRefreshTime;
  static const _refreshInterval = Duration(seconds: 30);
  
  // Subscription to auth state changes
  static StreamSubscription<AuthStateChange>? _authStateSubscription;
  
  /// Initialize the router and listen to auth state changes.
  /// Call this once during app startup.
  static void initialize() {
    // Listen to auth state changes and refresh router when session is invalidated
    _authStateSubscription?.cancel();
    _authStateSubscription = AuthStateNotifier().stream.listen((change) {
      if (change.type == AuthStateChangeType.sessionInvalidated ||
          change.type == AuthStateChangeType.loggedOut) {
        if (kDebugMode) {
          print('🔄 AppRouter: Auth state changed (${change.type}), refreshing router...');
        }
        // Reset the refresh time to force a fresh check on next navigation
        _lastRefreshTime = null;
        // Trigger a router refresh to re-evaluate redirect logic
        router.refresh();
      }
    });
    
    if (kDebugMode) {
      print('✅ AppRouter: Initialized and listening to auth state changes');
    }
  }
  
  /// Dispose of resources when the app is shutting down.
  static void dispose() {
    _authStateSubscription?.cancel();
    _authStateSubscription = null;
  }
  
  static Future<String?> _handleRedirect(BuildContext context, GoRouterState state) async {
    // Handle OAuth2 redirects (web): backend redirects here with tokens or errors
    // NOTE: On Flutter web, the initial route can be influenced by router config.
    // `Uri.base` is the most reliable source of the real browser URL at startup.
    final qp = <String, String>{
      ...state.uri.queryParameters,
      if (kIsWeb) ...Uri.base.queryParameters,
    };
    
    // Handle OAuth error from backend redirect
    final oauthError = qp['oauth_error'];
    if (oauthError == 'true') {
      // OAuth failed; send to welcome
      return '/welcome';
    }
    
    // Handle OAuth success from backend redirect (backend sends tokens in URL)
    final oauthSuccess = qp['oauth_success'];
    final accessToken = qp['access_token'];
    final refreshToken = qp['refresh_token'];
    
    if (oauthSuccess == 'true' && accessToken != null && accessToken.isNotEmpty) {
      if (kDebugMode) {
        print('🔑 OAuth Success detected in URL');
        print('   Access token: ${accessToken.substring(0, 20)}...');
      }
      
      try {
        // Store the tokens received from backend
        final oauthService = di.sl<OAuthService>();
        await oauthService.storeTokensFromRedirect(
          accessToken: accessToken,
          refreshToken: refreshToken,
        );
        
        // Clean up the URL to remove tokens (security best practice)
        if (kIsWeb) {
          url_cleaner.cleanUrl('/#/home');
        }
        
        // Force a fresh profile refresh after OAuth login
        _lastRefreshTime = null;
        
        if (kDebugMode) {
          print('✅ OAuth tokens stored, redirecting to /home');
        }
        return '/home';
      } catch (e) {
        if (kDebugMode) {
          print('❌ OAuth token storage failed: $e');
        }
        return '/welcome';
      }
    }

    // Legacy: Handle direct OAuth2 code flow (if frontend handles code exchange)
    final oauthCode = qp['code'];
    final oauthState = qp['state'];
    
    if (oauthCode != null && oauthCode.isNotEmpty && oauthSuccess == null) {
      try {
        final oauthService = di.sl<OAuthService>();
        final ok = await oauthService.completeOAuthFromRedirect(
          code: oauthCode,
          state: oauthState,
        );

        if (ok) {
          _lastRefreshTime = null;
          return '/home';
        }

        return '/welcome';
      } catch (_) {
        return '/welcome';
      }
    }

    // Skip redirect for routes that must be accessible without authentication.
    // (E.g. the user should be able to read the privacy policy before creating an account.)
    final publicRoutes = <String>{
      '/welcome',
      '/welcome-classic',
      '/login',
      '/register',
      '/forgot-password',
      '/reset-password',
      '/privacy-policy',
      '/terms-of-service',
      '/contact-support',
    };
    if (publicRoutes.contains(state.matchedLocation)) {
      return null;
    }

    // TEMP screenshot bypass (build23 brand QA). Gated on secret token.
    if (qp['_preview'] == 'selm2026qa') {
      return null;
    }

    try {
      // Get auth service from dependency injection
      final authService = di.sl<AuthService>();

      // Check if user is logged in
      final isLoggedIn = await authService.isLoggedIn();
      if (!isLoggedIn) {
        return '/welcome';
      }

      // Refresh user data from server if needed (to get latest onboarding status)
      // Only refresh if we haven't done so recently to avoid excessive API calls
      final now = DateTime.now();
      if (_lastRefreshTime == null || 
          now.difference(_lastRefreshTime!) > _refreshInterval) {
        final refreshed = await authService.refreshUserData();
        if (refreshed) {
          _lastRefreshTime = now;
        } else {
          // If refresh failed because the session is invalid (e.g. DB wiped and
          // /users/profile returns 401/404), AuthService will clear the session.
          // In that case, force the user back to the welcome/login flow.
          final stillLoggedIn = await authService.isLoggedIn();
          if (!stillLoggedIn) {
            _lastRefreshTime = null;
            return '/welcome';
          }
          // Otherwise (temporary network/server issue), keep the cached session
          // and try refreshing again later.
        }
      }

      // Check user data for onboarding completion
      final userData = await authService.getUserData();
      if (userData != null) {
        // Accept both snake_case and camelCase for robustness
        final onboardingCompleted = (userData['onboarding_completed'] ??
                userData['onboardingCompleted'] ??
                false) == true;
        
        // Only redirect to onboarding from root path or home path
        // Allow users to access other routes (profile, etc.) even if onboarding not completed
        // This allows users who cancelled assessment to use the app and take assessment later
        if (!onboardingCompleted && 
            (state.matchedLocation == '/' || state.matchedLocation == '/home')) {
          return '/onboarding';
        }
      }

      // User is logged in
      // If they are at root destination, send to home
      if (state.matchedLocation == '/') return '/home';
      return null;
    } catch (e) {
      // On error, redirect to welcome
      return '/welcome';
    }
  }
  static final GoRouter router = GoRouter(
    initialLocation: '/home',
    redirect: _handleRedirect,
    routes: [
      // Welcome & Auth Routes
      GoRoute(
        path: '/welcome',
        name: 'welcome',
        // Skip the onboarding-style welcome screen and go straight to login,
        // matching the web experience on selmapp.com.
        builder: (context, state) => const LoginPage(),
      ),
      // Keep the classic welcome page accessible for fallback
      GoRoute(
        path: '/welcome-classic',
        name: 'welcome-classic',
        builder: (context, state) => const WelcomePage(),
      ),
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginPage(),
      ),
      GoRoute(
        path: '/register',
        name: 'register',
        builder: (context, state) => const RegisterPage(),
      ),
      GoRoute(
        path: '/forgot-password',
        name: 'forgot-password',
        builder: (context, state) => const ForgotPasswordPage(),
      ),
      GoRoute(
        path: '/reset-password',
        name: 'reset-password',
        builder: (context, state) {
          final token = state.uri.queryParameters['token'];
          return ResetPasswordPage(token: token);
        },
      ),
      GoRoute(
        path: '/onboarding',
        name: 'onboarding',
        builder: (context, state) => const OnboardingProfilePage(),
      ),
      GoRoute(
        path: '/onboarding/assessment',
        name: 'onboarding-assessment',
        builder: (context, state) => const OnboardingAssessmentPage(),
      ),
      
      // OAuth callback route for deep links (selmapp://oauth/callback?...)
      GoRoute(
        path: '/oauth/callback',
        name: 'oauth-callback',
        redirect: (context, state) async {
          // Handle OAuth tokens from deep link
          final qp = state.uri.queryParameters;
          final accessToken = qp['access_token'];
          final refreshToken = qp['refresh_token'];
          final oauthSuccess = qp['oauth_success'];
          
          if (oauthSuccess == 'true' && accessToken != null && accessToken.isNotEmpty) {
            if (kDebugMode) {
              print('🔑 OAuth callback deep link detected');
            }
            
            try {
              final oauthService = di.sl<OAuthService>();
              await oauthService.storeTokensFromRedirect(
                accessToken: accessToken,
                refreshToken: refreshToken,
              );
              
              // Force a fresh profile refresh after OAuth login
              _lastRefreshTime = null;
              
              if (kDebugMode) {
                print('✅ OAuth tokens stored from deep link, redirecting to /home');
              }
              return '/home';
            } catch (e) {
              if (kDebugMode) {
                print('❌ OAuth token storage from deep link failed: $e');
              }
              return '/welcome';
            }
          }
          
          // OAuth failed or invalid params
          return '/welcome';
        },
        builder: (context, state) => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      ),
      
      // Main App Routes
      GoRoute(
        path: '/home',
        name: 'home',
        builder: (context, state) => const HomePage(),
      ),
      GoRoute(
        path: '/lessons',
        name: 'lessons',
        // Redirect lessons to home (Coach Center)
        redirect: (context, state) => '/home', 
        builder: (context, state) => const HomePage(),
      ),
      GoRoute(
        path: '/exercises',
        name: 'exercises',
        builder: (context, state) => const ExercisesPage(),
      ),
      GoRoute(
        path: '/progress',
        name: 'progress',
        builder: (context, state) => const ProgressPage(),
      ),
      GoRoute(
        path: '/profile',
        name: 'profile',
        builder: (context, state) => const ProfilePage(),
      ),
      // Practice page - shows skill-specific content directly (no Training Zone)
      GoRoute(
        path: '/practice',
        name: 'practice',
        builder: (context, state) {
          // Get the type query parameter to show skill-specific content
          final skillType = state.uri.queryParameters['type'] ?? 'vocabulary';
          return DirectSkillPracticePage(skillType: skillType);
        },
      ),
      // Journey route redirects to home (Coach Center now includes learning path)
      GoRoute(
        path: '/journey',
        name: 'journey',
        redirect: (context, state) => '/home',
        builder: (context, state) => const HomePage(),
      ),
      // Privacy Policy page - accessible to all users
      GoRoute(
        path: '/privacy-policy',
        name: 'privacy-policy',
        builder: (context, state) => const PrivacyPolicyPage(),
      ),
      // Terms of Service page - accessible to all users
      GoRoute(
        path: '/terms-of-service',
        name: 'terms-of-service',
        builder: (context, state) => const TermsOfServicePage(),
      ),
      // Contact & Support page - accessible to all users
      GoRoute(
        path: '/contact-support',
        name: 'contact-support',
        builder: (context, state) => const ContactSupportPage(),
      ),
      // ── Admin Routes ───────────────────────────────────────
      // Admins login as normal users; admin guard is enforced by
      // checking `is_admin` in the user data stored locally. The
      // backend endpoints also enforce admin auth via JWT + role deps.
      GoRoute(
        path: '/admin',
        name: 'admin',
        redirect: (context, state) async {
          final authService = di.sl<AuthService>();
          final userData = await authService.getUserData();
          if (userData == null || userData['is_admin'] != true) {
            return '/home';
          }
          return null;
        },
        builder: (context, state) => const AdminDashboardPage(),
      ),
      GoRoute(
        path: '/admin/users',
        name: 'admin-users',
        redirect: (context, state) async {
          final authService = di.sl<AuthService>();
          final userData = await authService.getUserData();
          if (userData == null || userData['is_admin'] != true) {
            return '/home';
          }
          return null;
        },
        builder: (context, state) => const AdminUsersPage(),
      ),
      GoRoute(
        path: '/admin/reports',
        name: 'admin-reports',
        redirect: (context, state) async {
          final authService = di.sl<AuthService>();
          final userData = await authService.getUserData();
          if (userData == null || userData['is_admin'] != true) {
            return '/home';
          }
          return null;
        },
        builder: (context, state) => const AdminReportsPage(),
      ),
      GoRoute(
        path: '/admin/settings',
        name: 'admin-settings',
        redirect: (context, state) async {
          final authService = di.sl<AuthService>();
          final userData = await authService.getUserData();
          if (userData == null || userData['is_admin'] != true) {
            return '/home';
          }
          return null;
        },
        builder: (context, state) => const AdminSettingsPage(),
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.red,
            ),
            const SizedBox(height: 16),
            Text(
              'Page not found',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'The page you are looking for does not exist.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => context.go('/home'),
              child: const Text('Go to Coach Center'),
            ),
          ],
        ),
      ),
    ),
  );
}