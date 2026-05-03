import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// SELM Brand Theme — v1.0 (2026)
/// Source: SELM Brand Guidelines.
/// Primary Navy #183048, Accent Teal #2EC4B6 (sparingly), App BG #F8F8F8.
class AppTheme {
  // Brand Primary
  static const Color primaryColor = Color(0xFF183048); // SELM Navy
  static const Color primaryLightColor = Color(0xFF2A4A6B);
  static const Color primaryDarkColor = Color(0xFF0F1F30);

  // Brand Accent (use sparingly for highlights only)
  static const Color accentColor = Color(0xFF2EC4B6);
  static const Color secondaryColor = Color(0xFF2EC4B6);
  static const Color secondaryLightColor = Color(0xFF5BD4C8);
  static const Color secondaryDarkColor = Color(0xFF1FA89B);

  // Status
  static const Color errorColor = Color(0xFFD9534F);
  static const Color warningColor = Color(0xFFE0A800);
  static const Color successColor = Color(0xFF2EC4B6);

  // Neutrals (from brand guide)
  static const Color backgroundColor = Color(0xFFF8F8F8); // App BG
  static const Color surfaceColor = Color(0xFFFFFFFF);    // Card
  static const Color cardColor = Color(0xFFFFFFFF);
  static const Color mutedColor = Color(0xFFE7EBEF);

  // Text
  static const Color textPrimaryColor = Color(0xFF0B0F14);
  static const Color textSecondaryColor = Color(0xFF5B6670);
  static const Color textTertiaryColor = Color(0xFF9AA4AE);

  // Borders
  static const Color borderColor = Color(0xFFC0C6CC); // Divider
  static const Color dividerColor = Color(0xFFE7EBEF);

  // Gradients (subtle, navy-based)
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primaryColor, primaryLightColor],
  );

  static const LinearGradient secondaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [secondaryColor, secondaryLightColor],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [accentColor, secondaryLightColor],
  );

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      primaryColor: primaryColor,
      scaffoldBackgroundColor: backgroundColor,
      fontFamily: 'Inter',

      colorScheme: const ColorScheme.light(
        primary: primaryColor,
        primaryContainer: primaryLightColor,
        secondary: accentColor,
        secondaryContainer: secondaryLightColor,
        tertiary: accentColor,
        surface: surfaceColor,
        error: errorColor,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: textPrimaryColor,
        onError: Colors.white,
      ),

      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: textPrimaryColor,
          fontSize: 18,
          fontWeight: FontWeight.w600,
          fontFamily: 'Poppins',
        ),
        iconTheme: IconThemeData(color: textPrimaryColor),
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.dark,
        ),
      ),

      cardTheme: CardThemeData(
        color: cardColor,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        shadowColor: Colors.black.withValues(alpha: .06),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: dividerColor, width: 1),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryColor,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          textStyle: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            fontFamily: 'Poppins',
          ),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primaryColor,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primaryColor,
          side: const BorderSide(color: primaryColor),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceColor,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: borderColor),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: borderColor),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: primaryColor, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: errorColor),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        hintStyle: const TextStyle(color: textTertiaryColor),
      ),

      textTheme: const TextTheme(
        displayLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: textPrimaryColor, height: 1.2, fontFamily: 'Poppins'),
        displayMedium: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: textPrimaryColor, height: 1.2, fontFamily: 'Poppins'),
        displaySmall: TextStyle(fontSize: 24, fontWeight: FontWeight.w600, color: textPrimaryColor, height: 1.3, fontFamily: 'Poppins'),
        headlineLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w600, color: textPrimaryColor, height: 1.3, fontFamily: 'Poppins'),
        headlineMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: textPrimaryColor, height: 1.3, fontFamily: 'Poppins'),
        headlineSmall: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: textPrimaryColor, height: 1.4, fontFamily: 'Poppins'),
        titleLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: textPrimaryColor, height: 1.4, fontFamily: 'Poppins'),
        titleMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: textPrimaryColor, height: 1.4, fontFamily: 'Poppins'),
        titleSmall: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: textSecondaryColor, height: 1.4),
        bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.normal, color: textPrimaryColor, height: 1.5),
        bodyMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.normal, color: textPrimaryColor, height: 1.5),
        bodySmall: TextStyle(fontSize: 12, fontWeight: FontWeight.normal, color: textSecondaryColor, height: 1.5),
        labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: textPrimaryColor),
        labelMedium: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: textSecondaryColor),
        labelSmall: TextStyle(fontSize: 10, fontWeight: FontWeight.w500, color: textTertiaryColor),
      ),

      iconTheme: const IconThemeData(color: textSecondaryColor, size: 24),

      dividerTheme: const DividerThemeData(
        color: dividerColor,
        thickness: 1,
        space: 1,
      ),
    );
  }

  static ThemeData get darkTheme {
    return lightTheme.copyWith(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: primaryDarkColor,
      colorScheme: const ColorScheme.dark(
        primary: Colors.white,
        primaryContainer: primaryLightColor,
        secondary: accentColor,
        secondaryContainer: secondaryLightColor,
        tertiary: accentColor,
        surface: primaryColor,
        error: errorColor,
        onPrimary: primaryDarkColor,
        onSecondary: Colors.white,
        onSurface: Colors.white,
        onError: Colors.white,
      ),
    );
  }
}
