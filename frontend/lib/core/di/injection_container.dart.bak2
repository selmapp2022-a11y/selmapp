import 'package:get_it/get_it.dart';

import '../network/api_client.dart';
import '../storage/secure_storage.dart';
import '../services/auth_service.dart';
import '../services/oauth_service.dart';
import '../services/auth_state_notifier.dart';
import '../api/tts_api.dart';
import '../../features/onboarding/data/repositories/onboarding_repository.dart';
import '../../features/lessons/data/repositories/lessons_repository.dart';
import '../../features/progress/data/repositories/progress_repository.dart';
import '../../features/practice/data/repositories/practice_repository.dart';
import '../../features/practice/data/services/ai_practice_service.dart';
import '../../features/admin/data/repositories/admin_repository.dart';

final GetIt sl = GetIt.instance;

Future<void> init() async {
  // Core
  sl.registerLazySingleton<SecureStorage>(() => SecureStorage());
  sl.registerLazySingleton<ApiClient>(() => ApiClient(sl()));
  sl.registerLazySingleton<AuthStateNotifier>(() => AuthStateNotifier());
  
  // API Services
  sl.registerLazySingleton<TTSApi>(() => TTSApi(sl()));
  
  // Services
  sl.registerLazySingleton<AuthService>(() => AuthService(sl(), sl()));
  sl.registerLazySingleton<OAuthService>(() => OAuthService(sl(), sl()));
  sl.registerLazySingleton<AIPracticeService>(() => AIPracticeService(sl()));

  // Repositories
  sl.registerLazySingleton<OnboardingRepository>(
    () => OnboardingRepositoryImpl(sl(), sl()),
  );
  sl.registerLazySingleton<LessonsRepository>(
    () => LessonsRepositoryImpl(sl()),
  );
  sl.registerLazySingleton<ProgressRepository>(
    () => ProgressRepositoryImpl(sl()),
  );
  sl.registerLazySingleton<PracticeRepository>(
    () => PracticeRepositoryImpl(sl()),
  );
  sl.registerLazySingleton<AdminRepository>(
    () => AdminRepository(sl()),
  );

  // Use cases (if needed later)
  // sl.registerLazySingleton(() => GetUserProfile(sl()));

  // BLoCs (will be registered in main.dart or specific widgets)
  // sl.registerFactory(() => OnboardingBloc(sl()));
}
