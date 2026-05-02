import 'package:flutter/material.dart';
import '../../data/models/exercise_models.dart';
import '../../../../core/theme/app_theme.dart';

class ProgressHeaderWidget extends StatelessWidget {
  final UserProgress progress;

  const ProgressHeaderWidget({super.key, required this.progress});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        children: [
          // Header Section
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: AppTheme.primaryGradient,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(24),
                topRight: Radius.circular(24),
              ),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Your Progress',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        'Level ${progress.currentLevel.name.toUpperCase()}',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                _buildStreakBadge(context, progress.streakDays),
              ],
            ),
          ),

          // Stats Section
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: _buildStatCard(
                        context,
                        icon: Icons.star_rounded,
                        title: 'Points',
                        value: _formatNumber(progress.totalPoints),
                        color: Colors.amber,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildStatCard(
                        context,
                        icon: Icons.check_circle_rounded,
                        title: 'Completed',
                        value: progress.completedExercises.length.toString(),
                        color: Colors.green,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildStatCard(
                        context,
                        icon: Icons.trending_up_rounded,
                        title: 'Avg Score',
                        value: _calculateAverageScore(progress.skillLevels),
                        color: AppTheme.primaryColor,
                      ),
                    ),
                  ],
                ),

                // Skills Progress
                if (progress.skillLevels.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(
                          Icons.pie_chart_rounded,
                          color: AppTheme.primaryColor,
                          size: 18,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        'Skills Overview',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimaryColor,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _buildSkillsProgress(context, progress.skillLevels),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatNumber(int number) {
    if (number >= 1000) {
      return '${(number / 1000).toStringAsFixed(1)}K';
    }
    return number.toString();
  }

  Widget _buildStreakBadge(BuildContext context, int streakDays) {
    final isActive = streakDays > 0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isActive
              ? [Colors.orange, Colors.deepOrange]
              : [Colors.grey.shade400, Colors.grey.shade500],
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: isActive ? [
          BoxShadow(
            color: Colors.orange.withValues(alpha: 0.4),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ] : null,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.local_fire_department, color: Colors.white, size: 20),
          const SizedBox(width: 6),
          Text(
            '$streakDays',
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold,
              fontSize: 16,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            'day${streakDays != 1 ? 's' : ''}',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.9),
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String value,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            color.withValues(alpha: 0.1),
            color.withValues(alpha: 0.05),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(height: 10),
          Text(
            value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTheme.textSecondaryColor,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSkillsProgress(BuildContext context, Map<ExerciseType, int> skillLevels) {
    final sortedEntries = skillLevels.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return Column(
      children: sortedEntries.map((entry) {
        return Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: _buildSkillProgressBar(
            context,
            _getSkillName(entry.key),
            entry.value,
            _getSkillColor(entry.key),
            _getSkillIcon(entry.key),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSkillProgressBar(
    BuildContext context,
    String skillName,
    int level,
    Color color,
    IconData icon,
  ) {
    return Column(
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: color, size: 16),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                skillName,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textPrimaryColor,
                ),
              ),
            ),
            Text(
              '$level%',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Stack(
          children: [
            Container(
              height: 8,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            FractionallySizedBox(
              widthFactor: (level / 100).clamp(0.0, 1.0),
              child: Container(
                height: 8,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [color, color.withValues(alpha: 0.7)],
                  ),
                  borderRadius: BorderRadius.circular(4),
                  boxShadow: [
                    BoxShadow(
                      color: color.withValues(alpha: 0.3),
                      blurRadius: 4,
                      offset: const Offset(0, 1),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  String _calculateAverageScore(Map<ExerciseType, int> skillLevels) {
    if (skillLevels.isEmpty) return '0%';
    final total = skillLevels.values.reduce((a, b) => a + b);
    final average = total / skillLevels.length;
    return '${average.round()}%';
  }

  String _getSkillName(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary: return 'Vocabulary';
      case ExerciseType.grammar: return 'Grammar';
      case ExerciseType.reading: return 'Reading';
      case ExerciseType.listening: return 'Listening';
      case ExerciseType.speaking: return 'Speaking';
      case ExerciseType.writing: return 'Writing';
      case ExerciseType.conversation: return 'Conversation';
    }
  }

  IconData _getSkillIcon(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary: return Icons.menu_book;
      case ExerciseType.grammar: return Icons.spellcheck;
      case ExerciseType.reading: return Icons.article;
      case ExerciseType.listening: return Icons.headphones;
      case ExerciseType.speaking: return Icons.mic;
      case ExerciseType.writing: return Icons.edit;
      case ExerciseType.conversation: return Icons.chat;
    }
  }

  Color _getSkillColor(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary: return Colors.purple;
      case ExerciseType.grammar: return Colors.blue;
      case ExerciseType.reading: return Colors.green;
      case ExerciseType.listening: return Colors.orange;
      case ExerciseType.speaking: return Colors.red;
      case ExerciseType.writing: return Colors.teal;
      case ExerciseType.conversation: return Colors.pink;
    }
  }
}
