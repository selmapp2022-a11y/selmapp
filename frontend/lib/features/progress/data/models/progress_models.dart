class UserProgressData {
  final int id;
  final int userId;
  final String currentLevel;
  final double levelProgressPercentage;
  final int totalStudyTimeMinutes;
  final int totalExercisesCompleted;
  final int totalPointsEarned;
  final int currentStreakDays;
  final int longestStreakDays;
  final double averageAccuracy;
  final int vocabularyMastered;
  final int grammarRulesLearned;
  final DateTime? lastStudyDate;

  UserProgressData({
    required this.id,
    required this.userId,
    required this.currentLevel,
    required this.levelProgressPercentage,
    required this.totalStudyTimeMinutes,
    required this.totalExercisesCompleted,
    required this.totalPointsEarned,
    required this.currentStreakDays,
    required this.longestStreakDays,
    required this.averageAccuracy,
    required this.vocabularyMastered,
    required this.grammarRulesLearned,
    this.lastStudyDate,
  });

  factory UserProgressData.fromJson(Map<String, dynamic> json) {
    return UserProgressData(
      id: json['id'] ?? 0,
      userId: json['user_id'] ?? 0,
      currentLevel: json['current_level'] ?? 'A1',
      levelProgressPercentage: (json['level_progress_percentage'] ?? 0.0).toDouble(),
      totalStudyTimeMinutes: json['total_study_time_minutes'] ?? 0,
      totalExercisesCompleted: json['total_exercises_completed'] ?? 0,
      totalPointsEarned: json['total_points_earned'] ?? 0,
      currentStreakDays: json['current_streak_days'] ?? 0,
      longestStreakDays: json['longest_streak_days'] ?? 0,
      averageAccuracy: (json['average_accuracy'] ?? 0.0).toDouble(),
      vocabularyMastered: json['vocabulary_mastered'] ?? 0,
      grammarRulesLearned: json['grammar_rules_learned'] ?? 0,
      lastStudyDate: json['last_study_date'] != null
          ? DateTime.tryParse(json['last_study_date'].toString())?.toLocal()
          : null,
    );
  }
}

class DailyProgressData {
  final int id;
  final DateTime date;
  final int studyTimeMinutes;
  final int exercisesCompleted;
  final int pointsEarned;
  final double accuracyRate;
  final bool dailyGoalMet;

  DailyProgressData({
    required this.id,
    required this.date,
    required this.studyTimeMinutes,
    required this.exercisesCompleted,
    required this.pointsEarned,
    required this.accuracyRate,
    required this.dailyGoalMet,
  });

  factory DailyProgressData.fromJson(Map<String, dynamic> json) {
    return DailyProgressData(
      id: json['id'] ?? 0,
      date: DateTime.tryParse(json['date']?.toString() ?? '')?.toLocal() ??
          DateTime.now(),
      studyTimeMinutes: json['study_time_minutes'] ?? 0,
      exercisesCompleted: json['exercises_completed'] ?? 0,
      pointsEarned: json['points_earned'] ?? 0,
      accuracyRate: (json['accuracy_rate'] ?? 0.0).toDouble(),
      dailyGoalMet: json['daily_goal_met'] ?? false,
    );
  }
}

class WeeklyProgressData {
  final List<WeekSummary> weeklyProgress;

  WeeklyProgressData({required this.weeklyProgress});

  factory WeeklyProgressData.fromJson(Map<String, dynamic> json) {
    final weeklyList = json['weekly_progress'] as List? ?? [];
    return WeeklyProgressData(
      weeklyProgress: weeklyList.map((w) => WeekSummary.fromJson(w)).toList(),
    );
  }
}

class WeekSummary {
  final DateTime weekStart;
  final DateTime weekEnd;
  final int totalStudyTime;
  final int totalExercises;
  final int totalPoints;
  final int daysStudied;

  WeekSummary({
    required this.weekStart,
    required this.weekEnd,
    required this.totalStudyTime,
    required this.totalExercises,
    required this.totalPoints,
    required this.daysStudied,
  });

  factory WeekSummary.fromJson(Map<String, dynamic> json) {
    return WeekSummary(
      weekStart:
          DateTime.tryParse(json['week_start']?.toString() ?? '')?.toLocal() ??
              DateTime.now(),
      weekEnd:
          DateTime.tryParse(json['week_end']?.toString() ?? '')?.toLocal() ??
              DateTime.now(),
      totalStudyTime: json['total_study_time'] ?? 0,
      totalExercises: json['total_exercises'] ?? 0,
      totalPoints: json['total_points'] ?? 0,
      daysStudied: json['days_studied'] ?? 0,
    );
  }
}

class StreakInfo {
  final int currentStreak;
  final int longestStreak;
  final DateTime? lastStudyDate;
  final List<int> achievedMilestones;
  final int? nextMilestone;
  final int daysToNextMilestone;

  StreakInfo({
    required this.currentStreak,
    required this.longestStreak,
    this.lastStudyDate,
    required this.achievedMilestones,
    this.nextMilestone,
    required this.daysToNextMilestone,
  });

  factory StreakInfo.fromJson(Map<String, dynamic> json) {
    return StreakInfo(
      currentStreak: json['current_streak'] ?? 0,
      longestStreak: json['longest_streak'] ?? 0,
      lastStudyDate: json['last_study_date'] != null
          ? DateTime.tryParse(json['last_study_date'].toString())?.toLocal()
          : null,
      achievedMilestones: (json['achieved_milestones'] as List? ?? [])
          .map((e) => e as int)
          .toList(),
      nextMilestone: json['next_milestone'],
      daysToNextMilestone: json['days_to_next_milestone'] ?? 0,
    );
  }
}

class AchievementData {
  final int id;
  final String name;
  final String description;
  final String? iconUrl;
  final int pointsReward;
  final DateTime? earnedAt;
  final bool isEarned;

  AchievementData({
    required this.id,
    required this.name,
    required this.description,
    this.iconUrl,
    required this.pointsReward,
    this.earnedAt,
    this.isEarned = false,
  });

  factory AchievementData.fromJson(Map<String, dynamic> json) {
    // Handle both direct achievement and nested achievement structure
    final achievement = json['achievement'] ?? json;
    return AchievementData(
      id: achievement['id'] ?? json['id'] ?? 0,
      name: achievement['name'] ?? json['name'] ?? '',
      description: achievement['description'] ?? json['description'] ?? '',
      iconUrl: achievement['icon_url'] ?? json['icon_url'],
      pointsReward: achievement['points_reward'] ?? json['points_reward'] ?? 0,
      earnedAt: json['earned_at'] != null
          ? DateTime.tryParse(json['earned_at'].toString())?.toLocal()
          : null,
      isEarned: json['earned_at'] != null,
    );
  }
}

class LearningGoalData {
  final int id;
  final String title;
  final String? description;
  final String goalType;
  final int targetValue;
  final int currentValue;
  final DateTime? deadline;
  final bool isActive;
  final bool isCompleted;

  LearningGoalData({
    required this.id,
    required this.title,
    this.description,
    required this.goalType,
    required this.targetValue,
    required this.currentValue,
    this.deadline,
    required this.isActive,
    required this.isCompleted,
  });

  double get progressPercentage => 
      targetValue > 0 ? (currentValue / targetValue * 100).clamp(0, 100) : 0;

  factory LearningGoalData.fromJson(Map<String, dynamic> json) {
    return LearningGoalData(
      id: json['id'] ?? 0,
      title: json['title'] ?? '',
      description: json['description'],
      goalType: json['goal_type'] ?? 'study_time',
      targetValue: json['target_value'] ?? 0,
      currentValue: json['current_value'] ?? 0,
      deadline: json['deadline'] != null
          ? DateTime.tryParse(json['deadline'].toString())?.toLocal()
          : null,
      isActive: json['is_active'] ?? true,
      isCompleted: json['is_completed'] ?? false,
    );
  }
}

class ProgressDashboard {
  final UserProgressData? userProgress;
  final List<AchievementData> recentAchievements;
  final List<DailyProgressData> dailyProgress;
  final List<LearningGoalData> activeGoals;
  final StreakInfo studyStreak;
  final LevelProgress levelProgress;

  ProgressDashboard({
    this.userProgress,
    required this.recentAchievements,
    required this.dailyProgress,
    required this.activeGoals,
    required this.studyStreak,
    required this.levelProgress,
  });

  factory ProgressDashboard.fromJson(Map<String, dynamic> json) {
    return ProgressDashboard(
      userProgress: json['user_progress'] != null 
          ? UserProgressData.fromJson(json['user_progress']) 
          : null,
      recentAchievements: (json['recent_achievements'] as List? ?? [])
          .map((a) => AchievementData.fromJson(a))
          .toList(),
      dailyProgress: (json['daily_progress'] as List? ?? [])
          .map((d) => DailyProgressData.fromJson(d))
          .toList(),
      activeGoals: (json['active_goals'] as List? ?? [])
          .map((g) => LearningGoalData.fromJson(g))
          .toList(),
      studyStreak: StreakInfo.fromJson(json['study_streak'] ?? {}),
      levelProgress: LevelProgress.fromJson(json['level_progress'] ?? {}),
    );
  }
}

class LevelProgress {
  final String currentLevel;
  final double progressPercentage;
  final int vocabularyMastered;
  final int grammarCompleted;

  LevelProgress({
    required this.currentLevel,
    required this.progressPercentage,
    required this.vocabularyMastered,
    required this.grammarCompleted,
  });

  factory LevelProgress.fromJson(Map<String, dynamic> json) {
    return LevelProgress(
      currentLevel: json['current_level'] ?? 'A1',
      progressPercentage: (json['progress_percentage'] ?? 0.0).toDouble(),
      vocabularyMastered: json['vocabulary_mastered'] ?? 0,
      grammarCompleted: json['grammar_completed'] ?? 0,
    );
  }
}

class ExerciseStatistics {
  final int totalAttempts;
  final int correctAnswers;
  final double averageScore;
  final double averageTimeSeconds;
  final Map<String, int> exercisesByType;
  final Map<String, double> accuracyByType;

  ExerciseStatistics({
    required this.totalAttempts,
    required this.correctAnswers,
    required this.averageScore,
    required this.averageTimeSeconds,
    required this.exercisesByType,
    required this.accuracyByType,
  });

  double get overallAccuracy => 
      totalAttempts > 0 ? correctAnswers / totalAttempts * 100 : 0;

  factory ExerciseStatistics.fromJson(Map<String, dynamic> json) {
    return ExerciseStatistics(
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








