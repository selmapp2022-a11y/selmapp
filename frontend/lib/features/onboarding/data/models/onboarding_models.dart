import 'package:equatable/equatable.dart';

enum LearningCategory {
  dailyLife('daily_life', 'Daily Life', '🏠', 'Everyday conversations and activities'),
  food('food', 'Food & Dining', '🍽️', 'Restaurant conversations, cooking, recipes'),
  travel('travel', 'Travel', '✈️', 'Airport, hotel, directions, sightseeing'),
  business('business', 'Business', '💼', 'Professional communication, meetings'),
  entertainment('entertainment', 'Entertainment', '🎬', 'Movies, music, sports, hobbies'),
  shopping('shopping', 'Shopping', '🛒', 'Stores, markets, prices, purchases'),
  health('health', 'Health & Medical', '🏥', 'Doctor visits, pharmacy, symptoms'),
  education('education', 'Education', '📚', 'School, university, learning topics'),
  technology('technology', 'Technology', '💻', 'Computers, internet, social media'),
  culture('culture', 'Culture & Arts', '🎨', 'Museums, traditions, festivals');

  const LearningCategory(this.id, this.title, this.icon, this.description);
  
  final String id;
  final String title;
  final String icon;
  final String description;
}

enum CEFRLevel {
  a1('A1', 'Beginner', 'Can understand and use familiar everyday expressions'),
  a2('A2', 'Elementary', 'Can communicate in simple routine tasks'),
  b1('B1', 'Intermediate', 'Can deal with most situations while travelling'),
  b2('B2', 'Upper-Intermediate', 'Can interact with fluency and spontaneity'),
  c1('C1', 'Advanced', 'Can use language flexibly and effectively'),
  c2('C2', 'Proficient', 'Can understand virtually everything heard or read');

  const CEFRLevel(this.code, this.name, this.description);
  
  final String code;
  final String name;
  final String description;
}

enum LearningPace {
  relaxed('relaxed', 'Relaxed', '🐌', '10-15 min/day', 'Perfect for busy schedules'),
  steady('steady', 'Steady', '🚶', '20-30 min/day', 'Consistent daily progress'),
  intensive('intensive', 'Intensive', '🏃', '45-60 min/day', 'Fast-track learning');

  const LearningPace(this.id, this.title, this.icon, this.duration, this.description);

  final String id;
  final String title;
  final String icon;
  final String duration;
  final String description;

  /// Get the average daily study time in minutes for this pace
  int get averageDailyMinutes {
    switch (this) {
      case LearningPace.relaxed:
        return 12; // Average of 10-15
      case LearningPace.steady:
        return 25; // Average of 20-30
      case LearningPace.intensive:
        return 52; // Average of 45-60
    }
  }
}

class UserProfile extends Equatable {
  final String userId;
  final String name;
  final String email;
  final List<LearningCategory> preferredCategories;
  final CEFRLevel currentLevel;
  final LearningPace learningPace;
  final Map<String, dynamic> assessmentResults;
  final DateTime createdAt;
  final bool onboardingCompleted;

  const UserProfile({
    required this.userId,
    required this.name,
    required this.email,
    required this.preferredCategories,
    required this.currentLevel,
    required this.learningPace,
    required this.assessmentResults,
    required this.createdAt,
    required this.onboardingCompleted,
  });

  UserProfile copyWith({
    String? userId,
    String? name,
    String? email,
    List<LearningCategory>? preferredCategories,
    CEFRLevel? currentLevel,
    LearningPace? learningPace,
    Map<String, dynamic>? assessmentResults,
    DateTime? createdAt,
    bool? onboardingCompleted,
  }) {
    return UserProfile(
      userId: userId ?? this.userId,
      name: name ?? this.name,
      email: email ?? this.email,
      preferredCategories: preferredCategories ?? this.preferredCategories,
      currentLevel: currentLevel ?? this.currentLevel,
      learningPace: learningPace ?? this.learningPace,
      assessmentResults: assessmentResults ?? this.assessmentResults,
      createdAt: createdAt ?? this.createdAt,
      onboardingCompleted: onboardingCompleted ?? this.onboardingCompleted,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'userId': userId,
      'name': name,
      'email': email,
      'preferredCategories': preferredCategories.map((c) => c.id).toList(),
      'currentLevel': currentLevel.code,
      'learningPace': learningPace.id,
      'assessmentResults': assessmentResults,
      'createdAt': createdAt.toIso8601String(),
      'onboardingCompleted': onboardingCompleted,
    };
  }

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['userId'],
      name: json['name'],
      email: json['email'],
      preferredCategories: (json['preferredCategories'] as List)
          .map((id) => LearningCategory.values.firstWhere((c) => c.id == id))
          .toList(),
      currentLevel: CEFRLevel.values.firstWhere((l) => l.code == json['currentLevel']),
      learningPace: LearningPace.values.firstWhere((p) => p.id == json['learningPace']),
      assessmentResults: json['assessmentResults'] ?? {},
      createdAt: DateTime.parse(json['createdAt'].toString()).toLocal(),
      onboardingCompleted: json['onboardingCompleted'] ?? false,
    );
  }

  @override
  List<Object?> get props => [
        userId,
        name,
        email,
        preferredCategories,
        currentLevel,
        learningPace,
        assessmentResults,
        createdAt,
        onboardingCompleted,
      ];
}

class AssessmentQuestion extends Equatable {
  final String id;
  final String? passage; // reading support
  final String question;
  final List<String> options;
  final int correctAnswerIndex;
  final CEFRLevel targetLevel;
  final String skillType; // grammar, vocabulary, reading, listening
  final String explanation;
  final String questionType; // multiple_choice, true_false, fill_in_blank
  final String? correctAnswerText; // used for fill_in_blank
  final String? audioUrl; // listening support
  final String? audioText; // listening TTS transcript

  const AssessmentQuestion({
    required this.id,
    this.passage,
    required this.question,
    required this.options,
    required this.correctAnswerIndex,
    required this.targetLevel,
    required this.skillType,
    required this.explanation,
    this.questionType = 'multiple_choice',
    this.correctAnswerText,
    this.audioUrl,
    this.audioText,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'passage': passage,
      'question': question,
      'options': options,
      'correctAnswerIndex': correctAnswerIndex,
      'targetLevel': targetLevel.code,
      'skillType': skillType,
      'explanation': explanation,
      'questionType': questionType,
      'correctAnswerText': correctAnswerText,
      'audioUrl': audioUrl,
      'audioText': audioText,
    };
  }

  factory AssessmentQuestion.fromJson(Map<String, dynamic> json) {
    return AssessmentQuestion(
      id: json['id'],
      passage: json['passage'],
      question: json['question'],
      options: List<String>.from(json['options']),
      correctAnswerIndex: json['correctAnswerIndex'],
      targetLevel: CEFRLevel.values.firstWhere((l) => l.code == json['targetLevel']),
      skillType: json['skillType'],
      explanation: json['explanation'],
      questionType: json['questionType'] ?? 'multiple_choice',
      correctAnswerText: json['correctAnswerText'],
      audioUrl: json['audioUrl'],
      audioText: json['audioText'],
    );
  }

  @override
  List<Object?> get props => [
        id,
        passage,
        question,
        options,
        correctAnswerIndex,
        targetLevel,
        skillType,
        explanation,
        questionType,
        correctAnswerText,
        audioUrl,
        audioText,
      ];
}

class AssessmentResult extends Equatable {
  final String userId;
  final List<AssessmentAnswer> answers;
  final CEFRLevel determinedLevel;
  final Map<String, double> skillScores;
  final double overallScore;
  final String feedback;
  final List<String> recommendations;
  final DateTime completedAt;

  const AssessmentResult({
    required this.userId,
    required this.answers,
    required this.determinedLevel,
    required this.skillScores,
    required this.overallScore,
    required this.feedback,
    required this.recommendations,
    required this.completedAt,
  });

  Map<String, dynamic> toJson() {
    return {
      'userId': userId,
      'answers': answers.map((a) => a.toJson()).toList(),
      'determinedLevel': determinedLevel.code,
      'skillScores': skillScores,
      'overallScore': overallScore,
      'feedback': feedback,
      'recommendations': recommendations,
      'completedAt': completedAt.toIso8601String(),
    };
  }

  factory AssessmentResult.fromJson(Map<String, dynamic> json) {
    return AssessmentResult(
      userId: json['userId'],
      answers: (json['answers'] as List)
          .map((a) => AssessmentAnswer.fromJson(a))
          .toList(),
      determinedLevel: CEFRLevel.values.firstWhere((l) => l.code == json['determinedLevel']),
      skillScores: Map<String, double>.from(json['skillScores']),
      overallScore: json['overallScore'].toDouble(),
      feedback: json['feedback'],
      recommendations: List<String>.from(json['recommendations']),
      completedAt: DateTime.parse(json['completedAt'].toString()).toLocal(),
    );
  }

  @override
  List<Object?> get props => [
        userId,
        answers,
        determinedLevel,
        skillScores,
        overallScore,
        feedback,
        recommendations,
        completedAt,
      ];
}

class AssessmentAnswer extends Equatable {
  final String questionId;
  final int selectedAnswerIndex;
  final bool isCorrect;
  final int timeSpentSeconds;
  final String? textAnswer; // for fill_in_blank

  const AssessmentAnswer({
    required this.questionId,
    required this.selectedAnswerIndex,
    required this.isCorrect,
    required this.timeSpentSeconds,
    this.textAnswer,
  });

  Map<String, dynamic> toJson() {
    return {
      'questionId': questionId,
      'selectedAnswerIndex': selectedAnswerIndex,
      'isCorrect': isCorrect,
      'timeSpentSeconds': timeSpentSeconds,
      'textAnswer': textAnswer,
    };
  }

  factory AssessmentAnswer.fromJson(Map<String, dynamic> json) {
    return AssessmentAnswer(
      questionId: json['questionId'],
      selectedAnswerIndex: json['selectedAnswerIndex'],
      isCorrect: json['isCorrect'],
      timeSpentSeconds: json['timeSpentSeconds'],
      textAnswer: json['textAnswer'],
    );
  }

  @override
  List<Object?> get props => [questionId, selectedAnswerIndex, isCorrect, timeSpentSeconds, textAnswer];
}

class LearningPath extends Equatable {
  final String userId;
  final List<LearningCategory> categories;
  final CEFRLevel currentLevel;
  final CEFRLevel targetLevel;
  final LearningPace pace;
  final List<LearningModule> modules;
  final DateTime createdAt;
  final DateTime updatedAt;

  const LearningPath({
    required this.userId,
    required this.categories,
    required this.currentLevel,
    required this.targetLevel,
    required this.pace,
    required this.modules,
    required this.createdAt,
    required this.updatedAt,
  });

  Map<String, dynamic> toJson() {
    return {
      'userId': userId,
      'categories': categories.map((c) => c.id).toList(),
      'currentLevel': currentLevel.code,
      'targetLevel': targetLevel.code,
      'pace': pace.id,
      'modules': modules.map((m) => m.toJson()).toList(),
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
    };
  }

  LearningPath copyWith({
    String? userId,
    List<LearningCategory>? categories,
    CEFRLevel? currentLevel,
    CEFRLevel? targetLevel,
    LearningPace? pace,
    List<LearningModule>? modules,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return LearningPath(
      userId: userId ?? this.userId,
      categories: categories ?? this.categories,
      currentLevel: currentLevel ?? this.currentLevel,
      targetLevel: targetLevel ?? this.targetLevel,
      pace: pace ?? this.pace,
      modules: modules ?? this.modules,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  factory LearningPath.fromJson(Map<String, dynamic> json) {
    return LearningPath(
      userId: json['userId'],
      categories: (json['categories'] as List)
          .map((id) => LearningCategory.values.firstWhere((c) => c.id == id))
          .toList(),
      currentLevel: CEFRLevel.values.firstWhere((l) => l.code == json['currentLevel']),
      targetLevel: CEFRLevel.values.firstWhere((l) => l.code == json['targetLevel']),
      pace: LearningPace.values.firstWhere((p) => p.id == json['pace']),
      modules: (json['modules'] as List)
          .map((m) => LearningModule.fromJson(m))
          .toList(),
      createdAt: DateTime.parse(json['createdAt'].toString()).toLocal(),
      updatedAt: DateTime.parse(json['updatedAt'].toString()).toLocal(),
    );
  }

  @override
  List<Object?> get props => [
        userId,
        categories,
        currentLevel,
        targetLevel,
        pace,
        modules,
        createdAt,
        updatedAt,
      ];
}

class LearningModule extends Equatable {
  final String id;
  final String title;
  final String description;
  final LearningCategory category;
  final CEFRLevel level;
  final List<String> skills; // speaking, writing, listening, reading
  final int estimatedMinutes;
  final bool isCompleted;
  final bool isUnlocked;
  final double progressPercentage;

  const LearningModule({
    required this.id,
    required this.title,
    required this.description,
    required this.category,
    required this.level,
    required this.skills,
    required this.estimatedMinutes,
    this.isCompleted = false,
    this.isUnlocked = false,
    this.progressPercentage = 0.0,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'category': category.id,
      'level': level.code,
      'skills': skills,
      'estimatedMinutes': estimatedMinutes,
      'isCompleted': isCompleted,
      'isUnlocked': isUnlocked,
      'progressPercentage': progressPercentage,
    };
  }

  factory LearningModule.fromJson(Map<String, dynamic> json) {
    return LearningModule(
      id: json['id'],
      title: json['title'],
      description: json['description'] ?? '',
      category: LearningCategory.values.firstWhere((c) => c.id == json['category']),
      level: CEFRLevel.values.firstWhere((l) => l.code == json['level']),
      skills: List<String>.from(json['skills']),
      estimatedMinutes: json['estimatedMinutes'],
      isCompleted: json['isCompleted'] ?? false,
      isUnlocked: json['isUnlocked'] ?? false,
      progressPercentage: json['progressPercentage']?.toDouble() ?? 0.0,
    );
  }

  LearningModule copyWith({
    String? id,
    String? title,
    String? description,
    LearningCategory? category,
    CEFRLevel? level,
    List<String>? skills,
    int? estimatedMinutes,
    bool? isCompleted,
    bool? isUnlocked,
    double? progressPercentage,
  }) {
    return LearningModule(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      category: category ?? this.category,
      level: level ?? this.level,
      skills: skills ?? this.skills,
      estimatedMinutes: estimatedMinutes ?? this.estimatedMinutes,
      isCompleted: isCompleted ?? this.isCompleted,
      isUnlocked: isUnlocked ?? this.isUnlocked,
      progressPercentage: progressPercentage ?? this.progressPercentage,
    );
  }

  @override
  List<Object?> get props => [
        id,
        title,
        description,
        category,
        level,
        skills,
        estimatedMinutes,
        isCompleted,
        isUnlocked,
        progressPercentage,
      ];
}

// New: Lesson session models
class LessonStep extends Equatable {
  final String stepType; // reading | listening | vocabulary | grammar | exercise | quiz
  final String title;
  final String? content;
  final String? mediaUrl;
  final List<Map<String, dynamic>>? questions;
  final int estimatedMinutes;
  final Map<String, dynamic>? contentJson;

  const LessonStep({
    required this.stepType,
    required this.title,
    this.content,
    this.mediaUrl,
    this.questions,
    this.estimatedMinutes = 5,
    this.contentJson,
  });

  factory LessonStep.fromJson(Map<String, dynamic> json) {
    final rawContent = json['content'];
    final Map<String, dynamic>? parsedContentJson = rawContent is Map
        ? Map<String, dynamic>.from(rawContent)
        : (json['content_json'] is Map ? Map<String, dynamic>.from(json['content_json']) : null);
    return LessonStep(
      stepType: json['step_type'],
      title: json['title'],
      content: rawContent is String ? rawContent : null,
      mediaUrl: json['media_url'],
      questions: (json['questions'] as List?)
          ?.map((e) => Map<String, dynamic>.from(e))
          .toList(),
      estimatedMinutes: json['estimated_minutes'] ?? 5,
      contentJson: parsedContentJson,
    );
  }

  Map<String, dynamic> toJson() => {
        'step_type': stepType,
        'title': title,
        'content': content,
        'media_url': mediaUrl,
        'questions': questions,
        'estimated_minutes': estimatedMinutes,
        if (contentJson != null) 'content_json': contentJson,
      };

  @override
  List<Object?> get props => [stepType, title, content, mediaUrl, questions, estimatedMinutes, contentJson];
}

class LessonSession extends Equatable {
  final String sessionId;
  final String moduleId;
  final int dayNumber;
  final List<LessonStep> steps;
  final int totalEstimatedMinutes;

  const LessonSession({
    required this.sessionId,
    required this.moduleId,
    required this.dayNumber,
    required this.steps,
    required this.totalEstimatedMinutes,
  });

  factory LessonSession.fromJson(Map<String, dynamic> json) {
    return LessonSession(
      sessionId: json['session_id'] as String,
      moduleId: json['module_id'] as String,
      dayNumber: json['day_number'] as int,
      steps: (json['steps'] as List)
          .map((e) => LessonStep.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      totalEstimatedMinutes: json['total_estimated_minutes'] as int,
    );
  }

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'module_id': moduleId,
        'day_number': dayNumber,
        'steps': steps.map((e) => e.toJson()).toList(),
        'total_estimated_minutes': totalEstimatedMinutes,
      };

  @override
  List<Object?> get props => [sessionId, moduleId, dayNumber, steps, totalEstimatedMinutes];
}
