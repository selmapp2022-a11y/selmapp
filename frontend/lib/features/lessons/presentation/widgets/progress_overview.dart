import 'package:flutter/material.dart';
import '../../data/models/lesson_models.dart';

class ProgressOverview extends StatelessWidget {
  final LearningProgress progress;

  const ProgressOverview({
    super.key,
    required this.progress,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
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
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF4CAF50).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.trending_up,
                  color: Color(0xFF4CAF50),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                'Your Progress',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: const Color(0xFF4CAF50),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          
          // Current Level
          Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  'Current Level',
                  progress.currentLevel.name.toUpperCase(),
                  Icons.school,
                  _getLevelColor(progress.currentLevel),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  'Study Time',
                  '${progress.totalStudyMinutes} min',
                  Icons.access_time,
                  Colors.blue,
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // Skills Progress
          Text(
            'Skills Overview',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          
          ...progress.skillScores.entries.map((entry) => 
            _buildSkillProgress(entry.key, entry.value)
          ),
          
          const SizedBox(height: 16),
          
          // Recent Activity
          Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  'Conversations',
                  progress.conversationCount.toString(),
                  Icons.chat,
                  Colors.green,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  'Writing Samples',
                  progress.writingCount.toString(),
                  Icons.edit,
                  Colors.purple,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            title,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[600],
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildSkillProgress(String skill, int score) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                skill.replaceFirst(skill[0], skill[0].toUpperCase()),
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
              Text(
                '$score%',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: _getScoreColor(score),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          LinearProgressIndicator(
            value: score / 100,
            backgroundColor: Colors.grey[200],
            valueColor: AlwaysStoppedAnimation<Color>(_getScoreColor(score)),
            minHeight: 6,
          ),
        ],
      ),
    );
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

  Color _getScoreColor(int score) {
    if (score >= 85) return Colors.green;
    if (score >= 70) return Colors.orange;
    return Colors.red;
  }
}

