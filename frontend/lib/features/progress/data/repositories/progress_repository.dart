import 'package:flutter/foundation.dart';

import '../../../../core/network/api_client.dart';
import '../models/progress_models.dart';

abstract class ProgressRepository {
  Future<UserProgressData?> getUserProgress();
  Future<ProgressDashboard?> getProgressDashboard();
  Future<List<DailyProgressData>> getDailyProgress({int days = 7});
  Future<WeeklyProgressData?> getWeeklyProgress({int weeks = 4});
  Future<StreakInfo?> getStreakInfo();
  Future<List<AchievementData>> getEarnedAchievements();
  Future<List<AchievementData>> getAllAchievements();
  Future<List<LearningGoalData>> getLearningGoals({bool activeOnly = true});
  Future<ExerciseStatistics?> getExerciseStatistics();
  Future<void> updateDailyProgress({
    int studyTimeMinutes = 0,
    int exercisesCompleted = 0,
    int pointsEarned = 0,
    double accuracyRate = 0.0,
  });
}

class ProgressRepositoryImpl implements ProgressRepository {
  final ApiClient _apiClient;

  ProgressRepositoryImpl(this._apiClient);

  @override
  Future<UserProgressData?> getUserProgress() async {
    try {
      final response = await _apiClient.get('/progress/');
      if (response.statusCode == 200) {
        return UserProgressData.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get user progress: $e');
      }
      return null;
    }
  }

  @override
  Future<ProgressDashboard?> getProgressDashboard() async {
    try {
      final response = await _apiClient.get('/progress/dashboard');
      if (response.statusCode == 200) {
        return ProgressDashboard.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get progress dashboard: $e');
      }
      return null;
    }
  }

  @override
  Future<List<DailyProgressData>> getDailyProgress({int days = 7}) async {
    try {
      final response = await _apiClient.get(
        '/progress/daily',
        queryParameters: {'days': days},
      );
      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => DailyProgressData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get daily progress: $e');
      }
      return [];
    }
  }

  @override
  Future<WeeklyProgressData?> getWeeklyProgress({int weeks = 4}) async {
    try {
      final response = await _apiClient.get(
        '/progress/weekly',
        queryParameters: {'weeks': weeks},
      );
      if (response.statusCode == 200) {
        return WeeklyProgressData.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get weekly progress: $e');
      }
      return null;
    }
  }

  @override
  Future<StreakInfo?> getStreakInfo() async {
    try {
      final response = await _apiClient.get('/progress/streak');
      if (response.statusCode == 200) {
        return StreakInfo.fromJson(response.data);
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get streak info: $e');
      }
      return null;
    }
  }

  @override
  Future<List<AchievementData>> getEarnedAchievements() async {
    try {
      final response = await _apiClient.get('/progress/achievements/earned');
      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => AchievementData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get earned achievements: $e');
      }
      return [];
    }
  }

  @override
  Future<List<AchievementData>> getAllAchievements() async {
    try {
      final response = await _apiClient.get('/progress/achievements');
      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => AchievementData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get all achievements: $e');
      }
      return [];
    }
  }

  @override
  Future<List<LearningGoalData>> getLearningGoals({
    bool activeOnly = true,
  }) async {
    try {
      final response = await _apiClient.get(
        '/progress/goals',
        queryParameters: {'active_only': activeOnly},
      );
      if (response.statusCode == 200) {
        final data = response.data as List;
        return data.map((json) => LearningGoalData.fromJson(json)).toList();
      }
      return [];
    } catch (e) {
      if (kDebugMode) {
        print('Failed to get learning goals: $e');
      }
      return [];
    }
  }

  @override
  Future<ExerciseStatistics?> getExerciseStatistics() async {
    try {
      final response = await _apiClient.get('/exercises/statistics/');
      if (response.statusCode == 200) {
        return ExerciseStatistics.fromJson(response.data);
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
  Future<void> updateDailyProgress({
    int studyTimeMinutes = 0,
    int exercisesCompleted = 0,
    int pointsEarned = 0,
    double accuracyRate = 0.0,
  }) async {
    try {
      await _apiClient.post(
        '/progress/daily/update',
        queryParameters: {
          'study_time_minutes': studyTimeMinutes,
          'exercises_completed': exercisesCompleted,
          'points_earned': pointsEarned,
          'accuracy_rate': accuracyRate,
        },
      );
    } catch (e) {
      if (kDebugMode) {
        print('Failed to update daily progress: $e');
      }
    }
  }
}
