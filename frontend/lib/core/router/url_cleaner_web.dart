import 'package:flutter/foundation.dart';
import 'package:web/web.dart' as web;

/// Web implementation for cleaning URL
void cleanUrl(String newUrl) {
  try {
    web.window.history.replaceState(null, '', newUrl);
    if (kDebugMode) {
      print('🧹 URL cleaned to: $newUrl');
    }
  } catch (e) {
    if (kDebugMode) {
      print('⚠️ Could not clean URL: $e');
    }
  }
}
