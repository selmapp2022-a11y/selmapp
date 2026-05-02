import 'package:flutter/foundation.dart';

import '../../../../core/network/api_client.dart';
import '../models/lesson_models.dart';

abstract class LessonsRepository {
  Future<List<Lesson>> getLessons({
    String? lessonType,
    String? difficultyLevel,
    int skip = 0,
    int limit = 20,
  });

  Future<Lesson?> getLessonById(String lessonId);

  Future<Lesson> generateLesson({
    required String lessonType,
    required String difficultyLevel,
    String? topic,
    Map<String, dynamic>? userPreferences,
  });

  Future<void> startLesson(String lessonId);

  Future<void> updateLessonProgress({
    required String lessonId,
    required double progress,
    double? accuracy,
    int? timeSpentMinutes,
    bool? isCompleted,
  });

  Future<List<Lesson>> getRecommendedLessons({int limit = 5});

  Future<void> cleanupExpiredLessons();
}

class LessonsRepositoryImpl implements LessonsRepository {
  final ApiClient _apiClient;

  LessonsRepositoryImpl(this._apiClient);

  @override
  Future<List<Lesson>> getLessons({
    String? lessonType,
    String? difficultyLevel,
    int skip = 0,
    int limit = 20,
  }) async {
    try {
      // Try to get cached lessons from database first
      final response = await _apiClient.get(
        '/lessons/cached/',
        queryParameters: {
          if (lessonType != null) 'lesson_type': lessonType,
          if (difficultyLevel != null) 'difficulty_level': difficultyLevel,
          'skip': skip,
          'limit': limit,
        },
      );

      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => Lesson.fromJson(json['lesson'])).toList();
      }

      // Fallback to generation if no cached lessons
      return [];
    } catch (e) {
      debugPrint('Failed to get lessons: $e');
      return [];
    }
  }

  @override
  Future<Lesson?> getLessonById(String lessonId) async {
    try {
      // This would typically fetch from a dedicated endpoint
      // For now, we'll get it from cached lessons
      final lessons = await getLessons();
      return lessons.cast<Lesson?>().firstWhere(
        (lesson) => lesson?.id == lessonId,
        orElse: () => null,
      );
    } catch (e) {
      debugPrint('Failed to get lesson by ID: $e');
      return null;
    }
  }

  @override
  Future<Lesson> generateLesson({
    required String lessonType,
    required String difficultyLevel,
    String? topic,
    Map<String, dynamic>? userPreferences,
  }) async {
    try {
      final response = await _apiClient.post(
        '/lessons/generate/',
        data: {
          'lesson_type': lessonType,
          'difficulty_level': difficultyLevel,
          if (topic != null) 'topic': topic,
          if (userPreferences != null) 'user_preferences': userPreferences,
        },
      );

      if (response.statusCode == 200) {
        final data = response.data;
        return Lesson.fromJson(data['lesson']);
      }

      throw Exception('Failed to generate lesson');
    } catch (e) {
      debugPrint('Failed to generate lesson: $e');
      // Return a fallback lesson
      return _createFallbackLesson(lessonType, difficultyLevel, topic);
    }
  }

  @override
  Future<void> startLesson(String lessonId) async {
    try {
      await _apiClient.post('/lessons/$lessonId/start/');
    } catch (e) {
      debugPrint('Failed to start lesson: $e');
      // Continue anyway - this is not critical
    }
  }

  @override
  Future<void> updateLessonProgress({
    required String lessonId,
    required double progress,
    double? accuracy,
    int? timeSpentMinutes,
    bool? isCompleted,
  }) async {
    try {
      await _apiClient.put(
        '/lessons/$lessonId/progress/',
        data: {
          'progress_percentage': progress,
          if (accuracy != null) 'accuracy_score': accuracy,
          if (timeSpentMinutes != null) 'time_spent_minutes': timeSpentMinutes,
          if (isCompleted != null) 'is_completed': isCompleted,
        },
      );
    } catch (e) {
      debugPrint('Failed to update lesson progress: $e');
      // Continue anyway - this is not critical
    }
  }

  @override
  Future<List<Lesson>> getRecommendedLessons({int limit = 5}) async {
    try {
      final response = await _apiClient.get(
        '/lessons/recommendations/',
        queryParameters: {'limit': limit},
      );

      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => Lesson.fromJson(json['lesson'])).toList();
      }

      return [];
    } catch (e) {
      debugPrint('Failed to get recommended lessons: $e');
      return [];
    }
  }

  @override
  Future<void> cleanupExpiredLessons() async {
    try {
      await _apiClient.post('/lessons/cleanup/');
    } catch (e) {
      debugPrint('Failed to cleanup expired lessons: $e');
    }
  }

  // Helper method to create fallback lesson when API fails
  Lesson _createFallbackLesson(String lessonType, String difficultyLevel, String? topic) {
    final title = topic != null
        ? '$lessonType Practice: $topic'
        : '$lessonType Practice';

    final description = 'Practice $lessonType at $difficultyLevel level${topic != null ? ' with focus on $topic' : ''}';

    return Lesson(
      id: 'fallback_${DateTime.now().millisecondsSinceEpoch}',
      title: title,
      description: description,
      type: _parseLessonType(lessonType),
      level: _parseDifficultyLevel(difficultyLevel),
      estimatedMinutes: 15,
      objectives: ['Practice $lessonType skills', 'Improve understanding', 'Build confidence'],
      keyTopics: topic != null ? [topic] : ['$lessonType basics'],
      isCompleted: false,
    );
  }

  LessonType _parseLessonType(String type) {
    switch (type.toLowerCase()) {
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
      default:
        return LessonType.mixed;
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














