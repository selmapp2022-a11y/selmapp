// Data models for the admin panel.
// These mirror the backend Pydantic schemas in admin.py.

class SystemStats {
  final int totalUsers;
  final int activeUsers;
  final int premiumUsers;
  final int newUsersToday;
  final int newUsersThisWeek;
  final int newUsersThisMonth;
  final int totalLessonsGenerated;
  final int totalExercisesCompleted;
  final double averageAccuracy;
  final int totalPayments;
  final double totalRevenue;

  SystemStats({
    this.totalUsers = 0,
    this.activeUsers = 0,
    this.premiumUsers = 0,
    this.newUsersToday = 0,
    this.newUsersThisWeek = 0,
    this.newUsersThisMonth = 0,
    this.totalLessonsGenerated = 0,
    this.totalExercisesCompleted = 0,
    this.averageAccuracy = 0.0,
    this.totalPayments = 0,
    this.totalRevenue = 0.0,
  });

  factory SystemStats.fromJson(Map<String, dynamic> json) {
    return SystemStats(
      totalUsers: json['total_users'] ?? 0,
      activeUsers: json['active_users'] ?? 0,
      premiumUsers: json['premium_users'] ?? 0,
      newUsersToday: json['new_users_today'] ?? 0,
      newUsersThisWeek: json['new_users_this_week'] ?? 0,
      newUsersThisMonth: json['new_users_this_month'] ?? 0,
      totalLessonsGenerated: json['total_lessons_generated'] ?? 0,
      totalExercisesCompleted: json['total_exercises_completed'] ?? 0,
      averageAccuracy: (json['average_accuracy'] ?? 0.0).toDouble(),
      totalPayments: json['total_payments'] ?? 0,
      totalRevenue: (json['total_revenue'] ?? 0.0).toDouble(),
    );
  }
}

class ContentStats {
  final int totalAiLessons;
  final int totalReadingTexts;
  final int totalVocabularySets;
  final Map<String, int> lessonsByType;
  final Map<String, int> lessonsByLevel;

  ContentStats({
    this.totalAiLessons = 0,
    this.totalReadingTexts = 0,
    this.totalVocabularySets = 0,
    this.lessonsByType = const {},
    this.lessonsByLevel = const {},
  });

  factory ContentStats.fromJson(Map<String, dynamic> json) {
    return ContentStats(
      totalAiLessons: json['total_ai_lessons'] ?? 0,
      totalReadingTexts: json['total_reading_texts'] ?? 0,
      totalVocabularySets: json['total_vocabulary_sets'] ?? 0,
      lessonsByType: Map<String, int>.from(json['lessons_by_type'] ?? {}),
      lessonsByLevel: Map<String, int>.from(json['lessons_by_level'] ?? {}),
    );
  }
}

class UserActivitySummary {
  final String date;
  final int activeUsers;
  final int newRegistrations;
  final int lessonsCompleted;
  final int exercisesCompleted;

  UserActivitySummary({
    required this.date,
    this.activeUsers = 0,
    this.newRegistrations = 0,
    this.lessonsCompleted = 0,
    this.exercisesCompleted = 0,
  });

  factory UserActivitySummary.fromJson(Map<String, dynamic> json) {
    return UserActivitySummary(
      date: json['date'] ?? '',
      activeUsers: json['active_users'] ?? 0,
      newRegistrations: json['new_registrations'] ?? 0,
      lessonsCompleted: json['lessons_completed'] ?? 0,
      exercisesCompleted: json['exercises_completed'] ?? 0,
    );
  }
}

class AdminUserListItem {
  final int id;
  final String email;
  final String username;
  final String? fullName;
  final String? currentLevel;
  final bool isActive;
  final bool isVerified;
  final bool isPremium;
  final bool isAdmin;
  final String? adminRole;
  final bool onboardingCompleted;
  final String? createdAt;
  final String? lastLogin;
  final String? deletedAt;

  AdminUserListItem({
    required this.id,
    required this.email,
    required this.username,
    this.fullName,
    this.currentLevel,
    this.isActive = true,
    this.isVerified = false,
    this.isPremium = false,
    this.isAdmin = false,
    this.adminRole,
    this.onboardingCompleted = false,
    this.createdAt,
    this.lastLogin,
    this.deletedAt,
  });

  factory AdminUserListItem.fromJson(Map<String, dynamic> json) {
    return AdminUserListItem(
      id: json['id'],
      email: json['email'] ?? '',
      username: json['username'] ?? '',
      fullName: json['full_name'],
      currentLevel: json['current_level']?.toString(),
      isActive: json['is_active'] ?? true,
      isVerified: json['is_verified'] ?? false,
      isPremium: json['is_premium'] ?? false,
      isAdmin: json['is_admin'] ?? false,
      adminRole: json['admin_role'],
      onboardingCompleted: json['onboarding_completed'] ?? false,
      createdAt: json['created_at'],
      lastLogin: json['last_login'],
      deletedAt: json['deleted_at'],
    );
  }
}

class AdminUserDetail extends AdminUserListItem {
  final String? avatarUrl;
  final String? nativeLanguage;
  final String? targetLanguage;
  final bool hasPassword;
  final int dailyGoalMinutes;
  final String? preferredStudyTime;
  final bool notificationEnabled;
  final String? updatedAt;
  final int totalStudyTimeMinutes;
  final int totalExercisesCompleted;
  final double averageAccuracy;
  final int currentStreakDays;

  AdminUserDetail({
    required super.id,
    required super.email,
    required super.username,
    super.fullName,
    super.currentLevel,
    super.isActive,
    super.isVerified,
    super.isPremium,
    super.isAdmin,
    super.adminRole,
    super.onboardingCompleted,
    super.createdAt,
    super.lastLogin,
    super.deletedAt,
    this.avatarUrl,
    this.nativeLanguage,
    this.targetLanguage,
    this.hasPassword = true,
    this.dailyGoalMinutes = 30,
    this.preferredStudyTime,
    this.notificationEnabled = true,
    this.updatedAt,
    this.totalStudyTimeMinutes = 0,
    this.totalExercisesCompleted = 0,
    this.averageAccuracy = 0.0,
    this.currentStreakDays = 0,
  });

  factory AdminUserDetail.fromJson(Map<String, dynamic> json) {
    return AdminUserDetail(
      id: json['id'],
      email: json['email'] ?? '',
      username: json['username'] ?? '',
      fullName: json['full_name'],
      currentLevel: json['current_level']?.toString(),
      isActive: json['is_active'] ?? true,
      isVerified: json['is_verified'] ?? false,
      isPremium: json['is_premium'] ?? false,
      isAdmin: json['is_admin'] ?? false,
      adminRole: json['admin_role'],
      onboardingCompleted: json['onboarding_completed'] ?? false,
      createdAt: json['created_at'],
      lastLogin: json['last_login'],
      deletedAt: json['deleted_at'],
      avatarUrl: json['avatar_url'],
      nativeLanguage: json['native_language'],
      targetLanguage: json['target_language'],
      hasPassword: json['has_password'] ?? true,
      dailyGoalMinutes: json['daily_goal_minutes'] ?? 30,
      preferredStudyTime: json['preferred_study_time'],
      notificationEnabled: json['notification_enabled'] ?? true,
      updatedAt: json['updated_at'],
      totalStudyTimeMinutes: json['total_study_time_minutes'] ?? 0,
      totalExercisesCompleted: json['total_exercises_completed'] ?? 0,
      averageAccuracy: (json['average_accuracy'] ?? 0.0).toDouble(),
      currentStreakDays: json['current_streak_days'] ?? 0,
    );
  }
}

class UserActivityReport {
  final int userId;
  final String email;
  final String username;
  final int totalStudyTimeMinutes;
  final int totalExercisesCompleted;
  final double averageAccuracy;
  final int currentStreakDays;
  final String? lastLogin;
  final String? lastStudyDate;
  final int lessonsCompleted;
  final bool onboardingCompleted;
  final String? currentLevel;

  UserActivityReport({
    required this.userId,
    required this.email,
    required this.username,
    this.totalStudyTimeMinutes = 0,
    this.totalExercisesCompleted = 0,
    this.averageAccuracy = 0.0,
    this.currentStreakDays = 0,
    this.lastLogin,
    this.lastStudyDate,
    this.lessonsCompleted = 0,
    this.onboardingCompleted = false,
    this.currentLevel,
  });

  factory UserActivityReport.fromJson(Map<String, dynamic> json) {
    return UserActivityReport(
      userId: json['user_id'],
      email: json['email'] ?? '',
      username: json['username'] ?? '',
      totalStudyTimeMinutes: json['total_study_time_minutes'] ?? 0,
      totalExercisesCompleted: json['total_exercises_completed'] ?? 0,
      averageAccuracy: (json['average_accuracy'] ?? 0.0).toDouble(),
      currentStreakDays: json['current_streak_days'] ?? 0,
      lastLogin: json['last_login'],
      lastStudyDate: json['last_study_date'],
      lessonsCompleted: json['lessons_completed'] ?? 0,
      onboardingCompleted: json['onboarding_completed'] ?? false,
      currentLevel: json['current_level'],
    );
  }
}

class AdminDashboard {
  final SystemStats systemStats;
  final ContentStats contentStats;
  final List<AdminUserListItem> recentUsers;
  final List<UserActivitySummary> dailyActivity;

  AdminDashboard({
    required this.systemStats,
    required this.contentStats,
    this.recentUsers = const [],
    this.dailyActivity = const [],
  });

  factory AdminDashboard.fromJson(Map<String, dynamic> json) {
    return AdminDashboard(
      systemStats: SystemStats.fromJson(json['system_stats'] ?? {}),
      contentStats: ContentStats.fromJson(json['content_stats'] ?? {}),
      recentUsers: (json['recent_users'] as List<dynamic>?)
              ?.map((e) => AdminUserListItem.fromJson(e))
              .toList() ??
          [],
      dailyActivity: (json['daily_activity'] as List<dynamic>?)
              ?.map((e) => UserActivitySummary.fromJson(e))
              .toList() ??
          [],
    );
  }
}
