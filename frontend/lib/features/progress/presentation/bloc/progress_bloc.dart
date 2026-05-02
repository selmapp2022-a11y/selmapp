import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../data/models/progress_models.dart';
import '../../data/repositories/progress_repository.dart';

// Events
abstract class ProgressEvent extends Equatable {
  const ProgressEvent();

  @override
  List<Object?> get props => [];
}

class LoadProgressData extends ProgressEvent {}

class RefreshProgressData extends ProgressEvent {}

class LoadWeeklyProgress extends ProgressEvent {
  final int weeks;
  const LoadWeeklyProgress({this.weeks = 4});

  @override
  List<Object?> get props => [weeks];
}

// States
abstract class ProgressState extends Equatable {
  const ProgressState();

  @override
  List<Object?> get props => [];
}

class ProgressInitial extends ProgressState {}

class ProgressLoading extends ProgressState {}

class ProgressLoaded extends ProgressState {
  final ProgressDashboard? dashboard;
  final UserProgressData? userProgress;
  final StreakInfo? streakInfo;
  final List<DailyProgressData> dailyProgress;
  final List<AchievementData> earnedAchievements;
  final List<AchievementData> allAchievements;
  final List<LearningGoalData> learningGoals;
  final ExerciseStatistics? exerciseStats;
  final WeeklyProgressData? weeklyProgress;

  const ProgressLoaded({
    this.dashboard,
    this.userProgress,
    this.streakInfo,
    this.dailyProgress = const [],
    this.earnedAchievements = const [],
    this.allAchievements = const [],
    this.learningGoals = const [],
    this.exerciseStats,
    this.weeklyProgress,
  });

  @override
  List<Object?> get props => [
    dashboard,
    userProgress,
    streakInfo,
    dailyProgress,
    earnedAchievements,
    allAchievements,
    learningGoals,
    exerciseStats,
    weeklyProgress,
  ];

  ProgressLoaded copyWith({
    ProgressDashboard? dashboard,
    UserProgressData? userProgress,
    StreakInfo? streakInfo,
    List<DailyProgressData>? dailyProgress,
    List<AchievementData>? earnedAchievements,
    List<AchievementData>? allAchievements,
    List<LearningGoalData>? learningGoals,
    ExerciseStatistics? exerciseStats,
    WeeklyProgressData? weeklyProgress,
  }) {
    return ProgressLoaded(
      dashboard: dashboard ?? this.dashboard,
      userProgress: userProgress ?? this.userProgress,
      streakInfo: streakInfo ?? this.streakInfo,
      dailyProgress: dailyProgress ?? this.dailyProgress,
      earnedAchievements: earnedAchievements ?? this.earnedAchievements,
      allAchievements: allAchievements ?? this.allAchievements,
      learningGoals: learningGoals ?? this.learningGoals,
      exerciseStats: exerciseStats ?? this.exerciseStats,
      weeklyProgress: weeklyProgress ?? this.weeklyProgress,
    );
  }
}

class ProgressError extends ProgressState {
  final String message;

  const ProgressError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class ProgressBloc extends Bloc<ProgressEvent, ProgressState> {
  final ProgressRepository _progressRepository;

  ProgressBloc(this._progressRepository) : super(ProgressInitial()) {
    on<LoadProgressData>(_onLoadProgressData);
    on<RefreshProgressData>(_onRefreshProgressData);
    on<LoadWeeklyProgress>(_onLoadWeeklyProgress);
  }

  Future<void> _onLoadProgressData(
    LoadProgressData event,
    Emitter<ProgressState> emit,
  ) async {
    emit(ProgressLoading());

    try {
      // Load all progress data in parallel
      final results = await Future.wait([
        _progressRepository.getProgressDashboard(),
        _progressRepository.getUserProgress(),
        _progressRepository.getStreakInfo(),
        _progressRepository.getDailyProgress(days: 7),
        _progressRepository.getEarnedAchievements(),
        _progressRepository.getAllAchievements(),
        _progressRepository.getLearningGoals(),
        _progressRepository.getExerciseStatistics(),
        _progressRepository.getWeeklyProgress(weeks: 4),
      ]);

      emit(ProgressLoaded(
        dashboard: results[0] as ProgressDashboard?,
        userProgress: results[1] as UserProgressData?,
        streakInfo: results[2] as StreakInfo?,
        dailyProgress: results[3] as List<DailyProgressData>,
        earnedAchievements: results[4] as List<AchievementData>,
        allAchievements: results[5] as List<AchievementData>,
        learningGoals: results[6] as List<LearningGoalData>,
        exerciseStats: results[7] as ExerciseStatistics?,
        weeklyProgress: results[8] as WeeklyProgressData?,
      ));
    } catch (e) {
      emit(ProgressError('Failed to load progress data: ${e.toString()}'));
    }
  }

  Future<void> _onRefreshProgressData(
    RefreshProgressData event,
    Emitter<ProgressState> emit,
  ) async {
    // Don't show loading state on refresh
    final currentState = state;
    
    try {
      final results = await Future.wait([
        _progressRepository.getProgressDashboard(),
        _progressRepository.getUserProgress(),
        _progressRepository.getStreakInfo(),
        _progressRepository.getDailyProgress(days: 7),
        _progressRepository.getEarnedAchievements(),
        _progressRepository.getAllAchievements(),
        _progressRepository.getLearningGoals(),
        _progressRepository.getExerciseStatistics(),
        _progressRepository.getWeeklyProgress(weeks: 4),
      ]);

      emit(ProgressLoaded(
        dashboard: results[0] as ProgressDashboard?,
        userProgress: results[1] as UserProgressData?,
        streakInfo: results[2] as StreakInfo?,
        dailyProgress: results[3] as List<DailyProgressData>,
        earnedAchievements: results[4] as List<AchievementData>,
        allAchievements: results[5] as List<AchievementData>,
        learningGoals: results[6] as List<LearningGoalData>,
        exerciseStats: results[7] as ExerciseStatistics?,
        weeklyProgress: results[8] as WeeklyProgressData?,
      ));
    } catch (e) {
      // Keep current state on refresh error
      if (currentState is ProgressLoaded) {
        emit(currentState);
      } else {
        emit(ProgressError('Failed to refresh progress data'));
      }
    }
  }

  Future<void> _onLoadWeeklyProgress(
    LoadWeeklyProgress event,
    Emitter<ProgressState> emit,
  ) async {
    if (state is ProgressLoaded) {
      final currentState = state as ProgressLoaded;
      
      try {
        final weeklyProgress = await _progressRepository.getWeeklyProgress(
          weeks: event.weeks,
        );
        
        emit(currentState.copyWith(weeklyProgress: weeklyProgress));
      } catch (e) {
        // Keep current state on error
        emit(currentState);
      }
    }
  }
}








