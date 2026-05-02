import 'package:flutter/material.dart';
import '../../data/models/lesson_models.dart';

class LessonDetailPage extends StatelessWidget {
  final Lesson lesson;

  const LessonDetailPage({
    super.key,
    required this.lesson,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: Text(
          lesson.title,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        backgroundColor: _getLessonTypeColor(lesson.type),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Lesson Header Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: _getLessonTypeColor(lesson.type).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          _getLessonTypeIcon(lesson.type),
                          color: _getLessonTypeColor(lesson.type),
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              lesson.type.name.toUpperCase(),
                              style: TextStyle(
                                color: _getLessonTypeColor(lesson.type),
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            Text(
                              lesson.title,
                              style: const TextStyle(
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (lesson.isCompleted)
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.green.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(
                            Icons.check_circle,
                            color: Colors.green,
                            size: 20,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    lesson.description,
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.grey[700],
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: _getLevelColor(lesson.level).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          lesson.level.name.toUpperCase(),
                          style: TextStyle(
                            color: _getLevelColor(lesson.level),
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.blue.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.access_time,
                              size: 14,
                              color: Colors.blue,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              '${lesson.estimatedMinutes} min',
                              style: const TextStyle(
                                color: Colors.blue,
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 20),
            
            // Learning Objectives
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.track_changes,
                        color: _getLessonTypeColor(lesson.type),
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'Learning Objectives',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: _getLessonTypeColor(lesson.type),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  ...lesson.objectives.map((objective) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          margin: const EdgeInsets.only(top: 8, right: 12),
                          decoration: BoxDecoration(
                            color: _getLessonTypeColor(lesson.type),
                            borderRadius: BorderRadius.circular(3),
                          ),
                        ),
                        Expanded(
                          child: Text(
                            objective,
                            style: const TextStyle(
                              fontSize: 14,
                              height: 1.4,
                            ),
                          ),
                        ),
                      ],
                    ),
                  )),
                ],
              ),
            ),
            
            const SizedBox(height: 20),
            
            // Key Topics
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.key,
                        color: _getLessonTypeColor(lesson.type),
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'Key Topics',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: _getLessonTypeColor(lesson.type),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: lesson.keyTopics.map((topic) {
                      return Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: _getLessonTypeColor(lesson.type).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: _getLessonTypeColor(lesson.type).withValues(alpha: 0.3),
                          ),
                        ),
                        child: Text(
                          topic,
                          style: TextStyle(
                            color: _getLessonTypeColor(lesson.type),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 80),
          ],
        ),
      ),
      
      // Start Lesson Button
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: SafeArea(
          child: SizedBox(
            width: double.infinity,
            height: 50,
            child: ElevatedButton(
              onPressed: () => _startLesson(context),
              style: ElevatedButton.styleFrom(
                backgroundColor: _getLessonTypeColor(lesson.type),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(25),
                ),
              ),
              child: Text(
                lesson.isCompleted ? 'Review Lesson' : 'Start Lesson',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _startLesson(BuildContext context) {
    // TODO: Navigate to appropriate lesson type page
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Starting ${lesson.title}...'),
        backgroundColor: _getLessonTypeColor(lesson.type),
      ),
    );
  }

  Color _getLessonTypeColor(LessonType type) {
    switch (type) {
      case LessonType.conversation:
        return const Color(0xFF4CAF50);
      case LessonType.writing:
        return const Color(0xFF2196F3);
      case LessonType.grammar:
        return const Color(0xFFFF9800);
      case LessonType.vocabulary:
        return const Color(0xFF9C27B0);
      case LessonType.pronunciation:
        return const Color(0xFFF44336);
      case LessonType.comprehension:
        return const Color(0xFF607D8B);
      case LessonType.mixed:
        return const Color(0xFF795548);
    }
  }

  IconData _getLessonTypeIcon(LessonType type) {
    switch (type) {
      case LessonType.conversation:
        return Icons.chat;
      case LessonType.writing:
        return Icons.edit;
      case LessonType.grammar:
        return Icons.spellcheck;
      case LessonType.vocabulary:
        return Icons.book;
      case LessonType.pronunciation:
        return Icons.record_voice_over;
      case LessonType.comprehension:
        return Icons.hearing;
      case LessonType.mixed:
        return Icons.extension;
    }
  }

  Color _getLevelColor(DifficultyLevel level) {
    switch (level) {
      case DifficultyLevel.a1:
      case DifficultyLevel.a2:
        return Colors.green;
      case DifficultyLevel.b1:
      case DifficultyLevel.b2:
        return Colors.orange;
      case DifficultyLevel.c1:
      case DifficultyLevel.c2:
        return Colors.red;
    }
  }
}
