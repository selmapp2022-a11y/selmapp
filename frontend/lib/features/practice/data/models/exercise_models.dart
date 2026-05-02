import 'package:equatable/equatable.dart';

// Enums for exercise types and difficulty levels
enum ExerciseType {
  vocabulary,
  grammar,
  reading,
  listening,
  speaking,
  writing,
  conversation,
}

enum DifficultyLevel {
  a1,
  a2,
  b1,
  b2,
  c1,
  c2,
}

enum ExerciseStatus {
  notStarted,
  inProgress,
  completed,
  failed,
}

// Base Exercise Model
abstract class Exercise extends Equatable {
  final String id;
  final String title;
  final String description;
  final ExerciseType type;
  final DifficultyLevel level;
  final int estimatedDurationMinutes;
  final int points;
  final List<String> tags;
  final ExerciseStatus status;

  const Exercise({
    required this.id,
    required this.title,
    required this.description,
    required this.type,
    required this.level,
    required this.estimatedDurationMinutes,
    required this.points,
    required this.tags,
    this.status = ExerciseStatus.notStarted,
  });

  @override
  List<Object?> get props => [id, title, type, level, status];
}

// Vocabulary Exercise
class VocabularyExercise extends Exercise {
  final List<VocabularyWord> words;
  final VocabularyExerciseType exerciseType;

  const VocabularyExercise({
    required super.id,
    required super.title,
    required super.description,
    required super.level,
    required super.estimatedDurationMinutes,
    required super.points,
    required super.tags,
    required this.words,
    required this.exerciseType,
    super.status,
  }) : super(
          type: ExerciseType.vocabulary,
        );

  @override
  List<Object?> get props => [...super.props, words, exerciseType];
}

enum VocabularyExerciseType {
  matching,
  multipleChoice,
  fillInTheBlanks,
  wordBuilding,
}

class VocabularyWord extends Equatable {
  final String word;
  final String definition;
  final String pronunciation;
  final String exampleSentence;
  final String? imageUrl;
  final List<String> synonyms;
  final List<String> antonyms;
  final String? question;
  final List<String> options;
  final String? correctAnswer;

  const VocabularyWord({
    required this.word,
    required this.definition,
    required this.pronunciation,
    required this.exampleSentence,
    this.imageUrl,
    this.synonyms = const [],
    this.antonyms = const [],
    this.question,
    this.options = const [],
    this.correctAnswer,
  });

  @override
  List<Object?> get props => [
        word,
        definition,
        pronunciation,
        exampleSentence,
        imageUrl,
        question,
        options,
        correctAnswer,
      ];
}

// Grammar Exercise
class GrammarExercise extends Exercise {
  final String grammarRule;
  final String explanation;
  final List<GrammarQuestion> questions;

  const GrammarExercise({
    required super.id,
    required super.title,
    required super.description,
    required super.level,
    required super.estimatedDurationMinutes,
    required super.points,
    required super.tags,
    required this.grammarRule,
    required this.explanation,
    required this.questions,
    super.status,
  }) : super(
          type: ExerciseType.grammar,
        );

  @override
  List<Object?> get props => [...super.props, grammarRule, questions];
}

class GrammarQuestion extends Equatable {
  final String id;
  final String question;
  final List<String> options;
  final String correctAnswer;
  final String explanation;

  const GrammarQuestion({
    required this.id,
    required this.question,
    required this.options,
    required this.correctAnswer,
    required this.explanation,
  });

  @override
  List<Object?> get props => [id, question, options, correctAnswer];
}

// Reading Exercise
class ReadingExercise extends Exercise {
  final String text;
  final List<ReadingQuestion> questions;
  final List<VocabularyWord> vocabularyHighlights;
  final int wordCount;

  const ReadingExercise({
    required super.id,
    required super.title,
    required super.description,
    required super.level,
    required super.estimatedDurationMinutes,
    required super.points,
    required super.tags,
    required this.text,
    required this.questions,
    required this.vocabularyHighlights,
    required this.wordCount,
    super.status,
  }) : super(
          type: ExerciseType.reading,
        );

  @override
  List<Object?> get props => [...super.props, text, questions, wordCount];
}

class ReadingQuestion extends Equatable {
  final String id;
  final String question;
  final List<String> options;
  final String correctAnswer;
  final ReadingQuestionType type;

  const ReadingQuestion({
    required this.id,
    required this.question,
    required this.options,
    required this.correctAnswer,
    required this.type,
  });

  @override
  List<Object?> get props => [id, question, options, correctAnswer, type];
}

enum ReadingQuestionType {
  multipleChoice,
  trueFalse,
  shortAnswer,
  mainIdea,
  detail,
}

// Listening Exercise
class ListeningExercise extends Exercise {
  final String audioUrl;
  final String transcript;
  final List<ListeningQuestion> questions;
  final int durationSeconds;
  final String? imageUrl;

  const ListeningExercise({
    required super.id,
    required super.title,
    required super.description,
    required super.level,
    required super.estimatedDurationMinutes,
    required super.points,
    required super.tags,
    required this.audioUrl,
    required this.transcript,
    required this.questions,
    required this.durationSeconds,
    this.imageUrl,
    super.status,
  }) : super(
          type: ExerciseType.listening,
        );

  @override
  List<Object?> get props => [...super.props, audioUrl, questions, durationSeconds];
}

class ListeningQuestion extends Equatable {
  final String id;
  final String question;
  final List<String> options;
  final String correctAnswer;
  final int? timestampSeconds;

  const ListeningQuestion({
    required this.id,
    required this.question,
    required this.options,
    required this.correctAnswer,
    this.timestampSeconds,
  });

  @override
  List<Object?> get props => [id, question, options, correctAnswer];
}

// Speaking Exercise
class SpeakingExercise extends Exercise {
  final String prompt;
  final List<String> keyWords;
  final String? sampleAudioUrl;
  final String? imageUrl; // AI-generated image for the speaking prompt
  final SpeakingExerciseType speakingType;
  final int maxRecordingSeconds;

  const SpeakingExercise({
    required super.id,
    required super.title,
    required super.description,
    required super.level,
    required super.estimatedDurationMinutes,
    required super.points,
    required super.tags,
    required this.prompt,
    required this.keyWords,
    required this.speakingType,
    required this.maxRecordingSeconds,
    this.sampleAudioUrl,
    this.imageUrl,
    super.status,
  }) : super(
          type: ExerciseType.speaking,
        );

  @override
  List<Object?> get props => [...super.props, prompt, keyWords, speakingType, imageUrl];
}

enum SpeakingExerciseType {
  pronunciation,
  conversation,
  description,
  storytelling,
  presentation,
}

// Writing Exercise
class WritingExercise extends Exercise {
  final String prompt;
  final List<String> guidelines;
  final int minWords;
  final int maxWords;
  final WritingType writingType;
  final List<String> keyWords;

  const WritingExercise({
    required super.id,
    required super.title,
    required super.description,
    required super.level,
    required super.estimatedDurationMinutes,
    required super.points,
    required super.tags,
    required this.prompt,
    required this.guidelines,
    required this.minWords,
    required this.maxWords,
    required this.writingType,
    required this.keyWords,
    super.status,
  }) : super(
          type: ExerciseType.writing,
        );

  @override
  List<Object?> get props => [...super.props, prompt, writingType, minWords, maxWords];
}

enum WritingType {
  essay,
  email,
  letter,
  story,
  description,
  opinion,
}

// AI Trainer Models
class AITrainerMessage extends Equatable {
  final String id;
  final String message;
  final AITrainerMessageType type;
  final DateTime timestamp;
  final Map<String, dynamic>? metadata;

  const AITrainerMessage({
    required this.id,
    required this.message,
    required this.type,
    required this.timestamp,
    this.metadata,
  });

  @override
  List<Object?> get props => [id, message, type, timestamp];
}

enum AITrainerMessageType {
  welcome,
  instruction,
  encouragement,
  correction,
  feedback,
  question,
  celebration,
}

// Learning Session Model
class LearningSession extends Equatable {
  final String id;
  final String title;
  final List<Exercise> exercises;
  final int totalDurationMinutes;
  final int totalPoints;
  final DifficultyLevel level;
  final List<String> focusAreas;
  final AITrainerMessage? trainerIntroduction;
  final SessionStatus status;

  const LearningSession({
    required this.id,
    required this.title,
    required this.exercises,
    required this.totalDurationMinutes,
    required this.totalPoints,
    required this.level,
    required this.focusAreas,
    this.trainerIntroduction,
    this.status = SessionStatus.notStarted,
  });

  @override
  List<Object?> get props => [id, title, exercises, level, status];
}

enum SessionStatus {
  notStarted,
  inProgress,
  completed,
  paused,
}

// User Progress Model
class UserProgress extends Equatable {
  final String userId;
  final DifficultyLevel currentLevel;
  final int totalPoints;
  final int streakDays;
  final Map<ExerciseType, int> skillLevels;
  final List<String> completedExercises;
  final DateTime lastActivity;

  const UserProgress({
    required this.userId,
    required this.currentLevel,
    required this.totalPoints,
    required this.streakDays,
    required this.skillLevels,
    required this.completedExercises,
    required this.lastActivity,
  });

  @override
  List<Object?> get props => [userId, currentLevel, totalPoints, streakDays];
}
