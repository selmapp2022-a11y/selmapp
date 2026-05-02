import 'package:flutter/material.dart';
import '../../data/models/lesson_models.dart';

class StudyPlanCard extends StatelessWidget {
  final PersonalStudyPlan studyPlan;
  final VoidCallback onTap;

  const StudyPlanCard({
    super.key,
    required this.studyPlan,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Container(
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
                        color: _getTypeColor(studyPlan.type).withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        _getTypeIcon(studyPlan.type),
                        color: _getTypeColor(studyPlan.type),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            studyPlan.title,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            studyPlan.type.name.toUpperCase(),
                            style: TextStyle(
                              fontSize: 12,
                              color: _getTypeColor(studyPlan.type),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.green.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${studyPlan.progressPercentage.toInt()}%',
                        style: const TextStyle(
                          color: Colors.green,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  studyPlan.description,
                  style: TextStyle(
                    color: Colors.grey[600],
                    fontSize: 14,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 16),
                LinearProgressIndicator(
                  value: studyPlan.progressPercentage / 100,
                  backgroundColor: Colors.grey[200],
                  valueColor: AlwaysStoppedAnimation<Color>(_getTypeColor(studyPlan.type)),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Text(
                      '${studyPlan.completedLessons}/${studyPlan.totalLessons} lessons',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[600],
                      ),
                    ),
                    const Spacer(),
                    Text(
                      '${studyPlan.estimatedDays} days',
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
        ),
      ),
    );
  }

  Color _getTypeColor(StudyPlanType type) {
    switch (type) {
      case StudyPlanType.daily:
        return const Color(0xFF4CAF50);
      case StudyPlanType.weekly:
        return const Color(0xFF2196F3);
      case StudyPlanType.intensive:
        return const Color(0xFFFF5722);
      case StudyPlanType.custom:
        return const Color(0xFF9C27B0);
    }
  }

  IconData _getTypeIcon(StudyPlanType type) {
    switch (type) {
      case StudyPlanType.daily:
        return Icons.today;
      case StudyPlanType.weekly:
        return Icons.date_range;
      case StudyPlanType.intensive:
        return Icons.flash_on;
      case StudyPlanType.custom:
        return Icons.tune;
    }
  }
}

