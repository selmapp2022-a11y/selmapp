import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../data/models/exercise_models.dart';
import '../../data/repositories/practice_repository.dart';

// Events
abstract class PracticeEvent extends Equatable {
  const PracticeEvent();

  @override
  List<Object?> get props => [];
}

class LoadPracticeData extends PracticeEvent {}

class RefreshPracticeData extends PracticeEvent {}

class StartExercise extends PracticeEvent {
  final Exercise exercise;

  const StartExercise(this.exercise);

  @override
  List<Object?> get props => [exercise];
}

class CompleteExercise extends PracticeEvent {
  final String exerciseId;
  final int score;

  const CompleteExercise(this.exerciseId, this.score);

  @override
  List<Object?> get props => [exerciseId, score];
}

class UpdateTrainerMessage extends PracticeEvent {
  final AITrainerMessage message;

  const UpdateTrainerMessage(this.message);

  @override
  List<Object?> get props => [message];
}

class SelectSkill extends PracticeEvent {
  final ExerciseType exerciseType;

  const SelectSkill(this.exerciseType);

  @override
  List<Object?> get props => [exerciseType];
}

class LoadExercisesByType extends PracticeEvent {
  final String exerciseType;
  final String? level;

  const LoadExercisesByType({required this.exerciseType, this.level});

  @override
  List<Object?> get props => [exerciseType, level];
}

// States
abstract class PracticeState extends Equatable {
  const PracticeState();

  @override
  List<Object?> get props => [];
}

class PracticeInitial extends PracticeState {}

class PracticeLoading extends PracticeState {}

class PracticeLoaded extends PracticeState {
  final List<LearningSession> learningSessions;
  final List<Exercise> exercises;
  final UserProgress userProgress;
  final AITrainerMessage currentTrainerMessage;
  final Exercise? currentExercise;
  final ExerciseStatisticsData? statistics;
  final List<QuizData> quizzes;
  final LearningPathExercises? learningPath;

  const PracticeLoaded({
    required this.learningSessions,
    required this.exercises,
    required this.userProgress,
    required this.currentTrainerMessage,
    this.currentExercise,
    this.statistics,
    this.quizzes = const [],
    this.learningPath,
  });

  @override
  List<Object?> get props => [
    learningSessions,
    exercises,
    userProgress,
    currentTrainerMessage,
    currentExercise,
    statistics,
    quizzes,
    learningPath,
  ];

  PracticeLoaded copyWith({
    List<LearningSession>? learningSessions,
    List<Exercise>? exercises,
    UserProgress? userProgress,
    AITrainerMessage? currentTrainerMessage,
    Exercise? currentExercise,
    ExerciseStatisticsData? statistics,
    List<QuizData>? quizzes,
    LearningPathExercises? learningPath,
  }) {
    return PracticeLoaded(
      learningSessions: learningSessions ?? this.learningSessions,
      exercises: exercises ?? this.exercises,
      userProgress: userProgress ?? this.userProgress,
      currentTrainerMessage: currentTrainerMessage ?? this.currentTrainerMessage,
      currentExercise: currentExercise ?? this.currentExercise,
      statistics: statistics ?? this.statistics,
      quizzes: quizzes ?? this.quizzes,
      learningPath: learningPath ?? this.learningPath,
    );
  }
}

class PracticeError extends PracticeState {
  final String message;

  const PracticeError(this.message);

  @override
  List<Object?> get props => [message];
}

class ExerciseInProgress extends PracticeState {
  final Exercise exercise;
  final int currentQuestionIndex;
  final List<String> userAnswers;
  final AITrainerMessage? trainerFeedback;

  const ExerciseInProgress({
    required this.exercise,
    required this.currentQuestionIndex,
    required this.userAnswers,
    this.trainerFeedback,
  });

  @override
  List<Object?> get props => [exercise, currentQuestionIndex, userAnswers, trainerFeedback];
}

class ExerciseCompleted extends PracticeState {
  final Exercise exercise;
  final int score;
  final int totalQuestions;
  final AITrainerMessage trainerFeedback;
  final List<String> userAnswers;

  const ExerciseCompleted({
    required this.exercise,
    required this.score,
    required this.totalQuestions,
    required this.trainerFeedback,
    required this.userAnswers,
  });

  @override
  List<Object?> get props => [exercise, score, totalQuestions, trainerFeedback];
}

// BLoC
class PracticeBloc extends Bloc<PracticeEvent, PracticeState> {
  final PracticeRepository? _practiceRepository;

  PracticeBloc([this._practiceRepository]) : super(PracticeInitial()) {
    on<LoadPracticeData>(_onLoadPracticeData);
    on<RefreshPracticeData>(_onRefreshPracticeData);
    on<StartExercise>(_onStartExercise);
    on<CompleteExercise>(_onCompleteExercise);
    on<UpdateTrainerMessage>(_onUpdateTrainerMessage);
    on<SelectSkill>(_onSelectSkill);
    on<LoadExercisesByType>(_onLoadExercisesByType);
  }

  Future<void> _onLoadPracticeData(
    LoadPracticeData event,
    Emitter<PracticeState> emit,
  ) async {
    emit(PracticeLoading());

    final repo = _practiceRepository;
    try {
      if (repo == null) {
        emit(const PracticeError('Practice repository not initialized'));
        return;
      }

      // STEP 1: Get user progress to know their level
      final userProgress = await repo.getUserProgress();
      final userLevel = userProgress?.currentLevel ?? DifficultyLevel.b1;
      final levelString = userLevel.name.toUpperCase();

      if (kDebugMode) {
        print('📚 Loading practice data for level: $levelString');
      }

      // STEP 2: Try to get cached/ready content FIRST (instant load)
      var exercises = <Exercise>[];
      final readyContent = await repo.getReadyContent();
      
      if (readyContent.hasContent) {
        exercises = readyContent.getAllExercises();
        if (kDebugMode) {
          print('⚡ Loaded ${exercises.length} cached exercises instantly');
        }
      }

      // STEP 3: Fetch additional data in parallel (statistics, quizzes, etc.)
      final results = await Future.wait([
        repo.getExerciseStatistics(),
        repo.getQuizzes(level: levelString),
        if (exercises.isEmpty) repo.getExercises(limit: 30, level: levelString),
      ]);

      final statistics = results[0] as ExerciseStatisticsData?;
      final quizzes = results[1] as List<QuizData>;
      
      // If no cached content, use backend exercises
      if (exercises.isEmpty && results.length > 2) {
        final exerciseData = results[2] as List<ExerciseData>;
        exercises = exerciseData.map((e) => e.toExercise()).toList();
        if (kDebugMode) {
          print('📊 Fetched ${exercises.length} exercises from backend');
        }
      }

      // STEP 4: If still not enough content, get micro-lessons quickly
      if (exercises.length < 5) {
        if (kDebugMode) {
          print('🚀 Getting micro-lessons for quick content...');
        }
        
        final microLessons = await _fetchMicroLessons(repo);
        exercises.addAll(microLessons);
        
        if (kDebugMode) {
          print('✨ Added ${microLessons.length} micro-lesson exercises');
        }
      }

      // STEP 5: Apply content fallbacks as safety net
      exercises = _applyContentFallbacks(exercises);

      // STEP 6: Trigger background generation for more content (don't wait)
      _triggerBackgroundGeneration(repo, readyContent.missingSkills);

      if (kDebugMode) {
        print('✅ Final exercise count: ${exercises.length}');
      }

      // Create learning sessions from exercises
      final learningSessions = _createLearningSessions(exercises);
      
      // Create default progress if none returned
      final progress = userProgress ?? UserProgress(
        userId: 'current_user',
        currentLevel: DifficultyLevel.b1,
        totalPoints: 0,
        streakDays: 0,
        skillLevels: const {},
        completedExercises: const [],
        lastActivity: DateTime.now(),
      );

      // Create personalized welcome message based on progress
      final currentMessage = _createWelcomeMessage(progress, exercises);

      emit(PracticeLoaded(
        learningSessions: learningSessions,
        exercises: exercises,
        userProgress: progress,
        currentTrainerMessage: currentMessage,
        statistics: statistics,
        quizzes: quizzes,
        learningPath: null,
      ));
    } catch (e) {
      if (kDebugMode) {
        print('❌ Failed to load practice data: $e');
      }
      emit(PracticeError('Failed to load practice data: ${e.toString()}'));
    }
  }

  /// Fetch micro-lessons quickly for immediate content
  Future<List<Exercise>> _fetchMicroLessons(PracticeRepository repo) async {
    final exercises = <Exercise>[];
    
    try {
      // Fetch vocabulary and grammar micro-lessons in parallel
      final results = await Future.wait([
        repo.getMicroLesson(skillType: 'vocabulary'),
        repo.getMicroLesson(skillType: 'grammar'),
      ]);

      for (var i = 0; i < results.length; i++) {
        final result = results[i];
        if (result.hasExercises) {
          final skillType = i == 0 ? 'vocabulary' : 'grammar';
          exercises.addAll(result.toExercises(skillType));
        }
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Failed to fetch micro-lessons: $e');
      }
    }
    
    return exercises;
  }

  /// Trigger background content generation (fire and forget)
  void _triggerBackgroundGeneration(PracticeRepository repo, List<String> missingSkills) {
    if (missingSkills.isEmpty) return;
    
    // Fire and forget - don't await
    repo.ensureContentReady().catchError((e) {
      if (kDebugMode) {
        print('⚠️ Background generation trigger failed: $e');
      }
    });
  }

  /// Ensure we have exercises for all key skill types by generating AI content if needed.
  AITrainerMessage _createWelcomeMessage(UserProgress progress, List<Exercise> exercises) {
    String message;
    AITrainerMessageType type;

    if (progress.streakDays >= 7) {
      message = '🔥 Amazing! You\'re on a ${progress.streakDays}-day streak! '
          'You have ${exercises.length} exercises ready. Let\'s keep the momentum going!';
      type = AITrainerMessageType.celebration;
    } else if (progress.streakDays > 0) {
      message = 'Welcome back! You\'re on a ${progress.streakDays}-day streak. '
          '${exercises.length} exercises are waiting for you. Let\'s practice!';
      type = AITrainerMessageType.encouragement;
    } else if (exercises.isEmpty) {
      message = 'Welcome! Let\'s start your English learning journey. '
          'I\'ll create personalized exercises just for you!';
      type = AITrainerMessageType.welcome;
    } else {
      message = 'Ready to practice? You have ${exercises.length} exercises available. '
          'Pick any skill to start improving your English!';
      type = AITrainerMessageType.welcome;
    }

    return AITrainerMessage(
      id: 'welcome_${DateTime.now().millisecondsSinceEpoch}',
      message: message,
      type: type,
      timestamp: DateTime.now(),
    );
  }

  Future<void> _onRefreshPracticeData(
    RefreshPracticeData event,
    Emitter<PracticeState> emit,
  ) async {
    // Reload without showing loading state
    add(LoadPracticeData());
  }

  List<LearningSession> _createLearningSessions(List<Exercise> exercises) {
    // Group exercises by type and create sessions
    final Map<ExerciseType, List<Exercise>> groupedExercises = {};
    
    for (final exercise in exercises) {
      groupedExercises.putIfAbsent(exercise.type, () => []).add(exercise);
    }

    final sessions = <LearningSession>[];
    
    groupedExercises.forEach((type, typeExercises) {
      if (typeExercises.isNotEmpty) {
        sessions.add(LearningSession(
          id: 'session_${type.name}',
          title: '${_formatExerciseType(type)} Practice',
          exercises: typeExercises.take(5).toList(),
          totalDurationMinutes: typeExercises.take(5).fold(
            0, 
            (sum, e) => sum + e.estimatedDurationMinutes,
          ),
          totalPoints: typeExercises.take(5).fold(0, (sum, e) => sum + e.points),
          level: typeExercises.first.level,
          focusAreas: [type.name],
        ));
      }
    });

    return sessions;
  }

  String _formatExerciseType(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return 'Vocabulary';
      case ExerciseType.grammar:
        return 'Grammar';
      case ExerciseType.reading:
        return 'Reading';
      case ExerciseType.listening:
        return 'Listening';
      case ExerciseType.speaking:
        return 'Speaking';
      case ExerciseType.writing:
        return 'Writing';
      case ExerciseType.conversation:
        return 'Conversation';
    }
  }

  /// Filter out empty or invalid exercises from the list.
  /// Does NOT use mock data - only returns valid real API content.
  List<Exercise> _applyContentFallbacks(List<Exercise> exercises) {
    final updated = <Exercise>[];

    for (final exercise in exercises) {
      bool isValid = true;
      
      if (exercise is VocabularyExercise) {
        // Only include vocabulary exercises with actual words
        isValid = exercise.words.isNotEmpty;
      } else if (exercise is GrammarExercise) {
        // Only include grammar exercises with questions
        isValid = exercise.questions.isNotEmpty;
      } else if (exercise is ReadingExercise) {
        isValid = exercise.text.isNotEmpty && exercise.questions.isNotEmpty;
      } else if (exercise is ListeningExercise) {
        isValid = exercise.questions.isNotEmpty;
      }
      
      if (isValid) {
        updated.add(exercise);
      }
    }

    return updated;
  }

  Future<void> _onStartExercise(
    StartExercise event,
    Emitter<PracticeState> emit,
  ) async {
    if (state is PracticeLoaded) {
      final currentState = state as PracticeLoaded;
      
      emit(ExerciseInProgress(
        exercise: event.exercise,
        currentQuestionIndex: 0,
        userAnswers: [],
      ));

      // Generate trainer encouragement message
      final encouragementMessage = AITrainerMessage(
        id: 'msg_${DateTime.now().millisecondsSinceEpoch}',
        message: _generateEncouragementMessage(event.exercise),
        type: AITrainerMessageType.instruction,
        timestamp: DateTime.now(),
      );

      // Update the loaded state with the new trainer message
      emit(currentState.copyWith(
        currentTrainerMessage: encouragementMessage,
        currentExercise: event.exercise,
      ));
    }
  }

  Future<void> _onCompleteExercise(
    CompleteExercise event,
    Emitter<PracticeState> emit,
  ) async {
    if (state is ExerciseInProgress) {
      final currentState = state as ExerciseInProgress;
      
      // Calculate score
      final totalQuestions = _getTotalQuestions(currentState.exercise);
      final score = (totalQuestions * 0.8).round();

      // Generate feedback message
      final feedbackMessage = _generateFeedbackMessage(score, totalQuestions);

      emit(ExerciseCompleted(
        exercise: currentState.exercise,
        score: score,
        totalQuestions: totalQuestions,
        trainerFeedback: feedbackMessage,
        userAnswers: currentState.userAnswers,
      ));

      // After delay, reload data
      await Future.delayed(const Duration(seconds: 3));
      
      // Reload practice data to get fresh state
      add(LoadPracticeData());
    }
  }

  Future<void> _onUpdateTrainerMessage(
    UpdateTrainerMessage event,
    Emitter<PracticeState> emit,
  ) async {
    if (state is PracticeLoaded) {
      final currentState = state as PracticeLoaded;
      emit(currentState.copyWith(currentTrainerMessage: event.message));
    }
  }

  Future<void> _onSelectSkill(
    SelectSkill event,
    Emitter<PracticeState> emit,
  ) async {
    if (state is PracticeLoaded) {
      final currentState = state as PracticeLoaded;
      
      // Generate skill-specific trainer message
      final skillMessage = AITrainerMessage(
        id: 'skill_${DateTime.now().millisecondsSinceEpoch}',
        message: _generateSkillMessage(event.exerciseType),
        type: AITrainerMessageType.instruction,
        timestamp: DateTime.now(),
      );

      emit(currentState.copyWith(currentTrainerMessage: skillMessage));
    }
  }

  Future<void> _onLoadExercisesByType(
    LoadExercisesByType event,
    Emitter<PracticeState> emit,
  ) async {
    final repo = _practiceRepository;
    if (state is PracticeLoaded && repo != null) {
      final currentState = state as PracticeLoaded;
      
      try {
        final exerciseData = await repo.getExercises(
          exerciseType: event.exerciseType,
          level: event.level,
        );
        
        final exercises = _applyContentFallbacks(
          exerciseData.map((e) => e.toExercise()).toList(),
        );
        
        emit(currentState.copyWith(exercises: exercises));
      } catch (e) {
        // Keep current state on error
        emit(currentState);
      }
    }
  }


  String _generateEncouragementMessage(Exercise exercise) {
    final messages = [
      'Great choice! Let\'s work on ${exercise.type.name} together. Take your time and do your best!',
      'I believe in you! This ${exercise.type.name} exercise will help you improve. Ready to start?',
      'Perfect! ${exercise.title} is exactly what you need to practice right now. Let\'s go!',
      'Excellent selection! Remember, every mistake is a learning opportunity. You\'ve got this!',
    ];
    
    return messages[DateTime.now().millisecond % messages.length];
  }

  AITrainerMessage _generateFeedbackMessage(int score, int totalQuestions) {
    final percentage = (score / totalQuestions * 100).round();
    String message;
    AITrainerMessageType type;

    if (percentage >= 90) {
      message = 'Outstanding work! You scored $score/$totalQuestions ($percentage%)! You\'re mastering this skill beautifully. Keep up the excellent work! 🌟';
      type = AITrainerMessageType.celebration;
    } else if (percentage >= 70) {
      message = 'Great job! You got $score out of $totalQuestions correct ($percentage%). You\'re making solid progress. Let\'s keep building on this success!';
      type = AITrainerMessageType.encouragement;
    } else if (percentage >= 50) {
      message = 'Good effort! You scored $score/$totalQuestions ($percentage%). There\'s room for improvement, but you\'re on the right track. Let\'s practice more!';
      type = AITrainerMessageType.feedback;
    } else {
      message = 'Don\'t worry about the score ($score/$totalQuestions - $percentage%). Learning takes time! Let\'s review the concepts and try again. You\'re improving with each attempt!';
      type = AITrainerMessageType.correction;
    }

    return AITrainerMessage(
      id: 'feedback_${DateTime.now().millisecondsSinceEpoch}',
      message: message,
      type: type,
      timestamp: DateTime.now(),
    );
  }

  String _generateSkillMessage(ExerciseType exerciseType) {
    final messages = {
      ExerciseType.vocabulary: 'Vocabulary building is fantastic for expanding your English! Let\'s learn some new words that will make your communication more effective.',
      ExerciseType.grammar: 'Grammar is the foundation of clear communication. Let\'s master these rules step by step!',
      ExerciseType.reading: 'Reading comprehension will boost your overall English skills. Let\'s dive into some interesting texts!',
      ExerciseType.listening: 'Listening skills are crucial for real-world communication. Let\'s train your ears to understand English better!',
      ExerciseType.speaking: 'Speaking practice builds confidence! Don\'t worry about perfection - focus on communication.',
      ExerciseType.writing: 'Writing helps organize your thoughts in English. Let\'s create clear, effective texts together!',
      ExerciseType.conversation: 'Conversation practice is where everything comes together. Let\'s have some engaging dialogues!',
    };

    return messages[exerciseType] ?? 'Let\'s practice this skill together!';
  }

  int _getTotalQuestions(Exercise exercise) {
    switch (exercise.type) {
      case ExerciseType.vocabulary:
        return (exercise as VocabularyExercise).words.length;
      case ExerciseType.grammar:
        return (exercise as GrammarExercise).questions.length;
      case ExerciseType.reading:
        return (exercise as ReadingExercise).questions.length;
      case ExerciseType.listening:
        return (exercise as ListeningExercise).questions.length;
      case ExerciseType.speaking:
      case ExerciseType.writing:
      case ExerciseType.conversation:
        return 5;
    }
  }

}
