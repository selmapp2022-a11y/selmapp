import 'dart:async';

import 'package:bloc/bloc.dart';
import 'package:equatable/equatable.dart';
import 'package:flutter/foundation.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/services/auth_service.dart';
import '../../../onboarding/data/models/onboarding_models.dart';
import '../../../onboarding/data/repositories/onboarding_repository.dart';

// Events
abstract class OnboardingEvent extends Equatable {
  const OnboardingEvent();

  @override
  List<Object?> get props => [];
}

class StartOnboardingEvent extends OnboardingEvent {}

class RegisterUserEvent extends OnboardingEvent {
  final String name;
  final String email;
  final String password;

  const RegisterUserEvent({
    required this.name,
    required this.email,
    required this.password,
  });

  @override
  List<Object?> get props => [name, email, password];
}

class SelectCategoriesEvent extends OnboardingEvent {
  final List<LearningCategory> categories;

  const SelectCategoriesEvent(this.categories);

  @override
  List<Object?> get props => [categories];
}

class SelectLearningPaceEvent extends OnboardingEvent {
  final LearningPace pace;

  const SelectLearningPaceEvent(this.pace);

  @override
  List<Object?> get props => [pace];
}

class StartAssessmentEvent extends OnboardingEvent {}

class SubmitAssessmentAnswerEvent extends OnboardingEvent {
  final String questionId;
  final int selectedAnswerIndex;
  final int timeSpentSeconds;
  final String? textAnswer;

  const SubmitAssessmentAnswerEvent({
    required this.questionId,
    required this.selectedAnswerIndex,
    required this.timeSpentSeconds,
    this.textAnswer,
  });

  @override
  List<Object?> get props => [
    questionId,
    selectedAnswerIndex,
    timeSpentSeconds,
    textAnswer,
  ];
}

class CompleteAssessmentEvent extends OnboardingEvent {}

class GenerateLearningPathEvent extends OnboardingEvent {}

class CompleteLearningPathVisualizationEvent extends OnboardingEvent {}

class CompleteOnboardingEvent extends OnboardingEvent {}

class SkipAssessmentEvent extends OnboardingEvent {
  final CEFRLevel selectedLevel;

  const SkipAssessmentEvent(this.selectedLevel);

  @override
  List<Object?> get props => [selectedLevel];
}

class RetryOnboardingStepEvent extends OnboardingEvent {}

// New: cancel assessment and return to onboarding home
class CancelAssessmentEvent extends OnboardingEvent {}

// States
abstract class OnboardingState extends Equatable {
  const OnboardingState();

  @override
  List<Object?> get props => [];
}

class OnboardingInitialState extends OnboardingState {}

class OnboardingLoadingState extends OnboardingState {
  final String message;
  final int progress;
  final bool showProgress;

  const OnboardingLoadingState(
    this.message, {
    this.progress = 0,
    this.showProgress = false,
  });

  @override
  List<Object?> get props => [message, progress, showProgress];
}

class OnboardingErrorState extends OnboardingState {
  final String message;
  final String? errorCode;

  const OnboardingErrorState(this.message, {this.errorCode});

  @override
  List<Object?> get props => [message, errorCode];
}

// Step-specific states
class WelcomeState extends OnboardingState {}

class RegistrationState extends OnboardingState {}

class RegistrationSuccessState extends OnboardingState {
  final String userId;
  final String name;

  const RegistrationSuccessState({required this.userId, required this.name});

  @override
  List<Object?> get props => [userId, name];
}

class CategorySelectionState extends OnboardingState {
  final String userId;
  final String userName;
  final List<LearningCategory> selectedCategories;

  const CategorySelectionState({
    required this.userId,
    required this.userName,
    this.selectedCategories = const [],
  });

  @override
  List<Object?> get props => [userId, userName, selectedCategories];
}

class LearningPaceSelectionState extends OnboardingState {
  final String userId;
  final String userName;
  final List<LearningCategory> selectedCategories;
  final LearningPace? selectedPace;

  const LearningPaceSelectionState({
    required this.userId,
    required this.userName,
    required this.selectedCategories,
    this.selectedPace,
  });

  @override
  List<Object?> get props => [
    userId,
    userName,
    selectedCategories,
    selectedPace,
  ];
}

class AssessmentIntroState extends OnboardingState {
  final String userId;
  final String userName;
  final List<LearningCategory> selectedCategories;
  final LearningPace selectedPace;

  const AssessmentIntroState({
    required this.userId,
    required this.userName,
    required this.selectedCategories,
    required this.selectedPace,
  });

  @override
  List<Object?> get props => [
    userId,
    userName,
    selectedCategories,
    selectedPace,
  ];
}

class AssessmentInProgressState extends OnboardingState {
  final String userId;
  final List<AssessmentQuestion> questions;
  final int currentQuestionIndex;
  final List<AssessmentAnswer> answers;
  final bool isLoadingNextQuestion;

  const AssessmentInProgressState({
    required this.userId,
    required this.questions,
    required this.currentQuestionIndex,
    required this.answers,
    this.isLoadingNextQuestion = false,
  });

  AssessmentQuestion get currentQuestion => questions[currentQuestionIndex];
  bool get isLastQuestion => currentQuestionIndex >= questions.length - 1;
  double get progress => (currentQuestionIndex + 1) / questions.length;

  @override
  List<Object?> get props => [
    userId,
    questions,
    currentQuestionIndex,
    answers,
    isLoadingNextQuestion,
  ];
}

class AssessmentResultsState extends OnboardingState {
  final String userId;
  final String userName;
  final List<LearningCategory> selectedCategories;
  final LearningPace selectedPace;
  final AssessmentResult assessmentResult;

  const AssessmentResultsState({
    required this.userId,
    required this.userName,
    required this.selectedCategories,
    required this.selectedPace,
    required this.assessmentResult,
  });

  @override
  List<Object?> get props => [
    userId,
    userName,
    selectedCategories,
    selectedPace,
    assessmentResult,
  ];
}

class LearningPathGenerationState extends OnboardingState {
  final UserProfile userProfile;

  const LearningPathGenerationState(this.userProfile);

  @override
  List<Object?> get props => [userProfile];
}

class LearningPathVisualizationState extends OnboardingState {
  final UserProfile userProfile;
  final LearningPath learningPath;

  const LearningPathVisualizationState({
    required this.userProfile,
    required this.learningPath,
  });

  @override
  List<Object?> get props => [userProfile, learningPath];
}

class OnboardingCompletedNavigateHomeState extends OnboardingState {}

// State to navigate to home when assessment is cancelled
class AssessmentCancelledNavigateHomeState extends OnboardingState {}

class OnboardingCompleteState extends OnboardingState {
  final UserProfile userProfile;
  final LearningPath learningPath;

  const OnboardingCompleteState({
    required this.userProfile,
    required this.learningPath,
  });

  @override
  List<Object?> get props => [userProfile, learningPath];
}

// BLoC
class OnboardingBloc extends Bloc<OnboardingEvent, OnboardingState> {
  final OnboardingRepository _repository;
  final AuthService _authService;
  final ApiClient _apiClient;

  // Temporary data during onboarding
  String? _tempUserId;
  String? _tempUserName;
  String? _tempEmail;
  List<LearningCategory> _tempCategories = [];
  LearningPace? _tempPace;
  List<AssessmentAnswer> _assessmentAnswers = [];
  // Cached assessment result (e.g. restored after app restart) to avoid forcing retakes.
  AssessmentResult? _cachedAssessmentResult;

  OnboardingBloc(this._repository, this._authService, this._apiClient)
    : super(OnboardingInitialState()) {
    on<StartOnboardingEvent>(_onStartOnboarding);
    on<RegisterUserEvent>(_onRegisterUser);
    on<SelectCategoriesEvent>(_onSelectCategories);
    on<SelectLearningPaceEvent>(_onSelectLearningPace);
    on<StartAssessmentEvent>(_onStartAssessment);
    on<SubmitAssessmentAnswerEvent>(_onSubmitAssessmentAnswer);
    on<CompleteAssessmentEvent>(_onCompleteAssessment);
    on<SkipAssessmentEvent>(_onSkipAssessment);
    on<GenerateLearningPathEvent>(_onGenerateLearningPath);
    on<CompleteLearningPathVisualizationEvent>(
      _onCompleteLearningPathVisualization,
    );
    on<CompleteOnboardingEvent>(_onCompleteOnboarding);
    on<RetryOnboardingStepEvent>(_onRetryOnboardingStep);
    on<CancelAssessmentEvent>(_onCancelAssessment);
  }

  Future<void> _onStartOnboarding(
    StartOnboardingEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    if (kDebugMode) {
      print('🔄 OnboardingBloc: StartOnboardingEvent received');
    }

    // First, refresh user data from the server to get latest onboarding status
    // This is critical to prevent showing assessment to users who already completed it
    await _authService.refreshUserData();

    // Check if user is already authenticated
    final userData = await _authService.getUserData();
    if (kDebugMode) {
      print('🔍 OnboardingBloc: User data check - userData: $userData');
    }

    if (userData != null && userData['id'] != null) {
      // Check if user has already completed onboarding
      // Accept both snake_case and camelCase for robustness
      final onboardingCompleted = (userData['onboarding_completed'] ?? 
              userData['onboardingCompleted'] ?? 
              false) == true;
      if (kDebugMode) {
        print(
          '📋 OnboardingBloc: Onboarding completed status: $onboardingCompleted',
        );
      }

      if (onboardingCompleted) {
        if (kDebugMode) {
          print(
            '✅ OnboardingBloc: User has completed onboarding, navigating to home',
          );
        }
        // User has already completed onboarding, navigate to home
        emit(OnboardingCompletedNavigateHomeState());
        return;
      }

      if (kDebugMode) {
        print(
          '✅ OnboardingBloc: User authenticated but onboarding not completed, transitioning to CategorySelectionState',
        );
      }
      // User is already logged in but hasn't completed onboarding, continue with category selection
      _tempUserId = userData['id'].toString(); // Convert int to string
      _tempUserName = userData['full_name'] ?? userData['username'] ?? 'User';
      _tempEmail = userData['email'];

      // --- Resume logic (production-friendly) ---
      // 1) If a learning path already exists (local cache or backend), resume from it.
      try {
        final path = await _repository.loadLearningPath();
        if (path != null && path.modules.isNotEmpty) {
          final storedProfile = await _repository.getUserProfile(_tempUserId!);
          final profile =
              storedProfile ??
              UserProfile(
                userId: _tempUserId!,
                name: _tempUserName ?? 'Learner',
                email: _tempEmail ?? '',
                preferredCategories: path.categories,
                currentLevel: path.currentLevel,
                learningPace: path.pace,
                assessmentResults: const {},
                createdAt: DateTime.now(),
                onboardingCompleted: false,
              );

          _tempCategories = profile.preferredCategories;
          _tempPace = profile.learningPace;

          if (kDebugMode) {
            print(
              '🔄 OnboardingBloc: Resuming from existing learning path (${path.modules.length} modules)',
            );
          }

          emit(
            LearningPathVisualizationState(userProfile: profile, learningPath: path),
          );
          return;
        }
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ OnboardingBloc: Failed to resume from learning path: $e');
        }
      }

      // 2) Try restoring onboarding selections + assessment status from backend.
      // This prevents forcing users to re-take the assessment after app restart.
      try {
        // Fetch onboarding status (selected categories, daily commitment, etc.)
        List<LearningCategory> restoredCategories = [];
        LearningPace? restoredPace;

        try {
          final onboardingResp = await _apiClient.get('/personalization/onboarding/status/');
          if (onboardingResp.statusCode == 200 && onboardingResp.data is Map) {
            final onboardingMap = (onboardingResp.data as Map).cast<String, dynamic>();
            final rawCats = onboardingMap['selected_categories'];
            if (rawCats is List) {
              for (final c in rawCats) {
                final raw = c?.toString().trim().toLowerCase();
                if (raw == null || raw.isEmpty) continue;
                // Direct match (mobile ids like daily_life, food, travel...)
                LearningCategory? mapped = LearningCategory.values
                    .where((lc) => lc.id == raw)
                    .cast<LearningCategory?>()
                    .firstWhere((_) => true, orElse: () => null);
                // Backward compatibility: map backend enum-style categories to closest mobile ids.
                mapped ??= switch (raw) {
                  'general_english' => LearningCategory.dailyLife,
                  'business_english' => LearningCategory.business,
                  'travel_english' => LearningCategory.travel,
                  'academic_english' => LearningCategory.education,
                  'conversation_practice' => LearningCategory.entertainment,
                  _ => null,
                };
                if (mapped != null && !restoredCategories.contains(mapped)) {
                  restoredCategories.add(mapped);
                }
              }
            }

            final rawMinutes = onboardingMap['daily_study_commitment'];
            final minutes = rawMinutes is num ? rawMinutes.toInt() : int.tryParse('$rawMinutes');
            if (minutes != null && minutes > 0) {
              // Pick the closest pace by minutes
              restoredPace = LearningPace.values.reduce((a, b) {
                final da = (minutes - a.averageDailyMinutes).abs();
                final db = (minutes - b.averageDailyMinutes).abs();
                return da <= db ? a : b;
              });
            }
          }
        } catch (_) {
          // Ignore; not every user has an onboarding record yet
        }

        if (restoredCategories.isNotEmpty) {
          _tempCategories = restoredCategories;
        }
        if (restoredPace != null) {
          _tempPace = restoredPace;
        }

        // Fetch assessment results (server-persisted)
        try {
          final assessmentResp = await _apiClient.get('/users/assessment-results');
          if (assessmentResp.statusCode == 200 && assessmentResp.data is Map) {
            final map = (assessmentResp.data as Map).cast<String, dynamic>();
            final results = map['results'];
            if (results is Map && results.isNotEmpty) {
              final r = results.cast<String, dynamic>();
              final levelCode =
                  (r['determined_level'] ?? r['determinedLevel'] ?? 'B1').toString();
              final determined = CEFRLevel.values.firstWhere(
                (l) => l.code.toLowerCase() == levelCode.toLowerCase(),
                orElse: () => CEFRLevel.b1,
              );

              final rawSkillScores = (r['skill_scores'] ?? r['skillScores'] ?? {}) as Map?;
              final skillScores = <String, double>{};
              rawSkillScores?.forEach((k, v) {
                final parsed = v is num ? v.toDouble() : double.tryParse('$v');
                if (parsed != null && parsed.isFinite) {
                  // Backend typically returns 0-100 for skill breakdown; clamp defensively.
                  skillScores[k.toString()] = parsed.clamp(0.0, 100.0).toDouble();
                }
              });

              final rawOverall = r['overall_score'] ?? r['overallScore'] ?? 0.0;
              final overall = rawOverall is num ? rawOverall.toDouble() : double.tryParse('$rawOverall') ?? 0.0;

              final recs = (r['recommendations'] as List?)
                      ?.map((x) => x.toString().trim())
                      .where((x) => x.isNotEmpty)
                      .toList() ??
                  const <String>[];

              _cachedAssessmentResult = AssessmentResult(
                userId: _tempUserId!,
                answers: const [],
                determinedLevel: determined,
                skillScores: skillScores,
                overallScore: overall.clamp(0.0, 100.0).toDouble(),
                feedback: (r['feedback'] ?? '').toString().trim().isNotEmpty
                    ? (r['feedback'] ?? '').toString().trim()
                    : 'Your assessment results are ready.',
                recommendations: recs,
                completedAt: DateTime.now(),
              );

              if (kDebugMode) {
                print('🔄 OnboardingBloc: Restored assessment results from backend');
              }
            }
          }
        } catch (_) {
          // Ignore; user may not have any assessment yet
        }

        // Decide where to resume:
        if (_tempCategories.isNotEmpty && _tempPace != null) {
          if (_cachedAssessmentResult != null) {
            emit(
              AssessmentResultsState(
                userId: _tempUserId!,
                userName: _tempUserName ?? 'Learner',
                selectedCategories: _tempCategories,
                selectedPace: _tempPace ?? LearningPace.steady,
                assessmentResult: _cachedAssessmentResult!,
              ),
            );
            return;
          }

          emit(
            AssessmentIntroState(
              userId: _tempUserId!,
              userName: _tempUserName ?? 'Learner',
              selectedCategories: _tempCategories,
              selectedPace: _tempPace ?? LearningPace.steady,
            ),
          );
          return;
        }

        if (_tempCategories.isNotEmpty) {
          emit(
            LearningPaceSelectionState(
              userId: _tempUserId!,
              userName: _tempUserName ?? 'Learner',
              selectedCategories: _tempCategories,
              selectedPace: _tempPace,
            ),
          );
          return;
        }
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ OnboardingBloc: Backend resume attempt failed: $e');
        }
      }

      // Default: start from category selection.
      emit(
        CategorySelectionState(userId: _tempUserId!, userName: _tempUserName!),
      );
    } else {
      if (kDebugMode) {
        print('👤 OnboardingBloc: User not authenticated, showing WelcomeState');
      }
      // New user, show welcome screen
      emit(WelcomeState());
    }
  }

  Future<void> _onRegisterUser(
    RegisterUserEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    emit(const OnboardingLoadingState('Creating your account...'));

    try {
      final result = await _repository.registerUser(
        name: event.name,
        email: event.email,
        password: event.password,
      );

      if (result['success']) {
        _tempUserId = result['userId'].toString(); // Convert int to string
        _tempUserName = event.name;
        _tempEmail = event.email;

        emit(
          RegistrationSuccessState(
            userId: result['userId'].toString(), // Convert int to string
            name: event.name,
          ),
        );

        // Automatically move to category selection after a short delay
        await Future.delayed(const Duration(seconds: 1));
        emit(
          CategorySelectionState(
            userId: result['userId'].toString(), // Convert int to string
            userName: event.name,
          ),
        );
      } else {
        emit(
          OnboardingErrorState(
            result['message'] ?? 'Registration failed',
            errorCode: result['errorCode'],
          ),
        );
      }
    } catch (e) {
      emit(
        OnboardingErrorState(
          'Registration failed. Please check your internet connection and try again.',
        ),
      );
    }
  }

  Future<void> _onSelectCategories(
    SelectCategoriesEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    debugPrint(
      '🚀 BLoC: SelectCategoriesEvent received with categories: ${event.categories}',
    );
    _tempCategories = event.categories;

    // Best-effort: persist onboarding progress to backend so the app can resume after restart.
    // IMPORTANT: We do not send primary_category because backend enum may not include mobile ids.
    Future<void>(() async {
      try {
        await _apiClient.put(
          '/personalization/onboarding/step/',
          data: {
            'step': 'category_selection',
            'data': {
              'selected_categories': _tempCategories.map((c) => c.id).toList(),
              'category_priorities': {
                for (int i = 0; i < _tempCategories.length; i++)
                  _tempCategories[i].id: i + 1,
              },
            },
          },
        );
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ Onboarding step sync (categories) failed: $e');
        }
      }
    });

    // Move forward to learning pace selection after categories are chosen
    final nextState = LearningPaceSelectionState(
      userId: _tempUserId!,
      userName: _tempUserName!,
      selectedCategories: _tempCategories,
      selectedPace: _tempPace,
    );
    if (kDebugMode) {
      print('📤 BLoC: Emitting LearningPaceSelectionState: $nextState');
    }
    emit(nextState);
  }

  Future<void> _onSelectLearningPace(
    SelectLearningPaceEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    if (kDebugMode) {
      print('🚀 BLoC: SelectLearningPaceEvent received with pace: ${event.pace}');
      print('📍 BLoC: Previous _tempPace: $_tempPace');
    }

    _tempPace = event.pace;
    if (kDebugMode) {
      print('✅ BLoC: _tempPace updated to: $_tempPace');
    }

    final newState = LearningPaceSelectionState(
      userId: _tempUserId!,
      userName: _tempUserName!,
      selectedCategories: _tempCategories,
      selectedPace: event.pace,
    );

    if (kDebugMode) {
      print('📤 BLoC: Emitting LearningPaceSelectionState: $newState');
    }
    emit(newState);
    if (kDebugMode) {
      print('✅ BLoC: LearningPaceSelectionState emitted');
    }

    // Best-effort: persist daily commitment to backend onboarding record for resume + AI.
    Future<void>(() async {
      try {
        await _apiClient.put(
          '/personalization/onboarding/step/',
          data: {
            'step': 'goals_setting',
            'data': {
              'daily_study_commitment': event.pace.averageDailyMinutes,
              'target_timeline': 'flexible',
            },
          },
        );
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ Onboarding step sync (pace) failed: $e');
        }
      }
    });
  }

  Future<void> _onStartAssessment(
    StartAssessmentEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    if (kDebugMode) {
      print('🚀 BLoC: StartAssessmentEvent received');
      print('📍 BLoC: Current state: ${state.runtimeType}');
      print('🔍 BLoC: Temp user ID: $_tempUserId');
      print('🔍 BLoC: Temp user name: $_tempUserName');
      print('🔍 BLoC: Temp categories: $_tempCategories');
      print('🔍 BLoC: Temp pace: $_tempPace');
    }

    // Check current state to determine the flow
    if (state is LearningPaceSelectionState) {
      if (kDebugMode) {
        print(
          '🎯 BLoC: Coming from LearningPaceSelectionState - moving to AssessmentIntroState',
        );
      }

      // Validate temp data before emitting
      if (_tempUserId == null || _tempUserName == null || _tempPace == null) {
        if (kDebugMode) {
          print('❌ BLoC: Missing temp data - cannot proceed');
          print('🔍 BLoC: _tempUserId: $_tempUserId');
          print('🔍 BLoC: _tempUserName: $_tempUserName');
          print('🔍 BLoC: _tempPace: $_tempPace');
          print('🔍 BLoC: _tempCategories: $_tempCategories');
        }
        return;
      }

      // Coming from learning pace screen - move to assessment intro
      final newState = AssessmentIntroState(
        userId: _tempUserId!,
        userName: _tempUserName!,
        selectedCategories: _tempCategories,
        selectedPace: _tempPace!,
      );
      if (kDebugMode) {
        print('📤 BLoC: Emitting AssessmentIntroState: $newState');
      }
      emit(newState);
      if (kDebugMode) {
        print('✅ BLoC: AssessmentIntroState emitted');
      }
    } else if (state is AssessmentIntroState) {
      if (kDebugMode) {
        print('🎯 BLoC: Coming from AssessmentIntroState - starting assessment');
      }
      // If we already have an assessment result (e.g., restored after app restart),
      // skip re-generating questions and continue to results.
      if (_cachedAssessmentResult != null) {
        emit(
          AssessmentResultsState(
            userId: _tempUserId!,
            userName: _tempUserName ?? 'Learner',
            selectedCategories: _tempCategories,
            selectedPace: _tempPace ?? LearningPace.steady,
            assessmentResult: _cachedAssessmentResult!,
          ),
        );
        return;
      }

      // Coming from assessment intro screen - start the actual assessment
      emit(
        const OnboardingLoadingState(
          'Preparing your personalized assessment...',
          progress: 0,
          showProgress: true,
        ),
      );

      try {
        if (kDebugMode) {
          print('📚 BLoC: Loading assessment questions...');
        }
        
        // Set up progress callback to update UI during AI generation
        _repository.setAssessmentProgressCallback((progress, message) {
          // Only emit if we're still in loading state
          if (state is OnboardingLoadingState) {
            emit(OnboardingLoadingState(
              message,
              progress: progress,
              showProgress: true,
            ));
          }
        });
        
        final questions = await _repository.getAssessmentQuestions(
          userId: _tempUserId!,
          categories: _tempCategories,
        );
        
        // Clear the callback
        _repository.setAssessmentProgressCallback(null);

        if (kDebugMode) {
          debugPrint('✅ BLoC: Questions loaded: ${questions.length} questions');
        }
        _assessmentAnswers = [];

        if (kDebugMode) {
          print('🚀 BLoC: Emitting AssessmentInProgressState');
        }
        emit(
          AssessmentInProgressState(
            userId: _tempUserId!,
            questions: questions,
            currentQuestionIndex: 0,
            answers: [],
          ),
        );
        if (kDebugMode) {
          print('✅ BLoC: AssessmentInProgressState emitted');
        }
      } on AssessmentCancelledException {
        if (kDebugMode) {
          print('ℹ️ BLoC: Assessment was cancelled');
        }
        _repository.setAssessmentProgressCallback(null);
        // User cancelled - go back to intro state
        emit(AssessmentIntroState(
          userId: _tempUserId!,
          userName: _tempUserName!,
          selectedCategories: _tempCategories,
          selectedPace: _tempPace!,
        ));
      } on AssessmentTimeoutException catch (e) {
        if (kDebugMode) {
          print('⏱️ BLoC: Assessment timed out: $e');
        }
        _repository.setAssessmentProgressCallback(null);
        emit(OnboardingErrorState(
          e.message,
          errorCode: 'assessment_timeout',
        ));
      } on AssessmentGenerationException catch (e) {
        if (kDebugMode) {
          print('❌ BLoC: Assessment generation failed: $e');
        }
        _repository.setAssessmentProgressCallback(null);
        emit(OnboardingErrorState(
          e.message,
          errorCode: 'assessment_generation_failed',
        ));
      } on NetworkException catch (e) {
        if (kDebugMode) {
          print('🌐 BLoC: Network error: $e');
        }
        _repository.setAssessmentProgressCallback(null);
        emit(OnboardingErrorState(
          e.message,
          errorCode: 'network_error',
        ));
      } catch (e) {
        if (kDebugMode) {
          print('❌ BLoC: Error loading questions: $e');
        }
        _repository.setAssessmentProgressCallback(null);
        emit(
          const OnboardingErrorState(
            'Failed to load assessment questions. Please try again.',
          ),
        );
      }
    }
  }

  Future<void> _onSubmitAssessmentAnswer(
    SubmitAssessmentAnswerEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    final currentState = state as AssessmentInProgressState;

    // Add answer to the list
    final isFillInBlank =
        currentState.currentQuestion.questionType.toLowerCase() ==
        'fill_in_blank';
    final bool computedCorrect = isFillInBlank
        ? (event.textAnswer != null &&
              event.textAnswer!.trim().toLowerCase() ==
                  (currentState.currentQuestion.correctAnswerText ?? '')
                      .trim()
                      .toLowerCase())
        : event.selectedAnswerIndex ==
              currentState.currentQuestion.correctAnswerIndex;

    final answer = AssessmentAnswer(
      questionId: event.questionId,
      selectedAnswerIndex: event.selectedAnswerIndex,
      isCorrect: computedCorrect,
      timeSpentSeconds: event.timeSpentSeconds,
      textAnswer: event.textAnswer,
    );

    _assessmentAnswers.add(answer);

    if (currentState.isLastQuestion) {
      // Assessment complete, show loading for results
      emit(const OnboardingLoadingState('Analyzing your results...'));
      add(CompleteAssessmentEvent());
    } else {
      // Move to next question with loading state
      emit(currentState.copyWith(isLoadingNextQuestion: true));

      await Future.delayed(const Duration(milliseconds: 800));

      emit(
        AssessmentInProgressState(
          userId: currentState.userId,
          questions: currentState.questions,
          currentQuestionIndex: currentState.currentQuestionIndex + 1,
          answers: _assessmentAnswers,
        ),
      );
    }
  }

  Future<void> _onCompleteAssessment(
    CompleteAssessmentEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    try {
      final assessmentResult = await _repository.submitAssessmentResults(
        userId: _tempUserId!,
        answers: _assessmentAnswers,
      );

      // Trigger background content pre-generation based on assessed level
      // This ensures practice content is ready when user navigates there
      _triggerContentPreGeneration(assessmentResult.determinedLevel.code);

      emit(
        AssessmentResultsState(
          userId: _tempUserId!,
          userName: _tempUserName ?? 'Learner',
          selectedCategories: _tempCategories,
          selectedPace: _tempPace ?? LearningPace.steady,
          assessmentResult: assessmentResult,
        ),
      );
    } catch (e) {
      emit(
        const OnboardingErrorState(
          'Failed to process assessment results. Please try again.',
        ),
      );
    }
  }

  /// Trigger background content generation after assessment completes.
  /// This runs asynchronously so user doesn't wait.
  void _triggerContentPreGeneration(String level) {
    // Fire and forget - don't block the UI
    _apiClient.post(
      '/practice-content/trigger-post-assessment',
      queryParameters: {'determined_level': level},
    ).then((_) {
      if (kDebugMode) {
        print('✅ Triggered content pre-generation for level: $level');
      }
    }).catchError((e) {
      if (kDebugMode) {
        print('⚠️ Failed to trigger content pre-generation: $e');
      }
    });
  }

  Future<void> _onCancelAssessment(
    CancelAssessmentEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    // Cancel any in-flight polling and reset in-memory assessment state
    _repository.cancelAssessmentPolling();
    _assessmentAnswers = [];

    // Navigate user to home - they can take assessment later from profile
    emit(AssessmentCancelledNavigateHomeState());
  }

  Future<void> _onSkipAssessment(
    SkipAssessmentEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    // Create user profile with the selected level
    final userProfile = UserProfile(
      userId: _tempUserId!,
      name: _tempUserName!,
      email: _tempEmail!,
      preferredCategories: _tempCategories,
      currentLevel: event.selectedLevel,
      learningPace: _tempPace!,
      assessmentResults: {
        'skipped': true,
        'selected_level': event.selectedLevel.code,
        'feedback':
            'Assessment skipped. Level set to ${event.selectedLevel.name}.',
      },
      createdAt: DateTime.now(),
      onboardingCompleted: false,
    );

    emit(LearningPathGenerationState(userProfile));
  }

  Future<void> _onGenerateLearningPath(
    GenerateLearningPathEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    if (kDebugMode) {
      print("✅ BLOC: _onGenerateLearningPath handler started.");
    }

    late final UserProfile userProfile;
    if (state is LearningPathGenerationState) {
      // Coming from “skip assessment”
      userProfile = (state as LearningPathGenerationState).userProfile;
    } else if (state is AssessmentResultsState) {
      final current = state as AssessmentResultsState;
      userProfile = UserProfile(
        userId: _tempUserId!,
        name: _tempUserName!,
        email: _tempEmail!,
        preferredCategories: _tempCategories,
        currentLevel: current.assessmentResult.determinedLevel,
        learningPace: _tempPace!,
        assessmentResults: current.assessmentResult.toJson(),
        createdAt: DateTime.now(),
        onboardingCompleted: false,
      );
    } else {
      emit(
        const OnboardingErrorState(
          'Invalid state for learning-path generation',
        ),
      );
      return;
    }
    emit(
      const OnboardingLoadingState(
        'Creating your personalized learning journey...',
      ),
    );

    try {
      final learningPath = await _repository.generateLearningPath(userProfile);

      // Save the learning path locally
      await _repository.saveLearningPath(learningPath);

      emit(
        LearningPathVisualizationState(
          userProfile: userProfile,
          learningPath: learningPath,
        ),
      );
    } catch (e) {
      if (kDebugMode) {
        print('💥 BLOC: Generate path failed: $e');
      }
      emit(
        const OnboardingErrorState(
          'Failed to create your learning path. Please try again.',
        ),
      );
    }
  }

  Future<void> _onCompleteLearningPathVisualization(
    CompleteLearningPathVisualizationEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    final currentState = state as LearningPathVisualizationState;

    if (kDebugMode) {
      print('🎯 OnboardingBloc: Completing onboarding...');
    }
    // Provide immediate UI feedback while we persist state.
    emit(const OnboardingLoadingState('Finalizing your setup...'));
    
    // Complete onboarding
    final completedProfile = currentState.userProfile.copyWith(
      onboardingCompleted: true,
    );
    
    // Save user profile with onboarding_completed=true to backend (best-effort)
    try {
      await _repository.updateUserProfile(completedProfile);
      if (kDebugMode) {
        print(
          '✅ OnboardingBloc: User profile updated with onboarding_completed=true',
        );
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ OnboardingBloc: Failed to update user profile (non-fatal): $e');
      }
    }

    // Save learning path for persistence (best-effort)
    try {
      await _repository.saveLearningPath(currentState.learningPath);
      if (kDebugMode) {
        print('✅ OnboardingBloc: Learning path saved');
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ OnboardingBloc: Failed to save learning path (non-fatal): $e');
      }
    }
    
    // Refresh user data from backend to ensure consistency (best-effort)
    try {
      await _authService.refreshUserData();
      if (kDebugMode) {
        print('✅ OnboardingBloc: User data refreshed from backend');
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ OnboardingBloc: refreshUserData failed (non-fatal): $e');
      }
    }

    emit(
      OnboardingCompleteState(
        userProfile: completedProfile,
        learningPath: currentState.learningPath,
      ),
    );
  }

  Future<void> _onCompleteOnboarding(
    CompleteOnboardingEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    // This will be handled by the parent navigator to move to main app
  }

  Future<void> _onRetryOnboardingStep(
    RetryOnboardingStepEvent event,
    Emitter<OnboardingState> emit,
  ) async {
    // Return to appropriate state based on where the error occurred
    if (_tempUserId == null) {
      emit(RegistrationState());
    } else if (_tempCategories.isEmpty) {
      emit(
        CategorySelectionState(userId: _tempUserId!, userName: _tempUserName!),
      );
    } else if (_tempPace == null) {
      emit(
        LearningPaceSelectionState(
          userId: _tempUserId!,
          userName: _tempUserName!,
          selectedCategories: _tempCategories,
        ),
      );
    } else {
      emit(
        AssessmentIntroState(
          userId: _tempUserId!,
          userName: _tempUserName!,
          selectedCategories: _tempCategories,
          selectedPace: _tempPace!,
        ),
      );
    }
  }
}

// Extension for copyWith on AssessmentInProgressState
extension AssessmentInProgressStateCopyWith on AssessmentInProgressState {
  AssessmentInProgressState copyWith({
    String? userId,
    List<AssessmentQuestion>? questions,
    int? currentQuestionIndex,
    List<AssessmentAnswer>? answers,
    bool? isLoadingNextQuestion,
  }) {
    return AssessmentInProgressState(
      userId: userId ?? this.userId,
      questions: questions ?? this.questions,
      currentQuestionIndex: currentQuestionIndex ?? this.currentQuestionIndex,
      answers: answers ?? this.answers,
      isLoadingNextQuestion:
          isLoadingNextQuestion ?? this.isLoadingNextQuestion,
    );
  }
}
