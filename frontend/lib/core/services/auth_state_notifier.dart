import 'dart:async';

import 'package:flutter/foundation.dart';

/// A singleton notifier that broadcasts authentication state changes.
/// 
/// This is used to force navigation refresh when the user's session becomes
/// invalid (e.g., after a database wipe, token expiration, or 401/404 errors).
/// 
/// Components like the router can listen to this stream and trigger a
/// re-evaluation of the current route when the auth state changes.
class AuthStateNotifier extends ChangeNotifier {
  static final AuthStateNotifier _instance = AuthStateNotifier._internal();
  
  factory AuthStateNotifier() => _instance;
  
  AuthStateNotifier._internal();
  
  final _controller = StreamController<AuthStateChange>.broadcast();
  
  /// Stream of auth state changes that components can listen to.
  Stream<AuthStateChange> get stream => _controller.stream;
  
  /// Notify listeners that the user has been forcefully logged out.
  /// 
  /// This is called when:
  /// - A 401 Unauthorized error occurs and token refresh fails
  /// - A 404 Not Found error occurs for user profile (user deleted from DB)
  /// - A 403 Forbidden error occurs
  void notifySessionInvalidated({String? reason}) {
    if (kDebugMode) {
      print('🔔 AuthStateNotifier: Session invalidated - $reason');
    }
    _controller.add(AuthStateChange(
      type: AuthStateChangeType.sessionInvalidated,
      reason: reason,
    ));
    notifyListeners();
  }
  
  /// Notify listeners that the user has logged out normally.
  void notifyLoggedOut() {
    if (kDebugMode) {
      print('🔔 AuthStateNotifier: User logged out');
    }
    _controller.add(AuthStateChange(
      type: AuthStateChangeType.loggedOut,
    ));
    notifyListeners();
  }
  
  /// Notify listeners that the user has logged in.
  void notifyLoggedIn() {
    if (kDebugMode) {
      print('🔔 AuthStateNotifier: User logged in');
    }
    _controller.add(AuthStateChange(
      type: AuthStateChangeType.loggedIn,
    ));
    notifyListeners();
  }
  
  @override
  void dispose() {
    _controller.close();
    super.dispose();
  }
}

enum AuthStateChangeType {
  loggedIn,
  loggedOut,
  sessionInvalidated,
}

class AuthStateChange {
  final AuthStateChangeType type;
  final String? reason;
  
  AuthStateChange({
    required this.type,
    this.reason,
  });
}




