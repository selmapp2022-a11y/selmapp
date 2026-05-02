import '../config/app_environment.dart';

class AppConstants {
  // App Info
  static const String appName = 'Selm';
  // Coach / brand naming
  static const String coachName = appName;
  static const String coachDisplayName = 'Coach $coachName';
  static const String appVersion = '1.0.0';
  static const String appDescription = 'Your Personal English Learning Companion';
  
  // API Configuration
  static String get baseUrl => AppEnvironment.apiBaseUrl;
  static const String apiVersion = '/api/v1';
  
  // Storage Keys
  static const String userTokenKey = 'user_token';
  static const String userDataKey = 'user_data';
  static const String settingsKey = 'app_settings';
  
  // Animation Durations
  static const Duration shortAnimation = Duration(milliseconds: 200);
  static const Duration mediumAnimation = Duration(milliseconds: 400);
  static const Duration longAnimation = Duration(milliseconds: 600);
  
  // Spacing
  static const double paddingXS = 4.0;
  static const double paddingS = 8.0;
  static const double paddingM = 16.0;
  static const double paddingL = 24.0;
  static const double paddingXL = 32.0;
  
  // Border Radius
  static const double radiusS = 8.0;
  static const double radiusM = 12.0;
  static const double radiusL = 16.0;
  static const double radiusXL = 24.0;
  
  // CEFR Levels
  static const List<String> cefrLevels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
  
  // Level Colors
  static const Map<String, int> levelColors = {
    'A1': 0xFF4CAF50, // Green
    'A2': 0xFF8BC34A, // Light Green
    'B1': 0xFFFF9800, // Orange
    'B2': 0xFFFF5722, // Deep Orange
    'C1': 0xFF9C27B0, // Purple
    'C2': 0xFF673AB7, // Deep Purple
  };
  
  // Exercise Types
  static const List<String> exerciseTypes = [
    'Multiple Choice',
    'Fill in the Blanks',
    'Listening',
    'Speaking',
    'Reading',
    'Writing',
    'Translation',
    'Pronunciation'
  ];

  /// Normalizes legacy/internal brand mentions in user-visible strings.
  ///
  /// Example: backend might return "selmapp" in an error message; in the UI we
  /// want the user-facing brand "Selm".
  ///
  /// Note: This intentionally avoids replacing inside URLs/schemes like
  /// "selmapp.com" or "selmapp://".
  static String normalizeBrandingText(String input) {
    return input.replaceAllMapped(
      RegExp(r'(^|[^\w./:])selmapp([^\w./:]|$)', caseSensitive: false),
      (m) => '${m.group(1)}$appName${m.group(2)}',
    );
  }
} 