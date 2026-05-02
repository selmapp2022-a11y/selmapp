import 'package:flutter/material.dart';
import '../../data/models/lesson_models.dart';

class LessonCard extends StatelessWidget {
  final Lesson lesson;
  final VoidCallback onTap;

  const LessonCard({
    super.key,
    required this.lesson,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: lesson.isCompleted
                  ? Border.all(color: Colors.green.withValues(alpha: 0.3))
                  : null,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: lesson.isCompleted
                        ? Colors.green.withValues(alpha: 0.1)
                        : _getLessonTypeColor(lesson.type).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(25),
                  ),
                  child: Icon(
                    lesson.isCompleted
                        ? Icons.check_circle
                        : _getLessonTypeIcon(lesson.type),
                    color: lesson.isCompleted
                        ? Colors.green
                        : _getLessonTypeColor(lesson.type),
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              lesson.title,
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                              ),
                            ),
                          ),
                          if (lesson.isCompleted && lesson.userScore != null)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.green.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                '${lesson.userScore}%',
                                style: const TextStyle(
                                  color: Colors.green,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        lesson.description,
                        style: TextStyle(
                          color: Colors.grey[600],
                          fontSize: 12,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: _getLevelColor(lesson.level).withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              lesson.level.name.toUpperCase(),
                              style: TextStyle(
                                color: _getLevelColor(lesson.level),
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Icon(
                            Icons.access_time,
                            size: 12,
                            color: Colors.grey[500],
                          ),
                          const SizedBox(width: 4),
                          Text(
                            '${lesson.estimatedMinutes} min',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Icon(
                  Icons.arrow_forward_ios,
                  size: 16,
                  color: Colors.grey[400],
                ),
              ],
            ),
          ),
        ),
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

