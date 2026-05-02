import 'package:flutter/material.dart';
import '../../data/models/exercise_models.dart';

class ExerciseCardWidget extends StatelessWidget {
  final Exercise exercise;
  final VoidCallback onTap;

  const ExerciseCardWidget({
    super.key,
    required this.exercise,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
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
              border: Border.all(color: Colors.grey[200]!),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.03),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              children: [
                // Exercise Type Icon
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: _getExerciseColor(exercise.type).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Icon(
                    _getExerciseIcon(exercise.type),
                    color: _getExerciseColor(exercise.type),
                    size: 24,
                  ),
                ),
                
                const SizedBox(width: 16),
                
                // Exercise Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        exercise.title,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: Colors.black87,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        exercise.description,
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey[600],
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          _buildInfoChip(
                            icon: Icons.schedule,
                            label: '${exercise.estimatedDurationMinutes} min',
                            color: Colors.blue,
                          ),
                          const SizedBox(width: 8),
                          _buildInfoChip(
                            icon: Icons.stars,
                            label: '${exercise.points} pts',
                            color: Colors.amber,
                          ),
                          const SizedBox(width: 8),
                          _buildLevelChip(exercise.level),
                        ],
                      ),
                    ],
                  ),
                ),
                
                // Status and Arrow
                Column(
                  children: [
                    _buildStatusIcon(exercise.status),
                    const SizedBox(height: 8),
                    Icon(
                      Icons.arrow_forward_ios,
                      color: Colors.grey[400],
                      size: 16,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInfoChip({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 12),
          const SizedBox(width: 2),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLevelChip(DifficultyLevel level) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: _getLevelColor(level).withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        level.name.toUpperCase(),
        style: TextStyle(
          color: _getLevelColor(level),
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildStatusIcon(ExerciseStatus status) {
    IconData icon;
    Color color;

    switch (status) {
      case ExerciseStatus.notStarted:
        icon = Icons.play_circle_outline;
        color = Colors.grey;
        break;
      case ExerciseStatus.inProgress:
        icon = Icons.pause_circle_outline;
        color = Colors.orange;
        break;
      case ExerciseStatus.completed:
        icon = Icons.check_circle;
        color = Colors.green;
        break;
      case ExerciseStatus.failed:
        icon = Icons.replay;
        color = Colors.red;
        break;
    }

    return Icon(icon, color: color, size: 20);
  }

  IconData _getExerciseIcon(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return Icons.menu_book;
      case ExerciseType.grammar:
        return Icons.rule;
      case ExerciseType.reading:
        return Icons.auto_stories;
      case ExerciseType.listening:
        return Icons.headphones;
      case ExerciseType.speaking:
        return Icons.record_voice_over;
      case ExerciseType.writing:
        return Icons.edit;
      case ExerciseType.conversation:
        return Icons.chat;
    }
  }

  Color _getExerciseColor(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return Colors.purple;
      case ExerciseType.grammar:
        return Colors.blue;
      case ExerciseType.reading:
        return Colors.green;
      case ExerciseType.listening:
        return Colors.orange;
      case ExerciseType.speaking:
        return Colors.red;
      case ExerciseType.writing:
        return Colors.teal;
      case ExerciseType.conversation:
        return Colors.pink;
    }
  }

  Color _getLevelColor(DifficultyLevel level) {
    switch (level) {
      case DifficultyLevel.a1:
        return Colors.green;
      case DifficultyLevel.a2:
        return Colors.lightGreen;
      case DifficultyLevel.b1:
        return Colors.blue;
      case DifficultyLevel.b2:
        return Colors.indigo;
      case DifficultyLevel.c1:
        return Colors.purple;
      case DifficultyLevel.c2:
        return Colors.red;
    }
  }
}
