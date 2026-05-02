import 'package:flutter/foundation.dart';

import '../../../../core/network/api_client.dart';
import '../models/exercise_models.dart';
import '../services/ai_practice_service.dart';

// Re-export models needed by bloc
export '../models/exercise_models.dart' show UserProgress, DifficultyLevel;

abstract class PracticeRepository {
  Future<List<ExerciseData>> getExercises({
    String? level,
    String? exerciseType,
    int skip = 0,
    int limit = 20,
  });

  Future<ExerciseData?> getExercise(int exerciseId);

  Future<List<ExerciseData>> getRandomExercises({
    required String level,
    String? exerciseType,
    int count = 10,
  });

  Future<ExerciseSubmissionResult> submitExercise({
    required int exerciseId,
    required Map<String, dynamic> userAnswer,
    int? timeTakenSeconds,
  });

  Future<List<ExerciseAttemptData>> getExerciseAttempts({
    int skip = 0,
    int limit = 20,
  });

  Future<ExerciseStatisticsData?> getExerciseStatistics();

  Future<List<QuizData>> getQuizzes({String? level});

  Future<QuizWithExercises?> getQuizWithExercises(int quizId);

  Future<QuizAttemptData?> startQuizAttempt(int quizId);

  Future<QuizSubmissionResult> submitQuiz({
    required int quizId,
    required List<Map<String, dynamic>> answers,
  });

  Future<LearningPathExercises?> getLearningPathExercises(String level);

  Future<UserProgress?> getUserProgress();

  /// Generate AI-powered exercises for a specific skill
  Future<List<Exercise>> generateAIExercises({
    required String exerciseType,
    required String level,
    String? topic,
    int count = 5,
  });

  /// Get AI vocabulary explanation
  Future<VocabularyExplanation?> getVocabularyExplanation({
    required String word,
    required String level,
  });

  /// Check grammar with AI
  Future<GrammarCheckResult?> checkGrammar(String text);

  // ============ OPTIMIZED CONTENT LOADING ============

  /// Get ready/cached practice content instantly
  Future<ReadyContentResult> getReadyContent();

  /// Get a micro-lesson for immediate practice (fast generation)
  Future<MicroLessonResult> getMicroLesson({
    required String skillType,
    String? topic,
  });

  /// Ensure content is ready - triggers background generation if needed
  Future<void> ensureContentReady();

  /// Trigger content pre-generation after assessment
  Future<void> triggerPostAssessmentGeneration(String level);

  /// Assess writing and get detailed AI feedback
  Future<WritingAssessmentResult> assessWriting({
    required String text,
    String writingType,
    String? userLevel,
  });

  /// Generate a listening exercise with audio
  Future<ListeningExercise?> generateListeningExercise({
    required String topic,
    String? level,
    String contentType,
    String? accent,
  });

  /// Assess a grammar answer and get detailed AI feedback
  Future<GrammarAssessmentResult> assessGrammarAnswer({
    required String question,
    required String selectedAnswer,
    required String correctAnswer,
    required List<String> options,
    String grammarRule,
    String userLevel,
  });
}

/// In-memory cache for practice content to avoid regenerating every time
class _PracticeCache {
  static final _PracticeCache _instance = _PracticeCache._internal();
  factory _PracticeCache() => _instance;
  _PracticeCache._internal();

  ReadyContentResult? _readyContent;
  DateTime? _readyContentTimestamp;
  final Map<String, MicroLessonResult> _microLessons = {};
  final Map<String, DateTime> _microLessonTimestamps = {};
  final Map<String, ListeningExercise> _generatedListening = {};
  
  static const Duration _cacheTtl = Duration(minutes: 10);
  static const Duration _microLessonTtl = Duration(minutes: 15);

  bool get hasValidReadyContent {
    if (_readyContent == null || _readyContentTimestamp == null) return false;
    return DateTime.now().difference(_readyContentTimestamp!) < _cacheTtl;
  }

  ReadyContentResult? get readyContent => hasValidReadyContent ? _readyContent : null;

  void setReadyContent(ReadyContentResult content) {
    _readyContent = content;
    _readyContentTimestamp = DateTime.now();
  }

  MicroLessonResult? getMicroLesson(String skillType) {
    final timestamp = _microLessonTimestamps[skillType];
    if (timestamp == null) return null;
    if (DateTime.now().difference(timestamp) > _microLessonTtl) {
      _microLessons.remove(skillType);
      _microLessonTimestamps.remove(skillType);
      return null;
    }
    return _microLessons[skillType];
  }

  void setMicroLesson(String skillType, MicroLessonResult lesson) {
    _microLessons[skillType] = lesson;
    _microLessonTimestamps[skillType] = DateTime.now();
  }

  ListeningExercise? getGeneratedListening(String topic) {
    return _generatedListening[topic.toLowerCase()];
  }

  void setGeneratedListening(String topic, ListeningExercise exercise) {
    _generatedListening[topic.toLowerCase()] = exercise;
  }

  void clearAll() {
    _readyContent = null;
    _readyContentTimestamp = null;
    _microLessons.clear();
    _microLessonTimestamps.clear();
    _generatedListening.clear();
  }

  void clearMicroLessons() {
    _microLessons.clear();
    _microLessonTimestamps.clear();
  }
}

class PracticeRepositoryImpl implements PracticeRepository {
  final ApiClient _apiClient;
  late final AIPracticeService _aiService;
  final _PracticeCache _cache = _PracticeCache();

  PracticeRepositoryImpl(this._apiClient) {
    _aiService = AIPracticeService(_apiClient);
  }

  @override
  Future<List<ExerciseData>> getExercises({
    String? level,
    String? exerciseType,
    int skip = 0,
    int limit = 20,
  }) async {
    try {
      final response = await _apiClient.get(
        '/exercises/',
        queryParameters: {
          if (level != null) 'level': level,
          if (exerciseType != null) 'exercise_type': exerciseType,
          'skip': skip,
          'limit': limit,
        },
      );

      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => ExerciseData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get exercises: $e');
      }
      return [];
    }
  }

  @override
  Future<ExerciseData?> getExercise(int exerciseId) async {
    try {
      final response = await _apiClient.get('/exercises/$exerciseId');
      if (response.statusCode == 200) {
        return ExerciseData.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get exercise: $e');
      }
      return null;
    }
  }

  @override
  Future<List<ExerciseData>> getRandomExercises({
    required String level,
    String? exerciseType,
    int count = 10,
  }) async {
    try {
      final response = await _apiClient.get(
        '/exercises/random/$level',
        queryParameters: {
          if (exerciseType != null) 'exercise_type': exerciseType,
          'count': count,
        },
      );

      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => ExerciseData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get random exercises: $e');
      }
      return [];
    }
  }

  @override
  Future<ExerciseSubmissionResult> submitExercise({
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
        return ExerciseSubmissionResult.fromJson(response.data);
      }
      return ExerciseSubmissionResult.error('Submission failed');
    } catch (e) {
      if (kDebugMode) {
        print('Failed to submit exercise: $e');
      }
      return ExerciseSubmissionResult.error('Failed to submit: $e');
    }
  }

  @override
  Future<List<ExerciseAttemptData>> getExerciseAttempts({
    int skip = 0,
    int limit = 20,
  }) async {
    try {
      final response = await _apiClient.get(
        '/exercises/attempts/',
        queryParameters: {'skip': skip, 'limit': limit},
      );

      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => ExerciseAttemptData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get exercise attempts: $e');
      }
      return [];
    }
  }

  @override
  Future<ExerciseStatisticsData?> getExerciseStatistics() async {
    try {
      final response = await _apiClient.get('/exercises/statistics/');
      if (response.statusCode == 200) {
        return ExerciseStatisticsData.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get exercise statistics: $e');
      }
      return null;
    }
  }

  @override
  Future<List<QuizData>> getQuizzes({String? level}) async {
    try {
      final response = await _apiClient.get(
        '/exercises/quizzes/',
        queryParameters: {if (level != null) 'level': level},
      );

      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => QuizData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get quizzes: $e');
      }
      return [];
    }
  }

  @override
  Future<QuizWithExercises?> getQuizWithExercises(int quizId) async {
    try {
      final response = await _apiClient.get('/exercises/quizzes/$quizId');
      if (response.statusCode == 200) {
        return QuizWithExercises.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get quiz with exercises: $e');
      }
      return null;
    }
  }

  @override
  Future<QuizAttemptData?> startQuizAttempt(int quizId) async {
    try {
      final response = await _apiClient.post(
        '/exercises/quizzes/$quizId/start',
      );
      if (response.statusCode == 200) {
        return QuizAttemptData.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to start quiz attempt: $e');
      }
      return null;
    }
  }

  @override
  Future<QuizSubmissionResult> submitQuiz({
    required int quizId,
    required List<Map<String, dynamic>> answers,
  }) async {
    try {
      final response = await _apiClient.post(
        '/exercises/quizzes/submit',
        data: {'quiz_id': quizId, 'answers': answers},
      );

      if (response.statusCode == 200) {
        return QuizSubmissionResult.fromJson(response.data);
      }
      return QuizSubmissionResult.error('Quiz submission failed');
    } catch (e) {
      if (kDebugMode) {
        print('Failed to submit quiz: $e');
      }
      return QuizSubmissionResult.error('Failed to submit quiz: $e');
    }
  }

  @override
  Future<LearningPathExercises?> getLearningPathExercises(String level) async {
    try {
      final response = await _apiClient.get('/exercises/learning-path/$level');
      if (response.statusCode == 200) {
        return LearningPathExercises.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get learning path exercises: $e');
      }
      return null;
    }
  }

  @override
  Future<UserProgress?> getUserProgress() async {
    try {
      // Use the dedicated progress endpoint for canonical totals (points, streak, etc.).
      final response = await _apiClient.get('/progress/');
      if (response.statusCode == 200) {
        final data = response.data as Map<String, dynamic>;

        return UserProgress(
          userId: (data['user_id']?.toString() ?? 'current_user'),
          currentLevel: _parseDifficultyLevel((data['current_level'] ?? 'B1').toString()),
          totalPoints: (data['total_points_earned'] as int?) ?? (data['total_points'] as int?) ?? 0,
          streakDays: (data['current_streak_days'] as int?) ?? (data['current_streak'] as int?) ?? 0,
          skillLevels: const {},
          completedExercises: const [],
          lastActivity: DateTime.tryParse((data['last_study_date'] ?? '').toString())
                  ?.toLocal() ??
              DateTime.now(),
        );
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get user progress: $e');
      }
      return null;
    }
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

  @override
  Future<List<Exercise>> generateAIExercises({
    required String exerciseType,
    required String level,
    String? topic,
    int count = 5,
  }) async {
    return _aiService.generateExercises(
      exerciseType: exerciseType,
      level: level,
      topic: topic,
      count: count,
    );
  }

  @override
  Future<VocabularyExplanation?> getVocabularyExplanation({
    required String word,
    required String level,
  }) async {
    return _aiService.getVocabularyExplanation(word: word, level: level);
  }

  @override
  Future<GrammarCheckResult?> checkGrammar(String text) async {
    return _aiService.checkGrammar(text);
  }

  // ============ OPTIMIZED CONTENT LOADING WITH CACHING ============

  @override
  Future<ReadyContentResult> getReadyContent({bool forceRefresh = false}) async {
    // Return cached content if valid and not forcing refresh
    if (!forceRefresh) {
      final cached = _cache.readyContent;
      if (cached != null && cached.hasContent) {
        if (kDebugMode) {
          print('📦 Using cached ready content (${cached.contentCount} items)');
        }
        return cached;
      }
    }

    try {
      final response = await _apiClient.get('/practice-content/ready');

      if (response.statusCode == 200) {
        final result = ReadyContentResult.fromJson(response.data);
        _cache.setReadyContent(result);
        return result;
      }
      return ReadyContentResult.empty();
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get ready content: $e');
      }
      return ReadyContentResult.empty();
    }
  }

  @override
  Future<MicroLessonResult> getMicroLesson({
    required String skillType,
    String? topic,
    bool forceRefresh = false,
  }) async {
    // Return cached micro-lesson if valid
    if (!forceRefresh && topic == null) {
      final cached = _cache.getMicroLesson(skillType);
      if (cached != null && cached.hasExercises) {
        if (kDebugMode) {
          print('📦 Using cached micro-lesson for $skillType');
        }
        return cached;
      }
    }

    try {
      final queryParams = <String, dynamic>{};
      if (topic != null) queryParams['topic'] = topic;

      final response = await _apiClient.get(
        '/practice-content/micro-lesson/$skillType',
        queryParameters: queryParams,
      );

      if (response.statusCode == 200) {
        final result = MicroLessonResult.fromJson(response.data);
        if (topic == null) {
          _cache.setMicroLesson(skillType, result);
        }
        return result;
      }
      return MicroLessonResult.empty();
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get micro-lesson: $e');
      }
      return MicroLessonResult.empty();
    }
  }

  /// Clear all cached content (useful when user logs out or wants fresh content)
  void clearCache() {
    _cache.clearAll();
  }

  /// Clear only micro-lessons cache (useful for refreshing specific content)
  void clearMicroLessonsCache() {
    _cache.clearMicroLessons();
  }

  @override
  Future<void> ensureContentReady() async {
    try {
      await _apiClient.post('/practice-content/ensure-ready');
    } catch (e) {
      if (kDebugMode) {
        print('Failed to ensure content ready: $e');
      }
    }
  }

  @override
  Future<void> triggerPostAssessmentGeneration(String level) async {
    try {
      await _apiClient.post(
        '/practice-content/trigger-post-assessment',
        queryParameters: {'determined_level': level},
      );
    } catch (e) {
      if (kDebugMode) {
        print('Failed to trigger post-assessment generation: $e');
      }
    }
  }

  @override
  Future<WritingAssessmentResult> assessWriting({
    required String text,
    String writingType = 'general',
    String? userLevel,
  }) async {
    try {
      final response = await _apiClient.post(
        '/writing/assess',
        data: {
          'text': text,
          'writing_type': writingType,
          if (userLevel != null) 'user_level': userLevel,
        },
      );

      final responseData = response.data as Map<String, dynamic>?;
      if (responseData != null && 
          responseData['success'] == true && 
          responseData['assessment'] != null) {
        final assessment = responseData['assessment'] as Map<String, dynamic>;
        final scores = assessment['scores'] as Map<String, dynamic>? ?? {};
        
        return WritingAssessmentResult(
          success: true,
          scores: WritingScores(
            overall: (scores['overall'] as num?)?.toInt() ?? 70,
            grammar: (scores['grammar'] as num?)?.toInt() ?? 70,
            vocabulary: (scores['vocabulary'] as num?)?.toInt() ?? 70,
            coherence: (scores['coherence'] as num?)?.toInt() ?? 70,
            taskAchievement: (scores['task_achievement'] as num?)?.toInt() ?? 70,
          ),
          feedback: assessment['feedback'] as String? ?? 'Good effort!',
          strengths: (assessment['strengths'] as List?)?.map((e) => e.toString()).toList() ?? [],
          weaknesses: (assessment['weaknesses'] as List?)?.map((e) => e.toString()).toList() ?? [],
          errors: (assessment['errors'] as List?)?.map((e) => WritingError.fromJson(e as Map<String, dynamic>)).toList() ?? [],
          vocabularySuggestions: (assessment['vocabulary_suggestions'] as List?)?.map((e) => VocabularySuggestion.fromJson(e as Map<String, dynamic>)).toList() ?? [],
          suggestions: (assessment['suggestions'] as List?)?.map((e) => e.toString()).toList() ?? [],
          nextSteps: (assessment['next_steps'] as List?)?.map((e) => e.toString()).toList() ?? [],
          correctedVersion: assessment['corrected_version'] as String?,
        );
      } else {
        return WritingAssessmentResult.fallback();
      }
    } catch (e) {
      if (kDebugMode) {
        print('Failed to assess writing: $e');
      }
      return WritingAssessmentResult.fallback();
    }
  }

  @override
  Future<GrammarAssessmentResult> assessGrammarAnswer({
    required String question,
    required String selectedAnswer,
    required String correctAnswer,
    required List<String> options,
    String grammarRule = '',
    String userLevel = 'B1',
  }) async {
    try {
      final response = await _apiClient.post(
        '/ai/assess-grammar-answer',
        data: {
          'question': question,
          'selected_answer': selectedAnswer,
          'correct_answer': correctAnswer,
          'options': options,
          'grammar_rule': grammarRule,
          'user_level': userLevel,
        },
      );

      final responseData = response.data as Map<String, dynamic>?;
      if (responseData != null && responseData['success'] == true) {
        return GrammarAssessmentResult.fromJson(responseData);
      } else {
        return GrammarAssessmentResult.fallback(
          isCorrect: selectedAnswer == correctAnswer,
          correctAnswer: correctAnswer,
        );
      }
    } catch (e) {
      if (kDebugMode) {
        print('Failed to assess grammar answer: $e');
      }
      return GrammarAssessmentResult.fallback(
        isCorrect: selectedAnswer == correctAnswer,
        correctAnswer: correctAnswer,
      );
    }
  }

  @override
  Future<ListeningExercise?> generateListeningExercise({
    required String topic,
    String? level,
    String contentType = 'conversation',
    String? accent,
    bool useCache = true,
  }) async {
    // Cache key includes accent so American/British versions are cached separately.
    final accentKey = (accent ?? '').trim().toLowerCase();
    final cacheKey = accentKey.isEmpty ? topic : '$topic::$accentKey';

    if (useCache) {
      final cached = _cache.getGeneratedListening(cacheKey);
      if (cached != null) {
        if (kDebugMode) {
          print('📦 Using cached listening exercise for: $cacheKey');
        }
        return cached;
      }
    }

    try {
      final response = await _apiClient.post(
        '/listening/generate',
        data: {
          'topic': topic,
          if (level != null) 'difficulty_level': level,
          'content_type': contentType,
          if (accentKey.isNotEmpty) 'accent': accentKey,
        },
      );

      final responseData = response.data as Map<String, dynamic>?;
      if (responseData != null && 
          responseData['success'] == true && 
          responseData['exercise'] != null) {
        final exercise = responseData['exercise'] as Map<String, dynamic>;
        final questions = (exercise['questions'] as List? ?? []).map((q) {
          final qMap = q as Map<String, dynamic>;
          return ListeningQuestion(
            id: qMap['id'] as String? ?? '',
            question: qMap['question'] as String? ?? '',
            options: (qMap['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
            correctAnswer: qMap['correct_answer'] as String? ?? '',
          );
        }).toList();
        
        final result = ListeningExercise(
          id: exercise['id'] as String? ?? 'listening_${DateTime.now().millisecondsSinceEpoch}',
          title: exercise['title'] as String? ?? 'Listening Practice',
          description: exercise['description'] as String? ?? 'Listen and answer questions',
          level: _parseDifficultyLevel(exercise['level'] as String? ?? 'B1'),
          estimatedDurationMinutes: ((exercise['duration_seconds'] as int? ?? 60) / 60).ceil(),
          points: exercise['points'] as int? ?? 30,
          tags: ['listening', 'ai-generated'],
          audioUrl: exercise['audio_url'] as String? ?? '',
          transcript: exercise['transcript'] as String? ?? '',
          questions: questions,
          durationSeconds: exercise['duration_seconds'] as int? ?? 60,
        );
        
        // Cache the generated exercise
        _cache.setGeneratedListening(topic, result);
        return result;
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to generate listening exercise: $e');
      }
      return null;
    }
  }

  /// Check if audio is available for a listening exercise
  /// Returns the audio URL if available, or null if still generating
  Future<String?> checkAudioAvailability(String exerciseId) async {
    try {
      final response = await _apiClient.get('/listening/audio-status/$exerciseId');
      final data = response.data as Map<String, dynamic>?;
      
      if (data != null && data['ready'] == true) {
        return data['audio_url'] as String?;
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to check audio availability: $e');
      }
      return null;
    }
  }

  /// Poll for audio availability with automatic retry
  /// Returns the audio URL when available, or null after max retries
  Future<String?> pollForAudio({
    required String exerciseId,
    int maxRetries = 10,
    Duration interval = const Duration(seconds: 3),
  }) async {
    for (var i = 0; i < maxRetries; i++) {
      final audioUrl = await checkAudioAvailability(exerciseId);
      if (audioUrl != null && audioUrl.isNotEmpty) {
        return audioUrl;
      }
      await Future.delayed(interval);
    }
    return null;
  }

  /// Generate TTS audio for a transcript without changing the transcript/questions.
  /// This is used to keep Listening "Reading Mode" content stable while adding audio later.
  Future<String?> generateGeminiTtsAudio({
    required String text,
    String audioType = 'conversation',
    String? voice,
    String? accent,
  }) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return null;

    try {
      final accentKey = (accent ?? '').trim().toLowerCase();
      final response = await _apiClient.post(
        '/ai/gemini-tts',
        data: {
          'text': trimmed,
          'audio_type': audioType,
          if (voice != null && voice.trim().isNotEmpty) 'voice': voice.trim(),
          if (accentKey.isNotEmpty) 'accent': accentKey,
        },
      );

      final data = response.data as Map<String, dynamic>?;
      if (data != null && data['success'] == true) {
        final url = (data['audio_url'] as String?)?.trim() ?? '';
        return url.isNotEmpty ? url : null;
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to generate Gemini TTS audio: $e');
      }
      return null;
    }
  }
}

// ============ WRITING ASSESSMENT RESULT ============

class WritingAssessmentResult {
  final bool success;
  final WritingScores scores;
  final String feedback;
  final List<String> strengths;
  final List<String> weaknesses;
  final List<WritingError> errors;
  final List<VocabularySuggestion> vocabularySuggestions;
  final List<String> suggestions;
  final List<String> nextSteps;
  final String? correctedVersion;

  WritingAssessmentResult({
    required this.success,
    required this.scores,
    required this.feedback,
    required this.strengths,
    required this.weaknesses,
    required this.errors,
    required this.vocabularySuggestions,
    required this.suggestions,
    required this.nextSteps,
    this.correctedVersion,
  });

  factory WritingAssessmentResult.fallback() {
    return WritingAssessmentResult(
      success: true,
      scores: WritingScores(
        overall: 70,
        grammar: 70,
        vocabulary: 70,
        coherence: 70,
        taskAchievement: 70,
      ),
      feedback: 'Your writing shows good effort. Keep practicing to improve!',
      strengths: ['Good attempt at expressing ideas'],
      weaknesses: [],
      errors: [],
      vocabularySuggestions: [],
      suggestions: [
        'Continue practicing writing regularly',
        'Read more English content to improve vocabulary',
      ],
      nextSteps: ['Practice writing daily'],
      correctedVersion: null,
    );
  }
}

class WritingScores {
  final int overall;
  final int grammar;
  final int vocabulary;
  final int coherence;
  final int taskAchievement;

  WritingScores({
    required this.overall,
    required this.grammar,
    required this.vocabulary,
    required this.coherence,
    required this.taskAchievement,
  });
}

class WritingError {
  final String type;
  final String original;
  final String corrected;
  final String explanation;
  final String severity;

  WritingError({
    required this.type,
    required this.original,
    required this.corrected,
    required this.explanation,
    required this.severity,
  });

  factory WritingError.fromJson(Map<String, dynamic> json) {
    return WritingError(
      type: json['type'] as String? ?? 'unknown',
      original: json['original'] as String? ?? '',
      corrected: json['corrected'] as String? ?? '',
      explanation: json['explanation'] as String? ?? '',
      severity: json['severity'] as String? ?? 'minor',
    );
  }
}

class VocabularySuggestion {
  final String originalWord;
  final List<String> betterAlternatives;
  final String context;

  VocabularySuggestion({
    required this.originalWord,
    required this.betterAlternatives,
    required this.context,
  });

  factory VocabularySuggestion.fromJson(Map<String, dynamic> json) {
    return VocabularySuggestion(
      originalWord: json['original_word'] as String? ?? '',
      betterAlternatives: (json['better_alternatives'] as List?)?.map((e) => e.toString()).toList() ?? [],
      context: json['context'] as String? ?? '',
    );
  }
}

// ============ GRAMMAR ASSESSMENT RESULT ============

class GrammarAssessmentResult {
  final bool success;
  final bool isCorrect;
  final String explanation;
  final String ruleExplanation;
  final List<String> examples;
  final List<String> commonMistakes;
  final String tip;
  final String? whyWrong;

  GrammarAssessmentResult({
    required this.success,
    required this.isCorrect,
    required this.explanation,
    required this.ruleExplanation,
    required this.examples,
    required this.commonMistakes,
    required this.tip,
    this.whyWrong,
  });

  factory GrammarAssessmentResult.fallback({required bool isCorrect, required String correctAnswer}) {
    return GrammarAssessmentResult(
      success: true,
      isCorrect: isCorrect,
      explanation: isCorrect 
          ? 'Excellent! "$correctAnswer" is the correct answer.' 
          : 'The correct answer is "$correctAnswer".',
      ruleExplanation: 'Keep practicing to master this grammar pattern.',
      examples: [],
      commonMistakes: [],
      tip: 'Practice makes perfect!',
      whyWrong: null,
    );
  }

  factory GrammarAssessmentResult.fromJson(Map<String, dynamic> json) {
    return GrammarAssessmentResult(
      success: json['success'] as bool? ?? true,
      isCorrect: json['is_correct'] as bool? ?? false,
      explanation: json['explanation'] as String? ?? '',
      ruleExplanation: json['rule_explanation'] as String? ?? '',
      examples: (json['examples'] as List?)?.map((e) => e.toString()).toList() ?? [],
      commonMistakes: (json['common_mistakes'] as List?)?.map((e) => e.toString()).toList() ?? [],
      tip: json['tip'] as String? ?? '',
      whyWrong: json['why_wrong'] as String?,
    );
  }
}

// ============ READY CONTENT RESULT ============

class ReadyContentResult {
  final bool success;
  final String userLevel;
  final Map<String, List<CachedExerciseContent>> readyContent;
  final int contentCount;
  final List<String> missingSkills;

  ReadyContentResult({
    required this.success,
    required this.userLevel,
    required this.readyContent,
    required this.contentCount,
    required this.missingSkills,
  });

  factory ReadyContentResult.fromJson(Map<String, dynamic> json) {
    final readyContentRaw = json['ready_content'] as Map<String, dynamic>? ?? {};
    final readyContent = <String, List<CachedExerciseContent>>{};

    readyContentRaw.forEach((key, value) {
      if (value is List) {
        readyContent[key] = value
            .map((e) => CachedExerciseContent.fromJson(e as Map<String, dynamic>))
            .toList();
      }
    });

    return ReadyContentResult(
      success: json['success'] as bool? ?? false,
      userLevel: json['user_level'] as String? ?? 'B1',
      readyContent: readyContent,
      contentCount: json['content_count'] as int? ?? 0,
      missingSkills: (json['missing_skills'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
    );
  }

  factory ReadyContentResult.empty() {
    return ReadyContentResult(
      success: false,
      userLevel: 'B1',
      readyContent: {},
      contentCount: 0,
      missingSkills: [],
    );
  }

  bool get hasContent => contentCount > 0;

  List<Exercise> getAllExercises() {
    final exercises = <Exercise>[];
    readyContent.forEach((skillType, contents) {
      for (final content in contents) {
        exercises.addAll(content.toExercises(skillType));
      }
    });
    return exercises;
  }
}

class CachedExerciseContent {
  final int id;
  final String? topic;
  final Map<String, dynamic> content;
  final String? createdAt;

  CachedExerciseContent({
    required this.id,
    this.topic,
    required this.content,
    this.createdAt,
  });

  factory CachedExerciseContent.fromJson(Map<String, dynamic> json) {
    return CachedExerciseContent(
      id: json['id'] as int? ?? 0,
      topic: json['topic'] as String?,
      content: json['content'] as Map<String, dynamic>? ?? {},
      createdAt: json['created_at'] as String?,
    );
  }

  List<Exercise> toExercises(String skillType) {
    final exercises = <Exercise>[];
    final exercisesList = content['exercises'] as List? ?? [];
    final level = _parseDifficultyLevel(content['level'] as String? ?? 'B1');
    final topicName = (topic ?? content['topic'] as String? ?? 'Practice').trim();

    // For grammar cached content, group multiple items into ONE exercise (multi-question)
    // to avoid showing the same title multiple times in the UI.
    if (skillType.toLowerCase() == 'grammar') {
      final questions = <GrammarQuestion>[];
      final seen = <String>{};
      var totalPoints = 0;

      // Best-effort extraction of grammar rule + explanation (if available)
      String grammarRule = topicName;
      String grammarExplanation = '';

      final grammarSummary = content['grammar_summary'];
      if (grammarSummary is Map) {
        final title = (grammarSummary['title'] as String?)?.trim();
        final expl = (grammarSummary['explanation'] as String?)?.trim();
        if (title != null && title.isNotEmpty) grammarRule = title;
        if (expl != null && expl.isNotEmpty) grammarExplanation = expl;
      }

      final lesson = content['lesson'];
      if (lesson is Map) {
        final gp = lesson['grammar_point'];
        if (gp is Map) {
          final title = (gp['title'] as String?)?.trim();
          final expl = (gp['explanation'] as String?)?.trim();
          if (title != null && title.isNotEmpty) grammarRule = title;
          if (grammarExplanation.isEmpty && expl != null && expl.isNotEmpty) {
            grammarExplanation = expl;
          }
        }
      }

      for (var i = 0; i < exercisesList.length; i++) {
        final ex = exercisesList[i] as Map<String, dynamic>;
        final questionText = ex['question'] as String? ?? '';
        final normalized = questionText.trim().toLowerCase();
        if (normalized.isEmpty || seen.contains(normalized)) continue;
        seen.add(normalized);

        final options = (ex['options'] as List?)?.map((e) => e.toString()).toList() ?? [];
        final correctAnswer = ex['correct_answer'] as String? ?? '';
        final explanation = ex['explanation'] as String? ?? '';
        final points = ex['points'] as int? ?? 10;

        totalPoints += points;
        questions.add(GrammarQuestion(
          id: 'q_${id}_$i',
          question: questionText,
          options: options,
          correctAnswer: correctAnswer,
          explanation: explanation,
        ));
      }

      if (questions.isNotEmpty) {
        exercises.add(GrammarExercise(
          id: 'cached_$id',
          title: '$topicName Grammar',
          description: 'Practice grammar patterns',
          level: level,
          estimatedDurationMinutes: 5,
          points: totalPoints > 0 ? totalPoints : (questions.length * 10),
          tags: [skillType, 'cached'],
          grammarRule: grammarRule,
          explanation: grammarExplanation,
          questions: questions,
        ));
      }

      return exercises;
    }

    for (var i = 0; i < exercisesList.length; i++) {
      final ex = exercisesList[i] as Map<String, dynamic>;
      exercises.add(_parseExercise(ex, skillType, level, topicName, i));
    }

    return exercises;
  }

  Exercise _parseExercise(
    Map<String, dynamic> data,
    String skillType,
    DifficultyLevel level,
    String topic,
    int index,
  ) {
    final id = 'cached_${this.id}_$index';
    final question = data['question'] as String? ?? '';
    final options = (data['options'] as List?)?.map((e) => e.toString()).toList() ?? [];
    final correctAnswer = data['correct_answer'] as String? ?? '';
    final explanation = data['explanation'] as String? ?? '';
    final points = data['points'] as int? ?? 10;
    final text = data['text'] as String? ?? data['passage'] as String? ?? '';
    final audioUrl = data['audio_url'] as String? ?? '';
    final transcript = data['transcript'] as String? ?? '';

    String normalizeReadAloudSentence(String input) {
      var s = input.trim();
      if (s.isEmpty) return s;
      s = s.replaceAll(RegExp(r'\s+'), ' ');
      // Remove surrounding quotes if present
      if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
        s = s.substring(1, s.length - 1).trim();
      }
      if (s.isEmpty) return s;
      // Capitalize first letter (safe for scoring; tokens are case-insensitive)
      s = s[0].toUpperCase() + s.substring(1);
      // Ensure the sentence ends with punctuation (safe for scoring; punctuation is ignored by tokenization)
      if (!RegExp(r'[.!?]$').hasMatch(s)) {
        s = '$s.';
      }
      return s;
    }

    switch (skillType.toLowerCase()) {
      case 'vocabulary':
        final wordText = (data['word'] as String? ?? '').trim();
        final definitionText = (data['definition'] as String? ?? '').trim();
        final exampleSentenceText = (data['example_sentence'] as String? ?? data['example'] as String? ?? '').trim();
        final pronunciationText = (data['pronunciation'] as String? ?? '').trim();
        final synonyms = (data['synonyms'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
        final antonyms = (data['antonyms'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];

        // In cached vocabulary micro-lessons, `question` is the prompt (e.g., "Choose the correct meaning of 'word'"),
        // while `word`/`definition` hold the actual vocabulary content.
        final prompt = question.trim();
        final correct = (correctAnswer.isNotEmpty ? correctAnswer : definitionText).trim();

        String displayWord = wordText;
        if (displayWord.isEmpty) {
          final quoted = RegExp(r"'([^']+)'").firstMatch(prompt) ?? RegExp(r'"([^"]+)"').firstMatch(prompt);
          displayWord = (quoted?.group(1) ?? '').trim();
        }
        if (displayWord.isEmpty) displayWord = prompt.isNotEmpty ? prompt : 'Vocabulary';

        return VocabularyExercise(
          id: id,
          title: '$topic Vocabulary',
          description: prompt.isNotEmpty ? prompt : 'Practice vocabulary words',
          level: level,
          estimatedDurationMinutes: 5,
          points: points,
          tags: [skillType, 'cached'],
          words: [
            VocabularyWord(
              word: displayWord,
              definition: definitionText.isNotEmpty ? definitionText : correct,
              pronunciation: pronunciationText,
              exampleSentence: exampleSentenceText.isNotEmpty ? exampleSentenceText : explanation,
              synonyms: synonyms,
              antonyms: antonyms,
              question: prompt.isNotEmpty ? prompt : null,
              options: options,
              correctAnswer: correct.isNotEmpty ? correct : null,
            ),
          ],
          exerciseType: VocabularyExerciseType.multipleChoice,
        );
      case 'reading':
        // Parse reading-specific content
        final readingText = text.isNotEmpty ? text : explanation.isNotEmpty ? explanation : 'Read the following passage and answer the questions.';
        final readingQuestions = <ReadingQuestion>[];
        final readingTitle = (data['title'] as String? ?? '').trim();
        final readingStyle = (data['style'] as String? ?? '').trim();
        final readingDescription = readingStyle.isNotEmpty
            ? 'Read this $readingStyle and answer the questions'
            : 'Read and answer comprehension questions';
        
        // Parse questions from data if available
        final questionsData = data['questions'] as List?;
        if (questionsData != null) {
          for (var i = 0; i < questionsData.length; i++) {
            final q = questionsData[i] as Map<String, dynamic>;
            readingQuestions.add(ReadingQuestion(
              id: 'rq_${index}_$i',
              question: q['question'] as String? ?? '',
              options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
              correctAnswer: q['correct_answer'] as String? ?? '',
              type: ReadingQuestionType.multipleChoice,
            ));
          }
        }
        
        // If no questions array, create one from the main question
        if (readingQuestions.isEmpty && question.isNotEmpty) {
          readingQuestions.add(ReadingQuestion(
            id: 'rq_${index}_0',
            question: question,
            options: options,
            correctAnswer: correctAnswer,
            type: ReadingQuestionType.multipleChoice,
          ));
        }
        
        return ReadingExercise(
          id: id,
          title: readingTitle.isNotEmpty ? readingTitle : '$topic Reading',
          description: readingDescription,
          level: level,
          estimatedDurationMinutes: 8,
          points: points,
          tags: [skillType, 'cached'],
          text: readingText,
          questions: readingQuestions,
          vocabularyHighlights: [],
          wordCount: readingText.split(' ').length,
        );
      case 'listening':
        // Parse listening-specific content
        final listeningQuestions = <ListeningQuestion>[];
        
        // Parse questions from data if available
        final listenQuestionsData = data['questions'] as List?;
        if (listenQuestionsData != null) {
          for (var i = 0; i < listenQuestionsData.length; i++) {
            final q = listenQuestionsData[i] as Map<String, dynamic>;
            listeningQuestions.add(ListeningQuestion(
              id: 'lq_${index}_$i',
              question: q['question'] as String? ?? '',
              options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
              correctAnswer: q['correct_answer'] as String? ?? '',
              timestampSeconds: q['timestamp_seconds'] as int? ?? q['timestamp'] as int?,
            ));
          }
        }
        
        // If no questions array, create questions based on the topic
        if (listeningQuestions.isEmpty) {
          // Create at least 2 questions
          listeningQuestions.add(ListeningQuestion(
            id: 'lq_${index}_0',
            question: question.isNotEmpty 
                ? question 
                : 'What is the main topic of this conversation?',
            options: options.isNotEmpty 
                ? options 
                : [topic, 'Weather', 'Sports', 'Travel'],
            correctAnswer: correctAnswer.isNotEmpty ? correctAnswer : topic,
          ));
          
          listeningQuestions.add(ListeningQuestion(
            id: 'lq_${index}_1',
            question: 'What can you learn from this?',
            options: ['New vocabulary', 'History facts', 'Science concepts', 'Math formulas'],
            correctAnswer: 'New vocabulary',
          ));
        }
        
        // Generate transcript if not available
        final listeningTranscript = transcript.isNotEmpty 
            ? transcript 
            : explanation.isNotEmpty 
                ? explanation 
                : _generateListeningTranscript(topic, level);
        
        return ListeningExercise(
          id: id,
          title: '$topic Listening',
          description: 'Read the transcript and answer the comprehension questions',
          level: level,
          estimatedDurationMinutes: 5,
          points: points,
          tags: [skillType, 'cached'],
          audioUrl: audioUrl,
          transcript: listeningTranscript,
          questions: listeningQuestions,
          durationSeconds: 60,
        );
      case 'speaking':
        final rawKeywords = data['keywords'];
        final parsedKeywords = rawKeywords is List
            ? rawKeywords.map((e) => e.toString().trim()).where((e) => e.isNotEmpty).toList()
            : <String>[];

        final referenceText = (data['reference_text'] as String? ??
                data['sentence'] as String? ??
                data['text'] as String? ??
                data['prompt'] as String? ??
                question)
            .trim();

        final sampleResponse = (data['sample_response'] as String? ?? '').trim();
        final customTitle = (data['title'] as String? ?? '').trim();

        final resolvedPrompt = normalizeReadAloudSentence(
          referenceText.isNotEmpty
              ? referenceText
              : (sampleResponse.isNotEmpty ? sampleResponse : 'I am practicing my English speaking skills today'),
        );

        // Keep only single-word keywords to avoid showing broken "sentences" built from phrases.
        final cleanKeywords = parsedKeywords.where((k) => !k.contains(' ')).take(6).toList();

        return SpeakingExercise(
          id: id,
          title: customTitle.isNotEmpty ? customTitle : '$topic Speaking',
          description: 'Read the sentence aloud and get pronunciation feedback',
          level: level,
          estimatedDurationMinutes: 4,
          points: points,
          tags: [skillType, 'cached'],
          prompt: resolvedPrompt,
          keyWords: cleanKeywords,
          speakingType: SpeakingExerciseType.pronunciation,
          maxRecordingSeconds: 60, // Allow up to 60 seconds for speaking practice
          imageUrl: data['image_url'] as String?,
        );
      case 'writing':
        // Extract keywords from options or generate topic-related keywords
        final writingKeywords = options.isNotEmpty 
            ? options 
            : _generateWritingKeywords(topic, correctAnswer);
        return WritingExercise(
          id: id,
          title: '$topic Writing',
          description: 'Practice your writing skills on this topic',
          level: level,
          estimatedDurationMinutes: 10,
          points: points,
          tags: [skillType, 'cached'],
          prompt: question.isNotEmpty 
              ? question 
              : 'Write a paragraph about "$topic". Express your thoughts clearly using the suggested keywords below.',
          guidelines: [
            'Write at least 50 words',
            'Use complete sentences with proper grammar',
            'Try to include the suggested keywords in your writing',
            'Check your spelling and punctuation',
          ],
          minWords: 50,
          maxWords: 200,
          writingType: WritingType.description,
          keyWords: writingKeywords,
        );
      case 'grammar':
      default:
        return GrammarExercise(
          id: id,
          title: '$topic Grammar',
          description: 'Practice grammar patterns',
          level: level,
          estimatedDurationMinutes: 5,
          points: points,
          tags: [skillType, 'cached'],
          grammarRule: topic,
          explanation: explanation,
          questions: [
            GrammarQuestion(
              id: 'q_$index',
              question: question,
              options: options,
              correctAnswer: correctAnswer,
              explanation: explanation,
            ),
          ],
        );
    }
  }

  /// Generate writing keywords based on topic and context
  List<String> _generateWritingKeywords(String topic, String context) {
    final keywords = <String>[];
    
    // Add topic-related words
    final topicWords = topic.toLowerCase().split(' ').where((w) => w.length > 3).toList();
    keywords.addAll(topicWords.take(2));
    
    // Add context-related words if available
    if (context.isNotEmpty) {
      final contextWords = context.toLowerCase().split(' ').where((w) => w.length > 4).toList();
      keywords.addAll(contextWords.take(2));
    }
    
    // Add common useful writing words based on topic category
    final topicLower = topic.toLowerCase();
    if (topicLower.contains('food') || topicLower.contains('eat')) {
      keywords.addAll(['delicious', 'taste', 'favorite', 'healthy']);
    } else if (topicLower.contains('travel') || topicLower.contains('trip')) {
      keywords.addAll(['adventure', 'experience', 'discover', 'beautiful']);
    } else if (topicLower.contains('family') || topicLower.contains('friend')) {
      keywords.addAll(['together', 'happy', 'special', 'important']);
    } else if (topicLower.contains('work') || topicLower.contains('job')) {
      keywords.addAll(['important', 'successful', 'challenge', 'opportunity']);
    } else if (topicLower.contains('hobby') || topicLower.contains('free time')) {
      keywords.addAll(['enjoy', 'relaxing', 'interesting', 'passion']);
    } else {
      // Default useful writing words
      keywords.addAll(['important', 'interesting', 'believe', 'example']);
    }
    
    // Remove duplicates and return unique keywords
    return keywords.toSet().take(6).toList();
  }

  /// Generate a listening transcript based on topic and level
  String _generateListeningTranscript(String topic, DifficultyLevel level) {
    final topicCapitalized = topic.isNotEmpty 
        ? topic[0].toUpperCase() + topic.substring(1).toLowerCase()
        : 'This topic';
    
    switch (level) {
      case DifficultyLevel.a1:
        return '''Hello! Today we talk about $topicCapitalized.

$topicCapitalized is very interesting. Many people like it.

Let's learn some new words about $topicCapitalized.

Thank you for listening!''';
      
      case DifficultyLevel.a2:
        return '''Welcome to today's lesson about $topicCapitalized.

$topicCapitalized is an important topic to understand. In this lesson, you will learn new vocabulary and useful phrases.

First, let's look at some basic concepts. $topicCapitalized can be found in many places around us.

I hope you enjoy learning about $topicCapitalized. Let's continue with some questions.''';
      
      case DifficultyLevel.b1:
        return '''Good morning everyone. Today we're going to explore $topicCapitalized in more detail.

$topicCapitalized has become increasingly relevant in our daily lives. Understanding this topic can help you communicate more effectively in English.

There are several key aspects to consider when we talk about $topicCapitalized. Let me explain each of them briefly.

First, it's important to understand the basic concepts. Second, we need to look at how it affects us personally. Finally, we should consider its broader implications.

Now let's move on to some comprehension questions to test your understanding.''';
      
      case DifficultyLevel.b2:
      case DifficultyLevel.c1:
      case DifficultyLevel.c2:
        return '''Hello and welcome to today's discussion about $topicCapitalized.

$topicCapitalized represents a fascinating area of study that has garnered significant attention in recent years. Understanding this subject matter will enhance your ability to engage in meaningful conversations and express complex ideas in English.

Throughout this session, we'll examine various perspectives on $topicCapitalized, analyzing both its advantages and potential challenges. We'll also explore how different cultures approach this topic and what we can learn from diverse viewpoints.

It's worth noting that $topicCapitalized continues to evolve, and staying informed about the latest developments can be beneficial for both personal and professional growth.

Let me now present some thought-provoking questions to assess your comprehension and critical thinking skills.''';
    }
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
}

// ============ MICRO LESSON RESULT ============

class MicroLessonResult {
  final bool success;
  final String source;
  final Map<String, dynamic>? content;
  final List<Map<String, dynamic>> exercises;
  final String? message;

  MicroLessonResult({
    required this.success,
    required this.source,
    this.content,
    required this.exercises,
    this.message,
  });

  factory MicroLessonResult.fromJson(Map<String, dynamic> json) {
    return MicroLessonResult(
      success: json['success'] as bool? ?? false,
      source: json['source'] as String? ?? 'unknown',
      content: json['content'] as Map<String, dynamic>?,
      exercises: (json['exercises'] as List?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          [],
      message: json['message'] as String?,
    );
  }

  factory MicroLessonResult.empty() {
    return MicroLessonResult(
      success: false,
      source: 'none',
      exercises: [],
    );
  }

  bool get hasExercises => exercises.isNotEmpty;

  List<Exercise> toExercises(String skillType) {
    final result = <Exercise>[];
    final level = _parseDifficultyLevel(content?['level'] as String? ?? 'B1');
    final topic = content?['topic'] as String? ?? 'Quick Practice';
    final id = 'micro_${DateTime.now().millisecondsSinceEpoch}';

    // Handle reading exercises - backend returns single object with text + questions
    if (skillType.toLowerCase() == 'reading') {
      // Check if exercises has reading content (text + questions)
      for (final ex in exercises) {
        final text = ex['text'] as String? ?? '';
        final questionsData = ex['questions'] as List?;
          final exTitle = (ex['title'] as String? ?? '').trim();
          final exStyle = (ex['style'] as String? ?? '').trim();
        
        if (text.isNotEmpty && questionsData != null && questionsData.isNotEmpty) {
          final readingQuestions = <ReadingQuestion>[];
          for (var i = 0; i < questionsData.length; i++) {
            final q = questionsData[i] as Map<String, dynamic>;
            readingQuestions.add(ReadingQuestion(
              id: 'rq_$i',
              question: q['question'] as String? ?? '',
              options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
              correctAnswer: q['correct_answer'] as String? ?? '',
              type: ReadingQuestionType.multipleChoice,
            ));
          }
          
          result.add(ReadingExercise(
            id: id,
            title: exTitle.isNotEmpty ? exTitle : '$topic Reading',
            description: exStyle.isNotEmpty
                ? 'Read this $exStyle and answer the questions'
                : 'Read and answer comprehension questions',
            level: level,
            estimatedDurationMinutes: 8,
            points: ex['points'] as int? ?? 20,
            tags: [skillType, 'micro'],
            text: text,
            questions: readingQuestions,
            vocabularyHighlights: [],
            wordCount: text.split(' ').length,
          ));
          return result;
        }
      }
      
      // Fallback: Generate reading content from available data
      if (exercises.isNotEmpty) {
        final ex = exercises.first;
        final fallbackText = _generateReadingPassage(topic, level);
        result.add(ReadingExercise(
          id: id,
          title: '$topic Reading',
          description: 'Read and answer comprehension questions',
          level: level,
          estimatedDurationMinutes: 8,
          points: 20,
          tags: [skillType, 'micro'],
          text: fallbackText,
          questions: [
            ReadingQuestion(
              id: 'rq_0',
              question: ex['question'] as String? ?? 'What is the main idea of this passage?',
              options: (ex['options'] as List?)?.map((e) => e.toString()).toList() ?? [topic, 'Other topic', 'Different idea', 'None of above'],
              correctAnswer: ex['correct_answer'] as String? ?? topic,
              type: ReadingQuestionType.multipleChoice,
            ),
          ],
          vocabularyHighlights: [],
          wordCount: fallbackText.split(' ').length,
        ));
        return result;
      }
    }

    // Handle listening exercises - backend returns single object with transcript + questions
    if (skillType.toLowerCase() == 'listening') {
      for (final ex in exercises) {
        final transcript = ex['transcript'] as String? ?? '';
        final questionsData = ex['questions'] as List?;
        
        if (transcript.isNotEmpty && questionsData != null && questionsData.isNotEmpty) {
          final listeningQuestions = <ListeningQuestion>[];
          for (var i = 0; i < questionsData.length; i++) {
            final q = questionsData[i] as Map<String, dynamic>;
            listeningQuestions.add(ListeningQuestion(
              id: 'lq_$i',
              question: q['question'] as String? ?? '',
              options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
              correctAnswer: q['correct_answer'] as String? ?? '',
            ));
          }
          
          result.add(ListeningExercise(
            id: id,
            title: '$topic Listening',
            description: 'Listen and answer comprehension questions',
            level: level,
            estimatedDurationMinutes: 5,
            points: ex['points'] as int? ?? 20,
            tags: [skillType, 'micro'],
            audioUrl: '',
            transcript: transcript,
            questions: listeningQuestions,
            durationSeconds: 60,
          ));
          return result;
        }
      }
    }

    // Handle speaking exercises - backend returns object with question, keywords, sample_response
    if (skillType.toLowerCase() == 'speaking') {
      for (final ex in exercises) {
        final prompt = ex['question'] as String? ?? '';
        final keywords = (ex['keywords'] as List?)?.map((e) => e.toString()).toList() ?? [];
        final sampleResponse = ex['sample_response'] as String? ?? '';
        
        if (prompt.isNotEmpty) {
          result.add(SpeakingExercise(
            id: id,
            title: '$topic Speaking',
            description: sampleResponse.isNotEmpty 
                ? 'Practice: $sampleResponse' 
                : 'Practice your pronunciation and speaking',
            level: level,
            estimatedDurationMinutes: 5,
            points: ex['points'] as int? ?? 15,
            tags: [skillType, 'micro'],
            prompt: prompt,
            keyWords: keywords.isNotEmpty ? keywords : [topic],
            speakingType: SpeakingExerciseType.pronunciation,
            maxRecordingSeconds: 60,
          ));
          return result;
        }
      }
      
      // Fallback: Generate speaking content
      result.add(SpeakingExercise(
        id: id,
        title: '$topic Speaking',
        description: 'Practice your pronunciation and speaking skills',
        level: level,
        estimatedDurationMinutes: 5,
        points: 15,
        tags: [skillType, 'micro'],
        prompt: _generateSpeakingPrompt(topic, level),
        keyWords: [topic],
        speakingType: SpeakingExerciseType.pronunciation,
        maxRecordingSeconds: 60,
      ));
      return result;
    }

    // Handle writing exercises - backend returns object with question, guidelines, keywords
    if (skillType.toLowerCase() == 'writing') {
      for (final ex in exercises) {
        final prompt = ex['question'] as String? ?? '';
        final guidelines = (ex['guidelines'] as List?)?.map((e) => e.toString()).toList() ?? [];
        final keywords = (ex['keywords'] as List?)?.map((e) => e.toString()).toList() ?? [];
        final minWords = ex['min_words'] as int? ?? 50;
        final maxWords = ex['max_words'] as int? ?? 200;
        
        if (prompt.isNotEmpty) {
          result.add(WritingExercise(
            id: id,
            title: '$topic Writing',
            description: 'Practice your writing skills',
            level: level,
            estimatedDurationMinutes: 10,
            points: ex['points'] as int? ?? 25,
            tags: [skillType, 'micro'],
            prompt: prompt,
            guidelines: guidelines.isNotEmpty ? guidelines : [
              'Write at least $minWords words',
              'Use complete sentences',
              'Check your grammar and spelling',
            ],
            minWords: minWords,
            maxWords: maxWords,
            writingType: WritingType.description,
            keyWords: keywords,
          ));
          return result;
        }
      }
    }

    // For grammar micro-lessons, group multiple items into ONE exercise
    // so the UI doesn't show the same title multiple times.
    if (skillType.toLowerCase() == 'grammar' && exercises.isNotEmpty) {
      final questions = <GrammarQuestion>[];
      var totalPoints = 0;

      for (var i = 0; i < exercises.length; i++) {
        final ex = exercises[i];
        final questionText = ex['question'] as String? ?? '';
        if (questionText.trim().isEmpty) continue;

        final options = (ex['options'] as List?)?.map((e) => e.toString()).toList() ?? [];
        final correctAnswer = ex['correct_answer'] as String? ?? '';
        final explanation = ex['explanation'] as String? ?? '';
        final points = ex['points'] as int? ?? 10;

        totalPoints += points;
        questions.add(GrammarQuestion(
          id: 'q_$i',
          question: questionText,
          options: options,
          correctAnswer: correctAnswer,
          explanation: explanation,
        ));
      }

      if (questions.isNotEmpty) {
        result.add(GrammarExercise(
          id: id,
          title: '$topic Grammar',
          description: 'Quick grammar practice',
          level: level,
          estimatedDurationMinutes: 3,
          points: totalPoints > 0 ? totalPoints : (questions.length * 10),
          tags: [skillType, 'micro'],
          grammarRule: topic,
          explanation: '',
          questions: questions,
        ));
      }

      return result;
    }

    for (var i = 0; i < exercises.length; i++) {
      final ex = exercises[i];
      result.add(_parseExercise(ex, skillType, level, topic, i));
    }

    return result;
  }

  Exercise _parseExercise(
    Map<String, dynamic> data,
    String skillType,
    DifficultyLevel level,
    String topic,
    int index,
  ) {
    final id = 'micro_${DateTime.now().millisecondsSinceEpoch}_$index';
    final question = data['question'] as String? ?? '';
    final options = (data['options'] as List?)?.map((e) => e.toString()).toList() ?? [];
    final correctAnswer = data['correct_answer'] as String? ?? '';
    final explanation = data['explanation'] as String? ?? '';
    final points = data['points'] as int? ?? 10;
    final text = data['text'] as String? ?? data['passage'] as String? ?? '';
    final audioUrl = data['audio_url'] as String? ?? '';
    final transcript = data['transcript'] as String? ?? '';

    switch (skillType.toLowerCase()) {
      case 'vocabulary':
        final wordText = (data['word'] as String? ?? '').trim();
        final definitionText = (data['definition'] as String? ?? '').trim();
        final exampleSentenceText = (data['example_sentence'] as String? ?? data['example'] as String? ?? '').trim();
        final pronunciationText = (data['pronunciation'] as String? ?? '').trim();
        final synonyms = (data['synonyms'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
        final antonyms = (data['antonyms'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];

        final prompt = question.trim();
        final correct = (correctAnswer.isNotEmpty ? correctAnswer : definitionText).trim();

        String displayWord = wordText;
        if (displayWord.isEmpty) {
          final quoted = RegExp(r"'([^']+)'").firstMatch(prompt) ?? RegExp(r'"([^"]+)"').firstMatch(prompt);
          displayWord = (quoted?.group(1) ?? '').trim();
        }
        if (displayWord.isEmpty) displayWord = prompt.isNotEmpty ? prompt : 'Vocabulary';

        return VocabularyExercise(
          id: id,
          title: '$topic Vocabulary',
          description: prompt.isNotEmpty ? prompt : 'Quick vocabulary practice',
          level: level,
          estimatedDurationMinutes: 3,
          points: points,
          tags: [skillType, 'micro'],
          words: [
            VocabularyWord(
              word: displayWord,
              definition: definitionText.isNotEmpty ? definitionText : correct,
              pronunciation: pronunciationText,
              exampleSentence: exampleSentenceText.isNotEmpty ? exampleSentenceText : explanation,
              synonyms: synonyms,
              antonyms: antonyms,
              question: prompt.isNotEmpty ? prompt : null,
              options: options,
              correctAnswer: correct.isNotEmpty ? correct : null,
            ),
          ],
          exerciseType: VocabularyExerciseType.multipleChoice,
        );

      case 'reading':
        // For reading, we need a passage text
        final readingText = text.isNotEmpty 
            ? text 
            : explanation.isNotEmpty 
                ? explanation 
                : _generateReadingPassage(topic, level);
        
        return ReadingExercise(
          id: id,
          title: '$topic Reading',
          description: 'Read and answer comprehension questions',
          level: level,
          estimatedDurationMinutes: 5,
          points: points,
          tags: [skillType, 'micro'],
          text: readingText,
          questions: [
            ReadingQuestion(
              id: 'rq_$index',
              question: question.isNotEmpty ? question : 'What is the main idea of this passage?',
              options: options.isNotEmpty ? options : [topic, 'Other topic', 'Different idea', 'None of the above'],
              correctAnswer: correctAnswer.isNotEmpty ? correctAnswer : topic,
              type: ReadingQuestionType.multipleChoice,
            ),
          ],
          vocabularyHighlights: [],
          wordCount: readingText.split(' ').length,
        );

      case 'listening':
        final listeningTranscript = transcript.isNotEmpty 
            ? transcript 
            : text.isNotEmpty 
                ? text 
                : _generateListeningTranscript(topic, level);
        
        return ListeningExercise(
          id: id,
          title: '$topic Listening',
          description: 'Listen and answer questions',
          level: level,
          estimatedDurationMinutes: 5,
          points: points,
          tags: [skillType, 'micro'],
          audioUrl: audioUrl,
          transcript: listeningTranscript,
          questions: [
            ListeningQuestion(
              id: 'lq_$index',
              question: question.isNotEmpty ? question : 'What is the speaker talking about?',
              options: options.isNotEmpty ? options : [topic, 'Weather', 'Sports', 'Travel'],
              correctAnswer: correctAnswer.isNotEmpty ? correctAnswer : topic,
            ),
          ],
          durationSeconds: 60,
        );

      case 'speaking':
        return SpeakingExercise(
          id: id,
          title: '$topic Speaking',
          description: 'Practice your pronunciation',
          level: level,
          estimatedDurationMinutes: 3,
          points: points,
          tags: [skillType, 'micro'],
          prompt: question.isNotEmpty ? question : 'Practice speaking about $topic.',
          keyWords: options.isNotEmpty ? options : [correctAnswer],
          speakingType: SpeakingExerciseType.pronunciation,
          maxRecordingSeconds: 60,
        );

      case 'writing':
        return WritingExercise(
          id: id,
          title: '$topic Writing',
          description: 'Practice your writing skills',
          level: level,
          estimatedDurationMinutes: 10,
          points: points,
          tags: [skillType, 'micro'],
          prompt: question.isNotEmpty ? question : 'Write a paragraph about $topic.',
          guidelines: [
            'Write at least 50 words',
            'Use complete sentences',
            'Check your grammar and spelling',
          ],
          minWords: 50,
          maxWords: 200,
          writingType: WritingType.description,
          keyWords: options.isNotEmpty ? options : [],
        );

      case 'grammar':
      default:
        return GrammarExercise(
          id: id,
          title: '$topic Grammar',
          description: 'Quick grammar practice',
          level: level,
          estimatedDurationMinutes: 3,
          points: points,
          tags: [skillType, 'micro'],
          grammarRule: topic,
          explanation: '',
          questions: [
            GrammarQuestion(
              id: 'q_$index',
              question: question,
              options: options,
              correctAnswer: correctAnswer,
              explanation: explanation,
            ),
          ],
        );
    }
  }

  /// Generate a reading passage based on topic and level
  String _generateReadingPassage(String topic, DifficultyLevel level) {
    final topicCapitalized = topic.isNotEmpty 
        ? topic[0].toUpperCase() + topic.substring(1).toLowerCase()
        : 'This topic';
    
    switch (level) {
      case DifficultyLevel.a1:
        return '''$topicCapitalized is interesting. Many people like $topicCapitalized.

It is good to learn about $topicCapitalized. You can read books about it. You can also watch videos.

$topicCapitalized helps us learn new things. It is fun to explore.''';
      
      case DifficultyLevel.a2:
        return '''$topicCapitalized is an interesting subject that many people enjoy learning about.

There are many ways to learn about $topicCapitalized. You can read books, watch videos, or talk to experts. Each method has its own benefits.

Learning about $topicCapitalized can help you understand the world better. It can also be a fun hobby to explore in your free time.''';
      
      case DifficultyLevel.b1:
      case DifficultyLevel.b2:
        return '''$topicCapitalized has become increasingly important in today's world. Many people are interested in learning more about this subject and its various applications.

There are numerous resources available for those who want to explore $topicCapitalized further. Books, online courses, and educational videos provide excellent starting points for beginners. More advanced learners can attend workshops or join discussion groups.

Understanding $topicCapitalized can open up new opportunities and perspectives. It helps develop critical thinking skills and encourages lifelong learning. Whether you're a student or a professional, this knowledge can be valuable in many areas of life.''';
      
      case DifficultyLevel.c1:
      case DifficultyLevel.c2:
        return '''$topicCapitalized represents a fascinating area of study that has garnered significant attention in recent years. Scholars and practitioners alike have contributed to a growing body of knowledge that continues to evolve.

The complexities inherent in $topicCapitalized require a nuanced understanding of various interconnected factors. Theoretical frameworks provide a foundation for analysis, while empirical research offers practical insights into real-world applications.

As our understanding of $topicCapitalized deepens, new questions emerge that challenge conventional thinking. This dynamic nature ensures that the field remains vibrant and intellectually stimulating for researchers and enthusiasts alike.''';
    }
  }

  /// Generate a listening transcript based on topic and level  
  String _generateListeningTranscript(String topic, DifficultyLevel level) {
    final topicCapitalized = topic.isNotEmpty 
        ? topic[0].toUpperCase() + topic.substring(1).toLowerCase()
        : 'This topic';
    
    switch (level) {
      case DifficultyLevel.a1:
        return '''Hello! Today we talk about $topicCapitalized.

$topicCapitalized is very interesting. Many people like it.

Let's learn some new words about $topicCapitalized.

Thank you for listening!''';
      
      case DifficultyLevel.a2:
        return '''Welcome to today's lesson about $topicCapitalized.

$topicCapitalized is a topic that many people find interesting. There are many things to learn about it.

First, let's understand what $topicCapitalized means. Then we will look at some examples.

I hope you enjoy learning about $topicCapitalized today!''';
      
      case DifficultyLevel.b1:
      case DifficultyLevel.b2:
        return '''Good morning everyone! Today we're going to explore the fascinating topic of $topicCapitalized.

$topicCapitalized is something that affects our daily lives in many ways. Understanding it better can help us make informed decisions.

Throughout this lesson, we'll examine different aspects of $topicCapitalized and discuss how it relates to the world around us.

Let's begin by looking at some key concepts and then move on to practical examples.''';
      
      case DifficultyLevel.c1:
      case DifficultyLevel.c2:
        return '''Welcome to this comprehensive discussion on $topicCapitalized.

In today's session, we'll delve into the multifaceted nature of $topicCapitalized, examining both its theoretical underpinnings and practical implications.

The significance of understanding $topicCapitalized cannot be overstated, particularly in our rapidly evolving global context.

We'll analyze various perspectives and consider how different stakeholders approach this subject.''';
    }
  }

  /// Generate a speaking prompt based on topic and level
  String _generateSpeakingPrompt(String topic, DifficultyLevel level) {
    final topicCapitalized = topic.isNotEmpty 
        ? topic[0].toUpperCase() + topic.substring(1).toLowerCase()
        : 'this topic';
    
    switch (level) {
      case DifficultyLevel.a1:
        return 'Say this sentence: "I like $topicCapitalized."';
      case DifficultyLevel.a2:
        return 'Practice saying: "$topicCapitalized is interesting. I want to learn more about it."';
      case DifficultyLevel.b1:
      case DifficultyLevel.b2:
        return 'Describe $topicCapitalized in 2-3 sentences. What do you think about it?';
      case DifficultyLevel.c1:
      case DifficultyLevel.c2:
        return 'Share your opinion about $topicCapitalized. Explain why it is important and give examples.';
    }
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
}

// Data Models for API responses
class ExerciseData {
  final int id;
  final String title;
  final String description;
  final String exerciseType;
  final String difficultyLevel;
  final String question;
  final List<String>? options;
  final String? audioUrl;
  final String? imageUrl;
  final int points;
  final int? timeLimitSeconds;
  final bool isActive;
  final Map<String, dynamic>? correctAnswer;
  final String? explanation;
  final Map<String, dynamic>? metadata;

  ExerciseData({
    required this.id,
    required this.title,
    required this.description,
    required this.exerciseType,
    required this.difficultyLevel,
    required this.question,
    this.options,
    this.audioUrl,
    this.imageUrl,
    required this.points,
    this.timeLimitSeconds,
    this.isActive = true,
    this.correctAnswer,
    this.explanation,
    this.metadata,
  });

  factory ExerciseData.fromJson(Map<String, dynamic> json) {
    // Backend `/exercises/` returns `options` as a JSON object (Map), not a List.
    // Normalize it into a List<String> for the UI models.
    final rawOptions = json['options'];
    List<String>? parsedOptions;
    if (rawOptions is List) {
      parsedOptions = rawOptions.map((e) => e.toString()).toList();
    } else if (rawOptions is Map) {
      final mapOptions = Map<String, dynamic>.from(rawOptions);
      final inner = mapOptions['options'] ?? mapOptions['choices'] ?? mapOptions['items'];
      if (inner is List) {
        parsedOptions = inner.map((e) => e.toString()).toList();
      } else if (inner is Map) {
        parsedOptions = Map<String, dynamic>.from(inner).values.map((e) => e.toString()).toList();
      } else {
        parsedOptions = mapOptions.values.map((e) => e.toString()).toList();
      }
    }

    // Some endpoints may return `correct_answer` as a string; normalize to Map.
    final rawCorrectAnswer = json['correct_answer'];
    Map<String, dynamic>? parsedCorrectAnswer;
    if (rawCorrectAnswer is Map<String, dynamic>) {
      parsedCorrectAnswer = rawCorrectAnswer;
    } else if (rawCorrectAnswer is Map) {
      parsedCorrectAnswer = Map<String, dynamic>.from(rawCorrectAnswer);
    } else if (rawCorrectAnswer is String) {
      parsedCorrectAnswer = {'text': rawCorrectAnswer};
    } else if (rawCorrectAnswer != null) {
      parsedCorrectAnswer = {'text': rawCorrectAnswer.toString()};
    }

    return ExerciseData(
      id: json['id'] ?? 0,
      title: json['title'] ?? '',
      description: json['description'] ?? '',
      exerciseType: json['exercise_type'] ?? 'multiple_choice',
      difficultyLevel: json['difficulty_level'] ?? 'A1',
      question: json['question'] ?? '',
      options: parsedOptions,
      audioUrl: json['audio_url'],
      imageUrl: json['image_url'],
      points: json['points'] ?? 10,
      timeLimitSeconds: json['time_limit_seconds'],
      isActive: json['is_active'] ?? true,
      correctAnswer: parsedCorrectAnswer,
      explanation: json['explanation'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  // Convert to Exercise model for UI
  Exercise toExercise() {
    final type = _parseExerciseType(exerciseType);
    final level = _parseDifficultyLevel(difficultyLevel);
    final duration = timeLimitSeconds != null ? (timeLimitSeconds! ~/ 60).clamp(1, 30) : 5;

    switch (type) {
      case ExerciseType.vocabulary:
        return _createVocabularyExercise(level, duration);
      case ExerciseType.grammar:
        return _createGrammarExercise(level, duration);
      case ExerciseType.reading:
        return _createReadingExercise(level, duration);
      case ExerciseType.listening:
        return _createListeningExercise(level, duration);
      case ExerciseType.speaking:
        return _createSpeakingExercise(level, duration);
      case ExerciseType.writing:
        return _createWritingExercise(level, duration);
      default:
        return _createGrammarExercise(level, duration);
    }
  }

  VocabularyExercise _createVocabularyExercise(DifficultyLevel level, int duration) {
    // Parse words from metadata or create from question/options
    final words = <VocabularyWord>[];
    
    if (metadata != null && metadata!['words'] != null) {
      for (final w in (metadata!['words'] as List)) {
        if (w is Map<String, dynamic>) {
          final wQuestion = (w['question'] as String?)?.trim();
          final wOptions = (w['options'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[];
          final wCorrect = (w['correct_answer'] as String?)?.trim();
          final wExample = (w['example_sentence'] as String? ?? w['example'] as String? ?? '').trim();

          words.add(VocabularyWord(
            word: w['word'] as String? ?? '',
            definition: w['definition'] as String? ?? w['meaning'] as String? ?? '',
            pronunciation: w['pronunciation'] as String? ?? '',
            exampleSentence: wExample,
            synonyms: (w['synonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
            antonyms: (w['antonyms'] as List?)?.map((e) => e.toString()).toList() ?? [],
            question: wQuestion,
            options: wOptions,
            correctAnswer: wCorrect,
          ));
        }
      }
    }

    // If no words from metadata, create from question
    if (words.isEmpty && question.isNotEmpty) {
      // For `/exercises/` practice responses, the backend does not include the correct answer.
      // Treat the item as a multiple-choice prompt with options and resolve correctness via submit.
      final prompt = question.trim();
      String displayWord = '';
      final quoted = RegExp(r"'([^']+)'").firstMatch(prompt) ?? RegExp(r'"([^"]+)"').firstMatch(prompt);
      displayWord = (quoted?.group(1) ?? '').trim();
      if (displayWord.isEmpty && !prompt.contains(' ') && prompt.length <= 30) {
        displayWord = prompt;
      }
      if (displayWord.isEmpty) displayWord = title.isNotEmpty ? title : 'Vocabulary';

      words.add(VocabularyWord(
        word: displayWord,
        definition: '',
        pronunciation: '',
        exampleSentence: '',
        question: prompt.isNotEmpty ? prompt : null,
        options: options ?? const <String>[],
      ));
    }

    return VocabularyExercise(
      id: id.toString(),
      title: title.isNotEmpty ? title : 'Vocabulary Practice',
      description: description.isNotEmpty ? description : 'Learn new vocabulary words',
      level: level,
      estimatedDurationMinutes: duration,
      points: points,
      tags: ['vocabulary'],
      words: words,
      exerciseType: VocabularyExerciseType.multipleChoice,
    );
  }

  GrammarExercise _createGrammarExercise(DifficultyLevel level, int duration) {
    final questions = <GrammarQuestion>[];

    // Parse questions from metadata or create from current data
    if (metadata != null && metadata!['questions'] != null) {
      final questionsData = metadata!['questions'] as List;
      for (var i = 0; i < questionsData.length; i++) {
        final q = questionsData[i];
        if (q is Map<String, dynamic>) {
          questions.add(GrammarQuestion(
            id: q['id']?.toString() ?? 'q_$i',
            question: q['question'] as String? ?? '',
            options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
            correctAnswer: q['correct_answer'] as String? ?? '',
            explanation: q['explanation'] as String? ?? '',
          ));
        }
      }
    }

    // If no questions from metadata, create from current data
    if (questions.isEmpty && question.isNotEmpty) {
      final correctOpt = correctAnswer?['correct_option'] as String? ??
          correctAnswer?['text'] as String? ??
          (options?.isNotEmpty == true ? options!.first : '');

      questions.add(GrammarQuestion(
        id: '1',
        question: question,
        options: options ?? [],
        correctAnswer: correctOpt,
        explanation: explanation ?? '',
      ));
    }

    return GrammarExercise(
      id: id.toString(),
      title: title.isNotEmpty ? title : 'Grammar Practice',
      description: description.isNotEmpty ? description : 'Practice grammar patterns',
      level: level,
      estimatedDurationMinutes: duration,
      points: points,
      tags: ['grammar'],
      grammarRule: metadata?['grammar_rule'] as String? ?? '',
      explanation: explanation ?? metadata?['explanation'] as String? ?? '',
      questions: questions,
    );
  }

  ReadingExercise _createReadingExercise(DifficultyLevel level, int duration) {
    final questions = <ReadingQuestion>[];
    final text = metadata?['text'] as String? ?? description;

    if (metadata != null && metadata!['questions'] != null) {
      for (var i = 0; i < (metadata!['questions'] as List).length; i++) {
        final q = (metadata!['questions'] as List)[i];
        if (q is Map<String, dynamic>) {
          questions.add(ReadingQuestion(
            id: q['id']?.toString() ?? 'q_$i',
            question: q['question'] as String? ?? '',
            options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
            correctAnswer: q['correct_answer'] as String? ?? '',
            type: ReadingQuestionType.multipleChoice,
          ));
        }
      }
    }

    if (questions.isEmpty && question.isNotEmpty) {
      questions.add(ReadingQuestion(
        id: '1',
        question: question,
        options: options ?? [],
        correctAnswer: correctAnswer?['correct_option'] as String? ?? '',
        type: ReadingQuestionType.multipleChoice,
      ));
    }

    return ReadingExercise(
      id: id.toString(),
      title: title.isNotEmpty ? title : 'Reading Comprehension',
      description: description,
      level: level,
      estimatedDurationMinutes: duration,
      points: points,
      tags: ['reading'],
      text: text,
      questions: questions,
      vocabularyHighlights: [],
      wordCount: text.split(' ').length,
    );
  }

  ListeningExercise _createListeningExercise(DifficultyLevel level, int duration) {
    final questions = <ListeningQuestion>[];

    if (metadata != null && metadata!['questions'] != null) {
      for (var i = 0; i < (metadata!['questions'] as List).length; i++) {
        final q = (metadata!['questions'] as List)[i];
        if (q is Map<String, dynamic>) {
          questions.add(ListeningQuestion(
            id: q['id']?.toString() ?? 'q_$i',
            question: q['question'] as String? ?? '',
            options: (q['options'] as List?)?.map((e) => e.toString()).toList() ?? [],
            correctAnswer: q['correct_answer'] as String? ?? '',
          ));
        }
      }
    }

    if (questions.isEmpty && question.isNotEmpty) {
      questions.add(ListeningQuestion(
        id: '1',
        question: question,
        options: options ?? [],
        correctAnswer: correctAnswer?['correct_option'] as String? ?? '',
      ));
    }

    return ListeningExercise(
      id: id.toString(),
      title: title.isNotEmpty ? title : 'Listening Practice',
      description: description,
      level: level,
      estimatedDurationMinutes: duration,
      points: points,
      tags: ['listening'],
      audioUrl: audioUrl ?? '',
      transcript: metadata?['transcript'] as String? ?? '',
      questions: questions,
      durationSeconds: timeLimitSeconds ?? 120,
    );
  }

  SpeakingExercise _createSpeakingExercise(DifficultyLevel level, int duration) {
    return SpeakingExercise(
      id: id.toString(),
      title: title.isNotEmpty ? title : 'Speaking Practice',
      description: description,
      level: level,
      estimatedDurationMinutes: duration,
      points: points,
      tags: ['speaking'],
      prompt: question.isNotEmpty ? question : description,
      keyWords: (metadata?['keywords'] as List?)?.map((e) => e.toString()).toList() ?? [],
      speakingType: SpeakingExerciseType.conversation,
      maxRecordingSeconds: timeLimitSeconds ?? 60,
      sampleAudioUrl: audioUrl,
    );
  }

  WritingExercise _createWritingExercise(DifficultyLevel level, int duration) {
    return WritingExercise(
      id: id.toString(),
      title: title.isNotEmpty ? title : 'Writing Practice',
      description: description,
      level: level,
      estimatedDurationMinutes: duration,
      points: points,
      tags: ['writing'],
      prompt: question.isNotEmpty ? question : description,
      guidelines: (metadata?['guidelines'] as List?)?.map((e) => e.toString()).toList() ?? [],
      minWords: metadata?['min_words'] as int? ?? 50,
      maxWords: metadata?['max_words'] as int? ?? 200,
      writingType: WritingType.essay,
      keyWords: (metadata?['keywords'] as List?)?.map((e) => e.toString()).toList() ?? [],
    );
  }

  ExerciseType _parseExerciseType(String type) {
    switch (type.toLowerCase()) {
      case 'vocabulary':
      case 'multiple_choice':
        return ExerciseType.vocabulary;
      case 'grammar':
      case 'fill_blank':
        return ExerciseType.grammar;
      case 'reading':
        return ExerciseType.reading;
      case 'listening':
        return ExerciseType.listening;
      case 'speaking':
        return ExerciseType.speaking;
      case 'writing':
        return ExerciseType.writing;
      default:
        return ExerciseType.vocabulary;
    }
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
        return DifficultyLevel.a1;
    }
  }
}

class ExerciseSubmissionResult {
  final bool isCorrect;
  final double score;
  final int pointsEarned;
  final Map<String, dynamic>? correctAnswer;
  final String? explanation;
  final String? aiFeedback;
  final String? error;

  ExerciseSubmissionResult({
    required this.isCorrect,
    required this.score,
    required this.pointsEarned,
    this.correctAnswer,
    this.explanation,
    this.aiFeedback,
    this.error,
  });

  factory ExerciseSubmissionResult.fromJson(Map<String, dynamic> json) {
    return ExerciseSubmissionResult(
      isCorrect: json['is_correct'] ?? false,
      score: (json['score'] ?? 0.0).toDouble(),
      pointsEarned: json['points_earned'] ?? 0,
      correctAnswer: json['correct_answer'],
      explanation: json['explanation'],
      aiFeedback: json['ai_feedback'],
    );
  }

  factory ExerciseSubmissionResult.error(String message) {
    return ExerciseSubmissionResult(
      isCorrect: false,
      score: 0,
      pointsEarned: 0,
      error: message,
    );
  }
}

class ExerciseAttemptData {
  final int id;
  final int exerciseId;
  final Map<String, dynamic> userAnswer;
  final bool isCorrect;
  final double score;
  final int? timeTakenSeconds;
  final String? aiFeedback;
  final DateTime attemptedAt;

  ExerciseAttemptData({
    required this.id,
    required this.exerciseId,
    required this.userAnswer,
    required this.isCorrect,
    required this.score,
    this.timeTakenSeconds,
    this.aiFeedback,
    required this.attemptedAt,
  });

  factory ExerciseAttemptData.fromJson(Map<String, dynamic> json) {
    return ExerciseAttemptData(
      id: json['id'] ?? 0,
      exerciseId: json['exercise_id'] ?? 0,
      userAnswer: json['user_answer'] ?? {},
      isCorrect: json['is_correct'] ?? false,
      score: (json['score'] ?? 0.0).toDouble(),
      timeTakenSeconds: json['time_taken_seconds'],
      aiFeedback: json['ai_feedback'],
      attemptedAt:
          DateTime.tryParse(json['attempted_at']?.toString() ?? '')?.toLocal() ??
              DateTime.now(),
    );
  }
}

class ExerciseStatisticsData {
  final int totalAttempts;
  final int correctAnswers;
  final double averageScore;
  final double averageTimeSeconds;
  final Map<String, int> exercisesByType;
  final Map<String, double> accuracyByType;

  ExerciseStatisticsData({
    required this.totalAttempts,
    required this.correctAnswers,
    required this.averageScore,
    required this.averageTimeSeconds,
    required this.exercisesByType,
    required this.accuracyByType,
  });

  factory ExerciseStatisticsData.fromJson(Map<String, dynamic> json) {
    return ExerciseStatisticsData(
      totalAttempts: json['total_attempts'] ?? 0,
      correctAnswers: json['correct_answers'] ?? 0,
      averageScore: (json['average_score'] ?? 0.0).toDouble(),
      averageTimeSeconds: (json['average_time_seconds'] ?? 0.0).toDouble(),
      exercisesByType: Map<String, int>.from(json['exercises_by_type'] ?? {}),
      accuracyByType: Map<String, double>.from(
        (json['accuracy_by_type'] ?? {}).map(
          (key, value) => MapEntry(key, (value as num).toDouble()),
        ),
      ),
    );
  }
}

class QuizData {
  final int id;
  final String title;
  final String? description;
  final String difficultyLevel;
  final int totalQuestions;
  final int totalPoints;
  final double passingScore;
  final int? timeLimitMinutes;
  final int maxAttempts;
  final bool isActive;

  QuizData({
    required this.id,
    required this.title,
    this.description,
    required this.difficultyLevel,
    required this.totalQuestions,
    required this.totalPoints,
    required this.passingScore,
    this.timeLimitMinutes,
    required this.maxAttempts,
    this.isActive = true,
  });

  factory QuizData.fromJson(Map<String, dynamic> json) {
    return QuizData(
      id: json['id'] ?? 0,
      title: json['title'] ?? '',
      description: json['description'],
      difficultyLevel: json['difficulty_level'] ?? 'A1',
      totalQuestions: json['total_questions'] ?? 0,
      totalPoints: json['total_points'] ?? 0,
      passingScore: (json['passing_score'] ?? 0.7).toDouble(),
      timeLimitMinutes: json['time_limit_minutes'],
      maxAttempts: json['max_attempts'] ?? 3,
      isActive: json['is_active'] ?? true,
    );
  }
}

class QuizWithExercises extends QuizData {
  final List<ExerciseData> exercises;

  QuizWithExercises({
    required super.id,
    required super.title,
    super.description,
    required super.difficultyLevel,
    required super.totalQuestions,
    required super.totalPoints,
    required super.passingScore,
    super.timeLimitMinutes,
    required super.maxAttempts,
    super.isActive,
    required this.exercises,
  });

  factory QuizWithExercises.fromJson(Map<String, dynamic> json) {
    return QuizWithExercises(
      id: json['id'] ?? 0,
      title: json['title'] ?? '',
      description: json['description'],
      difficultyLevel: json['difficulty_level'] ?? 'A1',
      totalQuestions: json['total_questions'] ?? 0,
      totalPoints: json['total_points'] ?? 0,
      passingScore: (json['passing_score'] ?? 0.7).toDouble(),
      timeLimitMinutes: json['time_limit_minutes'],
      maxAttempts: json['max_attempts'] ?? 3,
      isActive: json['is_active'] ?? true,
      exercises: (json['exercises'] as List? ?? [])
          .map((e) => ExerciseData.fromJson(e))
          .toList(),
    );
  }
}

class QuizAttemptData {
  final int id;
  final int quizId;
  final DateTime startedAt;
  final DateTime? completedAt;
  final double? score;
  final int? totalQuestions;
  final int? correctAnswers;
  final int? timeTakenMinutes;
  final bool? passed;

  QuizAttemptData({
    required this.id,
    required this.quizId,
    required this.startedAt,
    this.completedAt,
    this.score,
    this.totalQuestions,
    this.correctAnswers,
    this.timeTakenMinutes,
    this.passed,
  });

  factory QuizAttemptData.fromJson(Map<String, dynamic> json) {
    return QuizAttemptData(
      id: json['id'] ?? 0,
      quizId: json['quiz_id'] ?? 0,
      startedAt: DateTime.tryParse(json['started_at']?.toString() ?? '')?.toLocal() ??
          DateTime.now(),
      completedAt: json['completed_at'] != null
          ? DateTime.tryParse(json['completed_at'].toString())?.toLocal()
          : null,
      score: json['score']?.toDouble(),
      totalQuestions: json['total_questions'],
      correctAnswers: json['correct_answers'],
      timeTakenMinutes: json['time_taken_minutes'],
      passed: json['passed'],
    );
  }
}

class QuizSubmissionResult {
  final int? quizAttemptId;
  final double score;
  final int totalQuestions;
  final int correctAnswers;
  final bool passed;
  final int? timeTakenMinutes;
  final int pointsEarned;
  final List<Map<String, dynamic>>? detailedResults;
  final String? error;

  QuizSubmissionResult({
    this.quizAttemptId,
    required this.score,
    required this.totalQuestions,
    required this.correctAnswers,
    required this.passed,
    this.timeTakenMinutes,
    required this.pointsEarned,
    this.detailedResults,
    this.error,
  });

  factory QuizSubmissionResult.fromJson(Map<String, dynamic> json) {
    return QuizSubmissionResult(
      quizAttemptId: json['quiz_attempt_id'],
      score: (json['score'] ?? 0.0).toDouble(),
      totalQuestions: json['total_questions'] ?? 0,
      correctAnswers: json['correct_answers'] ?? 0,
      passed: json['passed'] ?? false,
      timeTakenMinutes: json['time_taken_minutes'],
      pointsEarned: json['points_earned'] ?? 0,
      detailedResults: (json['detailed_results'] as List?)
          ?.map((e) => Map<String, dynamic>.from(e))
          .toList(),
    );
  }

  factory QuizSubmissionResult.error(String message) {
    return QuizSubmissionResult(
      score: 0,
      totalQuestions: 0,
      correctAnswers: 0,
      passed: false,
      pointsEarned: 0,
      error: message,
    );
  }
}

class LearningPathExercises {
  final String level;
  final List<ExerciseData> vocabularyExercises;
  final List<ExerciseData> grammarExercises;
  final List<ExerciseData> listeningExercises;
  final List<ExerciseData> readingExercises;
  final List<ExerciseData> speakingExercises;
  final List<ExerciseData> writingExercises;

  LearningPathExercises({
    required this.level,
    required this.vocabularyExercises,
    required this.grammarExercises,
    required this.listeningExercises,
    required this.readingExercises,
    required this.speakingExercises,
    required this.writingExercises,
  });

  factory LearningPathExercises.fromJson(Map<String, dynamic> json) {
    return LearningPathExercises(
      level: json['level'] ?? 'A1',
      vocabularyExercises: (json['vocabulary_exercises'] as List? ?? [])
          .map((e) => ExerciseData.fromJson(e))
          .toList(),
      grammarExercises: (json['grammar_exercises'] as List? ?? [])
          .map((e) => ExerciseData.fromJson(e))
          .toList(),
      listeningExercises: (json['listening_exercises'] as List? ?? [])
          .map((e) => ExerciseData.fromJson(e))
          .toList(),
      readingExercises: (json['reading_exercises'] as List? ?? [])
          .map((e) => ExerciseData.fromJson(e))
          .toList(),
      speakingExercises: (json['speaking_exercises'] as List? ?? [])
          .map((e) => ExerciseData.fromJson(e))
          .toList(),
      writingExercises: (json['writing_exercises'] as List? ?? [])
          .map((e) => ExerciseData.fromJson(e))
          .toList(),
    );
  }

  List<ExerciseData> get allExercises => [
    ...vocabularyExercises,
    ...grammarExercises,
    ...listeningExercises,
    ...readingExercises,
    ...speakingExercises,
    ...writingExercises,
  ];
}
