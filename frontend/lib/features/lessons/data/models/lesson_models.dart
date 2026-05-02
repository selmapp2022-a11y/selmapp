import 'package:equatable/equatable.dart';

// Enums for lesson types and difficulty
enum LessonType {
  conversation,
  writing,
  grammar,
  vocabulary,
  pronunciation,
  comprehension,
  mixed,
}

enum StudyPlanType {
  daily,
  weekly,
  intensive,
  custom,
}

enum ConversationTopic {
  dailyLife,
  business,
  travel,
  education,
  health,
  technology,
  culture,
  currentEvents,
  personal,
}

enum DifficultyLevel {
  a1,
  a2,
  b1,
  b2,
  c1,
  c2,
}

enum InteractionType {
  speaking,
  writing,
  listening,
  reading,
}

// Base Lesson Model
class Lesson extends Equatable {
  final String id;
  final String title;
  final String description;
  final LessonType type;
  final DifficultyLevel level;
  final int estimatedMinutes;
  final List<String> objectives;
  final List<String> keyTopics;
  final bool isCompleted;
  final DateTime? completedAt;
  final int? userScore;

  const Lesson({
    required this.id,
    required this.title,
    required this.description,
    required this.type,
    required this.level,
    required this.estimatedMinutes,
    required this.objectives,
    required this.keyTopics,
    this.isCompleted = false,
    this.completedAt,
    this.userScore,
  });

  factory Lesson.fromJson(Map<String, dynamic> json) {
    // Accept both snake_case and camelCase from backend
    final dynamic idValue = json['id'];
    final String id = idValue?.toString() ?? '';

    final String title = (json['title'] ?? '').toString();
    final String description = (json['description'] ?? '').toString();

    final String? typeStr = (json['lesson_type'] ?? json['type'])?.toString();
    final String? levelStr =
        (json['difficulty_level'] ?? json['level'])?.toString();

    final dynamic estimated = json['estimated_minutes'] ?? json['estimatedMinutes'];
    final int estimatedMinutes = estimated is int
        ? estimated
        : estimated is double
            ? estimated.toInt()
            : int.tryParse(estimated?.toString() ?? '') ?? 0;

    final List<String> objectives = ((json['objectives'] as List?) ?? [])
        .map((e) => e.toString())
        .toList();

    final List<String> keyTopics = ((json['key_topics'] as List?) ?? [])
        .map((e) => e.toString())
        .toList();

    final bool isCompleted =
        (json['is_completed'] ?? json['isCompleted'] ?? false) == true;

    final String? completedAtStr =
        (json['completed_at'] ?? json['completedAt'])?.toString();
    final DateTime? completedAt = completedAtStr != null && completedAtStr.isNotEmpty
        ? DateTime.tryParse(completedAtStr)?.toLocal()
        : null;

    final dynamic scoreValue = json['user_score'] ?? json['userScore'];
    final int? userScore = scoreValue == null
        ? null
        : (scoreValue is int
            ? scoreValue
            : scoreValue is double
                ? scoreValue.toInt()
                : int.tryParse(scoreValue.toString()));

    return Lesson(
      id: id,
      title: title,
      description: description,
      type: _parseLessonType(typeStr),
      level: _parseDifficultyLevel(levelStr),
      estimatedMinutes: estimatedMinutes,
      objectives: objectives,
      keyTopics: keyTopics,
      isCompleted: isCompleted,
      completedAt: completedAt,
      userScore: userScore,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'lesson_type': _lessonTypeToString(type),
      'difficulty_level': _difficultyLevelToString(level),
      'estimated_minutes': estimatedMinutes,
      'objectives': objectives,
      'key_topics': keyTopics,
      'is_completed': isCompleted,
      'completed_at': completedAt?.toIso8601String(),
      'user_score': userScore,
    };
  }

  static LessonType _parseLessonType(String? value) {
    switch ((value ?? '').toLowerCase()) {
      case 'conversation':
        return LessonType.conversation;
      case 'writing':
        return LessonType.writing;
      case 'grammar':
        return LessonType.grammar;
      case 'vocabulary':
        return LessonType.vocabulary;
      case 'pronunciation':
        return LessonType.pronunciation;
      case 'comprehension':
        return LessonType.comprehension;
      case 'mixed':
        return LessonType.mixed;
      default:
        return LessonType.mixed;
    }
  }

  static DifficultyLevel _parseDifficultyLevel(String? value) {
    switch ((value ?? '').toUpperCase()) {
      case 'A1':
        return DifficultyLevel.a1;
      case 'A2':
        return DifficultyLevel.a2;
      case 'B1':
        return DifficultyLevel.b1;
      case 'B2':
        return DifficultyLevel.b2;
      case 'C1':
        return DifficultyLevel.c1;
      case 'C2':
        return DifficultyLevel.c2;
      default:
        return DifficultyLevel.b1;
    }
  }

  static String _lessonTypeToString(LessonType type) {
    switch (type) {
      case LessonType.conversation:
        return 'conversation';
      case LessonType.writing:
        return 'writing';
      case LessonType.grammar:
        return 'grammar';
      case LessonType.vocabulary:
        return 'vocabulary';
      case LessonType.pronunciation:
        return 'pronunciation';
      case LessonType.comprehension:
        return 'comprehension';
      case LessonType.mixed:
        return 'mixed';
    }
  }

  static String _difficultyLevelToString(DifficultyLevel level) {
    switch (level) {
      case DifficultyLevel.a1:
        return 'A1';
      case DifficultyLevel.a2:
        return 'A2';
      case DifficultyLevel.b1:
        return 'B1';
      case DifficultyLevel.b2:
        return 'B2';
      case DifficultyLevel.c1:
        return 'C1';
      case DifficultyLevel.c2:
        return 'C2';
    }
  }

  @override
  List<Object?> get props => [
    id,
    title,
    type,
    level,
    isCompleted,
    completedAt,
    userScore,
  ];
}

// Personal Study Plan Model
class PersonalStudyPlan extends Equatable {
  final String id;
  final String title;
  final String description;
  final StudyPlanType type;
  final DifficultyLevel targetLevel;
  final List<String> focusAreas;
  final List<Lesson> lessons;
  final int totalLessons;
  final int completedLessons;
  final DateTime startDate;
  final DateTime? endDate;
  final int estimatedDays;
  final bool isActive;
  final double progressPercentage;

  const PersonalStudyPlan({
    required this.id,
    required this.title,
    required this.description,
    required this.type,
    required this.targetLevel,
    required this.focusAreas,
    required this.lessons,
    required this.totalLessons,
    required this.completedLessons,
    required this.startDate,
    this.endDate,
    required this.estimatedDays,
    this.isActive = true,
    required this.progressPercentage,
  });

  @override
  List<Object?> get props => [
    id,
    title,
    type,
    targetLevel,
    totalLessons,
    completedLessons,
    progressPercentage,
    isActive,
  ];
}

// AI Conversation Model
class AIConversation extends Equatable {
  final String id;
  final ConversationTopic topic;
  final String title;
  final String context;
  final List<ConversationMessage> messages;
  final List<String> suggestedResponses;
  final InteractionType currentInteractionType;
  final bool isActive;
  final DateTime startedAt;
  final DateTime? endedAt;

  const AIConversation({
    required this.id,
    required this.topic,
    required this.title,
    required this.context,
    required this.messages,
    required this.suggestedResponses,
    required this.currentInteractionType,
    this.isActive = true,
    required this.startedAt,
    this.endedAt,
  });

  @override
  List<Object?> get props => [
    id,
    topic,
    title,
    messages,
    isActive,
    startedAt,
  ];
}

// Conversation Message Model
class ConversationMessage extends Equatable {
  final String id;
  final String content;
  final bool isFromUser;
  final DateTime timestamp;
  final InteractionType interactionType;
  final String? audioUrl;
  final AIFeedback? feedback;
  final Map<String, dynamic>? metadata;

  const ConversationMessage({
    required this.id,
    required this.content,
    required this.isFromUser,
    required this.timestamp,
    required this.interactionType,
    this.audioUrl,
    this.feedback,
    this.metadata,
  });

  @override
  List<Object?> get props => [
    id,
    content,
    isFromUser,
    timestamp,
    interactionType,
  ];
}

// AI Feedback Model
class AIFeedback extends Equatable {
  final String id;
  final String originalText;
  final GrammarAnalysis? grammarAnalysis;
  final PronunciationAnalysis? pronunciationAnalysis;
  final WritingAnalysis? writingAnalysis;
  final List<String> suggestions;
  final List<String> corrections;
  final Map<String, dynamic> scores;
  final String overallFeedback;
  final DateTime analyzedAt;

  const AIFeedback({
    required this.id,
    required this.originalText,
    this.grammarAnalysis,
    this.pronunciationAnalysis,
    this.writingAnalysis,
    required this.suggestions,
    required this.corrections,
    required this.scores,
    required this.overallFeedback,
    required this.analyzedAt,
  });

  @override
  List<Object?> get props => [
    id,
    originalText,
    suggestions,
    corrections,
    scores,
    analyzedAt,
  ];
}

// Grammar Analysis Model
class GrammarAnalysis extends Equatable {
  final List<GrammarError> errors;
  final List<GrammarSuggestion> suggestions;
  final int accuracyScore;
  final Map<String, int> categoryScores;

  const GrammarAnalysis({
    required this.errors,
    required this.suggestions,
    required this.accuracyScore,
    required this.categoryScores,
  });

  @override
  List<Object?> get props => [errors, suggestions, accuracyScore, categoryScores];
}

class GrammarError extends Equatable {
  final String type;
  final String description;
  final String originalText;
  final String correctedText;
  final int startIndex;
  final int endIndex;
  final String explanation;

  const GrammarError({
    required this.type,
    required this.description,
    required this.originalText,
    required this.correctedText,
    required this.startIndex,
    required this.endIndex,
    required this.explanation,
  });

  @override
  List<Object?> get props => [
    type,
    originalText,
    correctedText,
    startIndex,
    endIndex,
  ];
}

class GrammarSuggestion extends Equatable {
  final String category;
  final String suggestion;
  final String example;
  final String explanation;

  const GrammarSuggestion({
    required this.category,
    required this.suggestion,
    required this.example,
    required this.explanation,
  });

  @override
  List<Object?> get props => [category, suggestion, example];
}

// Pronunciation Analysis Model
class PronunciationAnalysis extends Equatable {
  final int overallScore;
  final int accuracyScore;
  final int fluencyScore;
  final int completenessScore;
  final List<WordPronunciation> wordAnalysis;
  final List<String> phoneticTranscription;
  final List<PronunciationError> errors;
  final List<String> improvements;

  const PronunciationAnalysis({
    required this.overallScore,
    required this.accuracyScore,
    required this.fluencyScore,
    required this.completenessScore,
    required this.wordAnalysis,
    required this.phoneticTranscription,
    required this.errors,
    required this.improvements,
  });

  @override
  List<Object?> get props => [
    overallScore,
    accuracyScore,
    fluencyScore,
    completenessScore,
    wordAnalysis,
  ];
}

class WordPronunciation extends Equatable {
  final String word;
  final int score;
  final String phonetic;
  final List<String> errors;
  final bool needsImprovement;

  const WordPronunciation({
    required this.word,
    required this.score,
    required this.phonetic,
    required this.errors,
    required this.needsImprovement,
  });

  @override
  List<Object?> get props => [word, score, phonetic, needsImprovement];
}

class PronunciationError extends Equatable {
  final String type;
  final String description;
  final String word;
  final String expectedSound;
  final String actualSound;
  final String improvement;

  const PronunciationError({
    required this.type,
    required this.description,
    required this.word,
    required this.expectedSound,
    required this.actualSound,
    required this.improvement,
  });

  @override
  List<Object?> get props => [type, word, expectedSound, actualSound];
}

// Writing Analysis Model
class WritingAnalysis extends Equatable {
  final int overallScore;
  final int grammarScore;
  final int vocabularyScore;
  final int structureScore;
  final int clarityScore;
  final int coherenceScore;
  final List<WritingSuggestion> suggestions;
  final List<String> strengths;
  final List<String> improvements;
  final int wordCount;
  final String readabilityLevel;

  const WritingAnalysis({
    required this.overallScore,
    required this.grammarScore,
    required this.vocabularyScore,
    required this.structureScore,
    required this.clarityScore,
    required this.coherenceScore,
    required this.suggestions,
    required this.strengths,
    required this.improvements,
    required this.wordCount,
    required this.readabilityLevel,
  });

  @override
  List<Object?> get props => [
    overallScore,
    grammarScore,
    vocabularyScore,
    structureScore,
    clarityScore,
    coherenceScore,
    wordCount,
  ];
}

class WritingSuggestion extends Equatable {
  final String category;
  final String suggestion;
  final String originalText;
  final String improvedText;
  final String explanation;
  final int priority;

  const WritingSuggestion({
    required this.category,
    required this.suggestion,
    required this.originalText,
    required this.improvedText,
    required this.explanation,
    required this.priority,
  });

  @override
  List<Object?> get props => [
    category,
    suggestion,
    originalText,
    improvedText,
    priority,
  ];
}

// Learning Progress Model
class LearningProgress extends Equatable {
  final String userId;
  final DifficultyLevel currentLevel;
  final Map<String, int> skillScores;
  final List<String> completedLessons;
  final List<String> strengths;
  final List<String> weaknesses;
  final int totalStudyMinutes;
  final int conversationCount;
  final int writingCount;
  final DateTime lastActivity;
  final List<String> recentTopics;

  const LearningProgress({
    required this.userId,
    required this.currentLevel,
    required this.skillScores,
    required this.completedLessons,
    required this.strengths,
    required this.weaknesses,
    required this.totalStudyMinutes,
    required this.conversationCount,
    required this.writingCount,
    required this.lastActivity,
    required this.recentTopics,
  });

  @override
  List<Object?> get props => [
    userId,
    currentLevel,
    skillScores,
    completedLessons,
    totalStudyMinutes,
    lastActivity,
  ];
}

