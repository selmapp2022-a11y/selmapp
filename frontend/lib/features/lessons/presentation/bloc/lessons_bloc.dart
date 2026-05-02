import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../data/models/lesson_models.dart';
import '../../data/repositories/lessons_repository.dart';

// Events
abstract class LessonsEvent extends Equatable {
  const LessonsEvent();

  @override
  List<Object?> get props => [];
}

class LoadLessonsData extends LessonsEvent {}

class RefreshLessonsData extends LessonsEvent {}

class CompleteLesson extends LessonsEvent {
  final String lessonId;
  final int score;

  const CompleteLesson(this.lessonId, this.score);

  @override
  List<Object?> get props => [lessonId, score];
}

class UpdateStudyPlan extends LessonsEvent {
  final PersonalStudyPlan studyPlan;

  const UpdateStudyPlan(this.studyPlan);

  @override
  List<Object?> get props => [studyPlan];
}

class GenerateLesson extends LessonsEvent {
  final String lessonType;
  final String difficultyLevel;
  final String? topic;
  final Map<String, dynamic>? userPreferences;

  const GenerateLesson({
    required this.lessonType,
    required this.difficultyLevel,
    this.topic,
    this.userPreferences,
  });

  @override
  List<Object?> get props => [lessonType, difficultyLevel, topic, userPreferences];
}

// States
abstract class LessonsState extends Equatable {
  const LessonsState();

  @override
  List<Object?> get props => [];
}

class LessonsInitial extends LessonsState {}

class LessonsLoading extends LessonsState {}

class LessonsLoaded extends LessonsState {
  final List<PersonalStudyPlan> studyPlans;
  final List<Lesson> lessons;
  final List<AIConversation> conversations;
  final List<ConversationMessage> writingSamples;
  final LearningProgress progress;

  const LessonsLoaded({
    required this.studyPlans,
    required this.lessons,
    required this.conversations,
    required this.writingSamples,
    required this.progress,
  });

  @override
  List<Object?> get props => [
    studyPlans,
    lessons,
    conversations,
    writingSamples,
    progress,
  ];
}

class LessonsError extends LessonsState {
  final String message;

  const LessonsError(this.message);

  @override
  List<Object?> get props => [message];
}

// BLoC
class LessonsBloc extends Bloc<LessonsEvent, LessonsState> {
  final LessonsRepository _lessonsRepository;

  LessonsBloc(this._lessonsRepository) : super(LessonsInitial()) {
    on<LoadLessonsData>(_onLoadLessonsData);
    on<RefreshLessonsData>(_onRefreshLessonsData);
    on<CompleteLesson>(_onCompleteLesson);
    on<UpdateStudyPlan>(_onUpdateStudyPlan);
    on<GenerateLesson>(_onGenerateLesson);
  }

  Future<void> _onLoadLessonsData(
    LoadLessonsData event,
    Emitter<LessonsState> emit,
  ) async {
    emit(LessonsLoading());

    try {
      // Load lessons from database cache first
      final lessons = await _lessonsRepository.getLessons();

      // If no cached lessons, get recommendations
      final recommendedLessons = lessons.isEmpty
          ? await _lessonsRepository.getRecommendedLessons()
          : [];

      // For now, create mock data for other components until they're implemented
      final List<PersonalStudyPlan> studyPlans = []; // TODO: Implement study plans
      final List<AIConversation> conversations = []; // TODO: Implement conversations
      final List<ConversationMessage> writingSamples = []; // TODO: Implement writing samples
      final progress = LearningProgress(
        userId: 'current_user',
        currentLevel: DifficultyLevel.b1,
        skillScores: {},
        completedLessons: lessons.where((l) => l.isCompleted).map((l) => l.id).toList(),
        strengths: const ['vocabulary', 'listening'],
        weaknesses: const ['grammar', 'pronunciation'],
        totalStudyMinutes: 0,
        conversationCount: 0,
        writingCount: 0,
        lastActivity: DateTime.now(),
        recentTopics: const [],
      );

      emit(LessonsLoaded(
        studyPlans: studyPlans,
        lessons: [...lessons, ...recommendedLessons],
        conversations: conversations,
        writingSamples: writingSamples,
        progress: progress,
      ));
    } catch (e) {
      emit(LessonsError('Failed to load lessons data: ${e.toString()}'));
    }
  }

  Future<void> _onRefreshLessonsData(
    RefreshLessonsData event,
    Emitter<LessonsState> emit,
  ) async {
    // Refresh by reloading from API
    add(LoadLessonsData());
  }

  Future<void> _onCompleteLesson(
    CompleteLesson event,
    Emitter<LessonsState> emit,
  ) async {
    if (state is LessonsLoaded) {
      final currentState = state as LessonsLoaded;

      try {
        // Update lesson progress via API
        await _lessonsRepository.updateLessonProgress(
          lessonId: event.lessonId,
          progress: 100.0,
          accuracy: event.score / 100.0,
          isCompleted: true,
        );

        // Update local state
        final updatedLessons = currentState.lessons.map((lesson) {
          if (lesson.id == event.lessonId) {
            return Lesson(
              id: lesson.id,
              title: lesson.title,
              description: lesson.description,
              type: lesson.type,
              level: lesson.level,
              estimatedMinutes: lesson.estimatedMinutes,
              objectives: lesson.objectives,
              keyTopics: lesson.keyTopics,
              isCompleted: true,
              completedAt: DateTime.now(),
              userScore: event.score,
            );
          }
          return lesson;
        }).toList();

        emit(LessonsLoaded(
          studyPlans: currentState.studyPlans,
          lessons: updatedLessons,
          conversations: currentState.conversations,
          writingSamples: currentState.writingSamples,
          progress: currentState.progress,
        ));
      } catch (e) {
        emit(LessonsError('Failed to complete lesson: ${e.toString()}'));
      }
    }
  }

  Future<void> _onGenerateLesson(
    GenerateLesson event,
    Emitter<LessonsState> emit,
  ) async {
    if (state is LessonsLoaded) {
      final currentState = state as LessonsLoaded;

      try {
        // Generate new lesson via API
        final newLesson = await _lessonsRepository.generateLesson(
          lessonType: event.lessonType,
          difficultyLevel: event.difficultyLevel,
          topic: event.topic,
          userPreferences: event.userPreferences,
        );

        // Start the lesson session
        await _lessonsRepository.startLesson(newLesson.id);

        // Add to lessons list
        final updatedLessons = [...currentState.lessons, newLesson];

        emit(LessonsLoaded(
          studyPlans: currentState.studyPlans,
          lessons: updatedLessons,
          conversations: currentState.conversations,
          writingSamples: currentState.writingSamples,
          progress: currentState.progress,
        ));
      } catch (e) {
        emit(LessonsError('Failed to generate lesson: ${e.toString()}'));
      }
    }
  }

  Future<void> _onUpdateStudyPlan(
    UpdateStudyPlan event,
    Emitter<LessonsState> emit,
  ) async {
    if (state is LessonsLoaded) {
      final currentState = state as LessonsLoaded;
      
      try {
        // Update study plan
        final updatedPlans = currentState.studyPlans.map((plan) {
          if (plan.id == event.studyPlan.id) {
            return event.studyPlan;
          }
          return plan;
        }).toList();
        
        emit(LessonsLoaded(
          studyPlans: updatedPlans,
          lessons: currentState.lessons,
          conversations: currentState.conversations,
          writingSamples: currentState.writingSamples,
          progress: currentState.progress,
        ));
      } catch (e) {
        emit(LessonsError('Failed to update study plan: ${e.toString()}'));
      }
    }
  }
}

