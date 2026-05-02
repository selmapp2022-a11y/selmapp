import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';

import 'core/constants/app_constants.dart';
import 'core/di/injection_container.dart' as di;
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'features/onboarding/data/repositories/onboarding_repository.dart';
import 'firebase_options.dart';

void main() async {
  // Catch all errors in a zone for Crashlytics
  runZonedGuarded<Future<void>>(() async {
    WidgetsFlutterBinding.ensureInitialized();
    
    Object? bootstrapError;
    StackTrace? bootstrapStack;

    try {
      // Initialize Firebase
      //
      // On web, Firebase *requires* explicit options. On Android/iOS these can
      // come from the native config files, but providing options is safe.
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );

      // Initialize Crashlytics (not supported on web)
      if (!kIsWeb) {
        // Pass all uncaught "fatal" errors from the framework to Crashlytics
        FlutterError.onError = (errorDetails) {
          FirebaseCrashlytics.instance.recordFlutterFatalError(errorDetails);
        };

        // Pass all uncaught asynchronous errors that aren't handled by the Flutter framework to Crashlytics
        PlatformDispatcher.instance.onError = (error, stack) {
          FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
          return true;
        };
      }

      // Initialize dependency injection
      await di.init();

      // Initialize Hive for local storage
      await Hive.initFlutter();

      // Initialize router and auth state listener
      // This ensures the app redirects to login when session becomes invalid
      AppRouter.initialize();

      // System chrome APIs are not meaningful on web and can throw on some web engines.
      if (!kIsWeb) {
        // Set preferred orientations
        await SystemChrome.setPreferredOrientations([
          DeviceOrientation.portraitUp,
          DeviceOrientation.portraitDown,
        ]);

        // Set system UI overlay style
        SystemChrome.setSystemUIOverlayStyle(
          const SystemUiOverlayStyle(
            statusBarColor: Colors.transparent,
            statusBarIconBrightness: Brightness.dark,
            systemNavigationBarColor: Colors.white,
            systemNavigationBarIconBrightness: Brightness.dark,
          ),
        );
      }
    } catch (e, s) {
      bootstrapError = e;
      bootstrapStack = s;
    }

    if (bootstrapError != null) {
      if (kDebugMode) {
        debugPrint('💥 App bootstrap failed: $bootstrapError');
        if (bootstrapStack != null) {
          debugPrint('$bootstrapStack');
        }
      }

      // Show a visible error page instead of a blank white screen.
      runApp(
        StartupErrorApp(
          error: bootstrapError,
          stack: bootstrapStack,
        ),
      );

      // Best-effort reporting (Crashlytics is not supported on web).
      if (!kIsWeb) {
        try {
          FirebaseCrashlytics.instance.recordError(
            bootstrapError,
            bootstrapStack,
            fatal: true,
          );
        } catch (_) {
          // Ignore secondary failures during crash reporting.
        }
      }
      return;
    }

    runApp(const SelmApp());
  }, (error, stack) {
    // Catch errors that happen outside of the Flutter framework
    if (!kIsWeb) {
      try {
        FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      } catch (_) {
        // Ignore secondary failures.
      }
    } else {
      // On web, fall back to console logging.
      debugPrint('💥 Uncaught error (web): $error');
      debugPrint('$stack');
    }
  });
}

class StartupErrorApp extends StatelessWidget {
  final Object? error;
  final StackTrace? stack;

  const StartupErrorApp({
    super.key,
    required this.error,
    required this.stack,
  });

  @override
  Widget build(BuildContext context) {
    final errorText = error?.toString() ?? 'Unknown error';

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'App failed to start',
                    style: Theme.of(context).textTheme.headlineMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    errorText,
                    style: Theme.of(context).textTheme.bodyMedium,
                    textAlign: TextAlign.center,
                  ),
                  if (kDebugMode && stack != null) ...[
                    const SizedBox(height: 16),
                    const Text('Stack trace:'),
                    const SizedBox(height: 8),
                    SelectableText(
                      stack.toString(),
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class SelmApp extends StatelessWidget {
  const SelmApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiRepositoryProvider(
      providers: [
        RepositoryProvider<OnboardingRepository>(
          create: (context) => di.sl<OnboardingRepository>(),
        ),
      ],
      child: MaterialApp.router(
        title: AppConstants.appName,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.light,
        routerConfig: AppRouter.router,
        builder: (context, child) {
          if (!kIsWeb) {
            return child ?? const SizedBox.shrink();
          }

          return Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1200),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: child ?? const SizedBox.shrink(),
              ),
            ),
          );
        },
      ),
    );
  }
}
