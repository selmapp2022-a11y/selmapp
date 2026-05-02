import 'package:flutter/foundation.dart';

import '../../../../core/network/api_client.dart';
import '../models/exercise_models.dart';

/// Service for generating AI-powered personalized practice exercises.
/// This service connects to the backend AI endpoints to generate
/// exercises tailored to the user's level and learning goals.
class AIPracticeService {
  final ApiClient _apiClient;

  // Cache for generated exercises to avoid redundant API calls
  final Map<String, List<Exercise>> _exerciseCache = {};
  DateTime? _lastCacheRefresh;
  static const _cacheValidityDuration = Duration(minutes: 15);

  AIPracticeService(this._apiClient);

  /// Generate AI-powered exercises for a specific skill type and level.
  Future<List<Exercise>> generateExercises({
    required String exerciseType,
    required String level,
    String? topic,
    int count = 5,
  }) async {
    final cacheKey = '${exerciseType}_${level}_${topic ?? "general"}';

    // Check cache validity
    if (_isCacheValid(cacheKey)) {
      if (kDebugMode) {
        print('📦 Using cached exercises for $cacheKey');
      }
      return _exerciseCache[cacheKey]!;
    }

    try {
      if (kDebugMode) {
        print('🤖 Generating AI exercises: type=$exerciseType, level=$level, topic=$topic');
      }

      final response = await _apiClient.post(
        '/ai/generate-exercises',
        data: {
          'topic': topic ?? _getDefaultTopic(exerciseType),
          'difficulty_level': level,
          'exercise_type': exerciseType,
          'count': count,
        },
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        final exercises = _parseGeneratedExercises(
          response.data,
          exerciseType,
          level,
        );

        // Update cache
        _exerciseCache[cacheKey] = exercises;
        _lastCacheRefresh = DateTime.now();

        if (kDebugMode) {
          print('✅ Generated ${exercises.length} AI exercises');
        }

        return exercises;
      } else {
        if (kDebugMode) {
          print('⚠️ AI generation response unsuccessful: ${response.data}');
        }
        return [];
      }
    } catch (e) {
      if (kDebugMode) {
        print('❌ Failed to generate AI exercises: $e');
      }
      return [];
    }
  }

  /// Get vocabulary explanation and examples from AI.
  Future<VocabularyExplanation?> getVocabularyExplanation({
    required String word,
    required String level,
  }) async {
    try {
      final response = await _apiClient.post(
        '/ai/vocabulary-explanation',
        data: {
          'word': word,
          'level': level,
        },
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        return VocabularyExplanation.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Failed to get vocabulary explanation: $e');
      }
      return null;
    }
  }

  /// Check grammar and get AI feedback.
  Future<GrammarCheckResult?> checkGrammar(String text) async {
    try {
      final response = await _apiClient.post(
        '/ai/grammar-check',
        data: {'text': text},
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        return GrammarCheckResult.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Failed to check grammar: $e');
      }
      return null;
    }
  }

  /// Generate conversation practice scenarios.
  Future<ConversationPractice?> generateConversationPractice({
    required String topic,
    required String level,
    int turns = 6,
  }) async {
    try {
      final response = await _apiClient.post(
        '/ai/conversation-practice',
        data: {
          'topic': topic,
          'level': level,
          'turns': turns,
        },
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        return ConversationPractice.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Failed to generate conversation practice: $e');
      }
      return null;
    }
  }

  /// Submit exercise answer and get AI feedback.
  Future<ExerciseFeedback?> submitExerciseAnswer({
    required int exerciseId,
    required Map<String, dynamic> userAnswer,
    int? timeTakenSeconds,
  }) async {
    try {
      final response = await _apiClient.post(
        '/exercises/submit',
        data: {
          'exercise_id': exerciseId,
          'user_answer': userAnswer,
          if (timeTakenSeconds != null) 'time_taken_seconds': timeTakenSeconds,
        },
      );

      if (response.statusCode == 200) {
        return ExerciseFeedback.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Failed to submit exercise: $e');
      }
      return null;
    }
  }

  bool _isCacheValid(String key) {
    if (!_exerciseCache.containsKey(key) || _lastCacheRefresh == null) {
      return false;
    }
    return DateTime.now().difference(_lastCacheRefresh!) < _cacheValidityDuration;
  }

  String _getDefaultTopic(String exerciseType) {
    switch (exerciseType.toLowerCase()) {
      case 'vocabulary':
        return 'everyday vocabulary and common phrases';
      case 'grammar':
        return 'essential grammar patterns';
      case 'reading':
        return 'interesting articles and stories';
      case 'listening':
        return 'conversations and dialogues';
      case 'speaking':
        return 'practical speaking scenarios';
      case 'writing':
        return 'writing for communication';
      default:
        return 'English language skills';
    }
  }

  List<Exercise> _parseGeneratedExercises(
    Map<String, dynamic> data,
    String exerciseType,
    String level,
  ) {
    final List<Exercise> exercises = [];
    final content = data['content'] ?? data['exercises'] ?? data;
    final difficultyLevel = _parseDifficultyLevel(level);

    // Handle different response formats
    if (content is List) {
      for (var i = 0; i < content.length; i++) {
        final item = content[i];
        final exercise = _parseExerciseItem(
          item,
          exerciseType,
          difficultyLevel,
          i,
        );
        if (exercise != null) {
          exercises.add(exercise);
        }
      }
    } else if (content is Map) {
      // Cast to proper type
      final contentMap = Map<String, dynamic>.from(content);
      
      // Single exercise or structured content
      if (contentMap.containsKey('exercises')) {
        final exerciseList = contentMap['exercises'] as List? ?? [];
        for (var i = 0; i < exerciseList.length; i++) {
          final exercise = _parseExerciseItem(
            exerciseList[i],
            exerciseType,
            difficultyLevel,
            i,
          );
          if (exercise != null) {
            exercises.add(exercise);
          }
        }
      } else if (contentMap.containsKey('words') || contentMap.containsKey('vocabulary')) {
        // Vocabulary format
        exercises.add(_parseVocabularyExercise(contentMap, difficultyLevel));
      } else if (contentMap.containsKey('questions')) {
        // Grammar/quiz format
        exercises.add(_parseGrammarExercise(contentMap, difficultyLevel));
      }
    }

    return exercises;
  }

  Exercise? _parseExerciseItem(
    dynamic item,
    String exerciseType,
    DifficultyLevel level,
    int index,
  ) {
    if (item == null) return null;

    final Map<String, dynamic> exerciseData = item is Map<String, dynamic>
        ? item
        : {'content': item.toString()};

    final id = exerciseData['id']?.toString() ?? 'ai_${DateTime.now().millisecondsSinceEpoch}_$index';
    final title = exerciseData['title'] as String? ?? 'Practice Exercise ${index + 1}';
    final description = exerciseData['description'] as String? ?? '';

    switch (exerciseType.toLowerCase()) {
      case 'vocabulary':
        return _parseVocabularyFromItem(exerciseData, id, title, description, level);
      case 'grammar':
        return _parseGrammarFromItem(exerciseData, id, title, description, level);
      case 'reading':
        return _parseReadingFromItem(exerciseData, id, title, description, level);
      case 'speaking':
        return _parseSpeakingFromItem(exerciseData, id, title, description, level);
      case 'writing':
        return _parseWritingFromItem(exerciseData, id, title, description, level);
      default:
        return _parseGrammarFromItem(exerciseData, id, title, description, level);
    }
  }

  VocabularyExercise _parseVocabularyExercise(
    Map<String, dynamic> data,
    DifficultyLevel level,
  ) {
    final wordsData = data['words'] ?? data['vocabulary'] ?? [];
    final words = <VocabularyWord>[];

    if (wordsData is List) {
      for (final wordData in wordsData) {
        if (wordData is Map<String, dynamic>) {
          words.add(VocabularyWord(
            word: wordData['word'] as String? ?? '',
            definition: wordData['definition'] as String? ?? wordData['meaning'] as String? ?? '',
            pronunciation: wordData['pronunciation'] as String? ?? '',
            exampleSentence: wordData['example'] as String? ?? wordData['example_sentence'] as String? ?? '',
            synonyms: (wordData['synonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
            antonyms: (wordData['antonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
          ));
        }
      }
    }

    return VocabularyExercise(
      id: 'vocab_${DateTime.now().millisecondsSinceEpoch}',
      title: data['title'] as String? ?? 'Vocabulary Practice',
      description: data['description'] as String? ?? 'Learn and practice new words',
      level: level,
      estimatedDurationMinutes: 10,
      points: words.length * 10,
      tags: ['vocabulary', 'ai-generated'],
      words: words,
      exerciseType: VocabularyExerciseType.multipleChoice,
    );
  }

  VocabularyExercise _parseVocabularyFromItem(
    Map<String, dynamic> data,
    String id,
    String title,
    String description,
    DifficultyLevel level,
  ) {
    final words = <VocabularyWord>[];

    // Try different data formats
    if (data.containsKey('words')) {
      for (final w in (data['words'] as List? ?? [])) {
        words.add(_parseWord(w));
      }
    } else if (data.containsKey('word')) {
      words.add(_parseWord(data));
    } else if (data.containsKey('questions')) {
      // Convert questions to vocabulary words
      for (final q in (data['questions'] as List? ?? [])) {
        if (q is Map<String, dynamic>) {
          words.add(VocabularyWord(
            word: q['word'] as String? ?? q['question'] as String? ?? '',
            definition: q['definition'] as String? ?? q['correct_answer'] as String? ?? '',
            pronunciation: q['pronunciation'] as String? ?? '',
            exampleSentence: q['example'] as String? ?? '',
          ));
        }
      }
    }

    return VocabularyExercise(
      id: id,
      title: title.isNotEmpty ? title : 'Vocabulary Practice',
      description: description.isNotEmpty ? description : 'Expand your vocabulary',
      level: level,
      estimatedDurationMinutes: 5 + (words.length * 2),
      points: words.length * 10,
      tags: ['vocabulary', 'ai-generated'],
      words: words,
      exerciseType: VocabularyExerciseType.multipleChoice,
    );
  }

  VocabularyWord _parseWord(dynamic data) {
    if (data is Map<String, dynamic>) {
      return VocabularyWord(
        word: data['word'] as String? ?? data['term'] as String? ?? '',
        definition: data['definition'] as String? ?? data['meaning'] as String? ?? '',
        pronunciation: data['pronunciation'] as String? ?? data['phonetic'] as String? ?? '',
        exampleSentence: data['example'] as String? ?? data['example_sentence'] as String? ?? data['sentence'] as String? ?? '',
        synonyms: (data['synonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
        antonyms: (data['antonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
      );
    }
    return VocabularyWord(
      word: data.toString(),
      definition: '',
      pronunciation: '',
      exampleSentence: '',
    );
  }

  GrammarExercise _parseGrammarExercise(
    Map<String, dynamic> data,
    DifficultyLevel level,
  ) {
    final questionsData = data['questions'] ?? [];
    final questions = <GrammarQuestion>[];

    if (questionsData is List) {
      for (var i = 0; i < questionsData.length; i++) {
        final q = questionsData[i];
        if (q is Map<String, dynamic>) {
          questions.add(GrammarQuestion(
            id: q['id']?.toString() ?? 'q_$i',
            question: q['question'] as String? ?? '',
            options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
            correctAnswer: q['correct_answer'] as String? ?? q['answer'] as String? ?? '',
            explanation: q['explanation'] as String? ?? '',
          ));
        }
      }
    }

    return GrammarExercise(
      id: 'grammar_${DateTime.now().millisecondsSinceEpoch}',
      title: data['title'] as String? ?? 'Grammar Practice',
      description: data['description'] as String? ?? 'Practice grammar rules',
      level: level,
      estimatedDurationMinutes: 10,
      points: questions.length * 15,
      tags: ['grammar', 'ai-generated'],
      grammarRule: data['grammar_rule'] as String? ?? data['rule'] as String? ?? '',
      explanation: data['explanation'] as String? ?? '',
      questions: questions,
    );
  }

  GrammarExercise _parseGrammarFromItem(
    Map<String, dynamic> data,
    String id,
    String title,
    String description,
    DifficultyLevel level,
  ) {
    final questions = <GrammarQuestion>[];

    if (data.containsKey('questions')) {
      for (var i = 0; i < (data['questions'] as List).length; i++) {
        final q = (data['questions'] as List)[i];
        if (q is Map<String, dynamic>) {
          questions.add(GrammarQuestion(
            id: q['id']?.toString() ?? 'q_$i',
            question: q['question'] as String? ?? '',
            options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
            correctAnswer: q['correct_answer'] as String? ?? q['answer'] as String? ?? '',
            explanation: q['explanation'] as String? ?? '',
          ));
        }
      }
    } else if (data.containsKey('question')) {
      // Single question format
      questions.add(GrammarQuestion(
        id: 'q_0',
        question: data['question'] as String? ?? '',
        options: (data['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
        correctAnswer: data['correct_answer'] as String? ?? data['answer'] as String? ?? '',
        explanation: data['explanation'] as String? ?? '',
      ));
    }

    return GrammarExercise(
      id: id,
      title: title.isNotEmpty ? title : 'Grammar Practice',
      description: description.isNotEmpty ? description : 'Master grammar patterns',
      level: level,
      estimatedDurationMinutes: 5 + (questions.length * 2),
      points: questions.length * 15,
      tags: ['grammar', 'ai-generated'],
      grammarRule: data['grammar_rule'] as String? ?? data['rule'] as String? ?? '',
      explanation: data['explanation'] as String? ?? '',
      questions: questions,
    );
  }

  ReadingExercise _parseReadingFromItem(
    Map<String, dynamic> data,
    String id,
    String title,
    String description,
    DifficultyLevel level,
  ) {
    final questions = <ReadingQuestion>[];
    final text = data['text'] as String? ?? data['passage'] as String? ?? data['content'] as String? ?? '';

    if (data.containsKey('questions')) {
      for (var i = 0; i < (data['questions'] as List).length; i++) {
        final q = (data['questions'] as List)[i];
        if (q is Map<String, dynamic>) {
          questions.add(ReadingQuestion(
            id: q['id']?.toString() ?? 'q_$i',
            question: q['question'] as String? ?? '',
            options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
            correctAnswer: q['correct_answer'] as String? ?? q['answer'] as String? ?? '',
            type: ReadingQuestionType.multipleChoice,
          ));
        }
      }
    }

    return ReadingExercise(
      id: id,
      title: title.isNotEmpty ? title : 'Reading Comprehension',
      description: description.isNotEmpty ? description : 'Read and answer questions',
      level: level,
      estimatedDurationMinutes: 10,
      points: 25 + (questions.length * 10),
      tags: ['reading', 'ai-generated'],
      text: text,
      questions: questions,
      vocabularyHighlights: [],
      wordCount: text.split(' ').length,
    );
  }

  SpeakingExercise _parseSpeakingFromItem(
    Map<String, dynamic> data,
    String id,
    String title,
    String description,
    DifficultyLevel level,
  ) {
    return SpeakingExercise(
      id: id,
      title: title.isNotEmpty ? title : 'Speaking Practice',
      description: description.isNotEmpty ? description : 'Practice your speaking skills',
      level: level,
      estimatedDurationMinutes: 5,
      points: 30,
      tags: ['speaking', 'ai-generated'],
      prompt: data['prompt'] as String? ?? data['question'] as String? ?? data['text'] as String? ?? '',
      keyWords: (data['keywords'] as List?)?.map((e) => e.toString()).toList() ?? [],
      speakingType: SpeakingExerciseType.conversation,
      maxRecordingSeconds: 60,
    );
  }

  WritingExercise _parseWritingFromItem(
    Map<String, dynamic> data,
    String id,
    String title,
    String description,
    DifficultyLevel level,
  ) {
    return WritingExercise(
      id: id,
      title: title.isNotEmpty ? title : 'Writing Practice',
      description: description.isNotEmpty ? description : 'Practice your writing skills',
      level: level,
      estimatedDurationMinutes: 15,
      points: 40,
      tags: ['writing', 'ai-generated'],
      prompt: data['prompt'] as String? ?? data['question'] as String? ?? data['topic'] as String? ?? '',
      guidelines: (data['guidelines'] as List?)?.map((e) => e.toString()).toList() ?? [],
      minWords: data['min_words'] as int? ?? 50,
      maxWords: data['max_words'] as int? ?? 200,
      writingType: WritingType.essay,
      keyWords: (data['keywords'] as List?)?.map((e) => e.toString()).toList() ?? [],
    );
  }

  DifficultyLevel _parseDifficultyLevel(String level) {
    switch (level.toUpperCase()) {
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

  /// Clear the exercise cache to force fresh generation.
  void clearCache() {
    _exerciseCache.clear();
    _lastCacheRefresh = null;
  }
}

// Supporting data classes
class VocabularyExplanation {
  final String word;
  final String definition;
  final String pronunciation;
  final List<String> examples;
  final List<String> synonyms;
  final List<String> antonyms;
  final String usage;

  VocabularyExplanation({
    required this.word,
    required this.definition,
    required this.pronunciation,
    required this.examples,
    required this.synonyms,
    required this.antonyms,
    required this.usage,
  });

  factory VocabularyExplanation.fromJson(Map<String, dynamic> json) {
    final content = json['content'] ?? json;
    return VocabularyExplanation(
      word: content['word'] as String? ?? '',
      definition: content['definition'] as String? ?? '',
      pronunciation: content['pronunciation'] as String? ?? '',
      examples: (content['examples'] as List?)?.map((e) => e.toString()).toList() ?? [],
      synonyms: (content['synonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
      antonyms: (content['antonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
      usage: content['usage'] as String? ?? '',
    );
  }
}

class GrammarCheckResult {
  final bool isCorrect;
  final String originalText;
  final String correctedText;
  final List<GrammarError> errors;
  final String overallFeedback;

  GrammarCheckResult({
    required this.isCorrect,
    required this.originalText,
    required this.correctedText,
    required this.errors,
    required this.overallFeedback,
  });

  factory GrammarCheckResult.fromJson(Map<String, dynamic> json) {
    final content = json['content'] ?? json;
    return GrammarCheckResult(
      isCorrect: content['is_correct'] as bool? ?? false,
      originalText: content['original_text'] as String? ?? '',
      correctedText: content['corrected_text'] as String? ?? '',
      errors: (content['errors'] as List?)
              ?.map((e) => GrammarError.fromJson(e))
              .toList() ??
          [],
      overallFeedback: content['feedback'] as String? ?? content['overall_feedback'] as String? ?? '',
    );
  }
}

class GrammarError {
  final String type;
  final String original;
  final String correction;
  final String explanation;

  GrammarError({
    required this.type,
    required this.original,
    required this.correction,
    required this.explanation,
  });

  factory GrammarError.fromJson(Map<String, dynamic> json) {
    return GrammarError(
      type: json['type'] as String? ?? 'grammar',
      original: json['original'] as String? ?? '',
      correction: json['correction'] as String? ?? '',
      explanation: json['explanation'] as String? ?? '',
    );
  }
}

class ConversationPractice {
  final String topic;
  final String scenario;
  final List<ConversationTurn> turns;

  ConversationPractice({
    required this.topic,
    required this.scenario,
    required this.turns,
  });

  factory ConversationPractice.fromJson(Map<String, dynamic> json) {
    final content = json['content'] ?? json;
    return ConversationPractice(
      topic: content['topic'] as String? ?? '',
      scenario: content['scenario'] as String? ?? '',
      turns: (content['turns'] as List?)
              ?.map((e) => ConversationTurn.fromJson(e))
              .toList() ??
          [],
    );
  }
}

class ConversationTurn {
  final String speaker;
  final String text;
  final String? hint;

  ConversationTurn({
    required this.speaker,
    required this.text,
    this.hint,
  });

  factory ConversationTurn.fromJson(Map<String, dynamic> json) {
    return ConversationTurn(
      speaker: json['speaker'] as String? ?? 'AI',
      text: json['text'] as String? ?? '',
      hint: json['hint'] as String?,
    );
  }
}

class ExerciseFeedback {
  final bool isCorrect;
  final double score;
  final int pointsEarned;
  final Map<String, dynamic>? correctAnswer;
  final String? explanation;
  final String? aiFeedback;

  ExerciseFeedback({
    required this.isCorrect,
    required this.score,
    required this.pointsEarned,
    this.correctAnswer,
    this.explanation,
    this.aiFeedback,
  });

  factory ExerciseFeedback.fromJson(Map<String, dynamic> json) {
    return ExerciseFeedback(
      isCorrect: json['is_correct'] as bool? ?? false,
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      pointsEarned: json['points_earned'] as int? ?? 0,
      correctAnswer: json['correct_answer'] as Map<String, dynamic>?,
      explanation: json['explanation'] as String?,
      aiFeedback: json['ai_feedback'] as String?,
    );
  }
}











