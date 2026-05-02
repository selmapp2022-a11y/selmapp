import 'package:flutter/material.dart';
import '../../data/models/exercise_models.dart';

class LearningSessionWidget extends StatelessWidget {
  final LearningSession session;
  final VoidCallback onTap;

  const LearningSessionWidget({
    super.key,
    required this.session,
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
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header Row
                Row(
                  children: [
                    Container(
                      width: 50,
                      height: 50,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: _getLevelGradient(session.level),
                        ),
                        borderRadius: BorderRadius.circular(25),
                      ),
                      child: const Icon(
                        Icons.school,
                        color: Colors.white,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            session.title,
                            style: Theme.of(context).textTheme.titleLarge
                                ?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.grey[800],
                                ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Level ${session.level.name.toUpperCase()}',
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(
                                  color: const Color(0xFF2196F3),
                                  fontWeight: FontWeight.w600,
                                ),
                          ),
                        ],
                      ),
                    ),
                    _buildStatusBadge(session.status),
                  ],
                ),

                const SizedBox(height: 16),

                // Session Info
                Row(
                  children: [
                    _buildInfoChip(
                      icon: Icons.timer,
                      label: '${session.totalDurationMinutes} min',
                      color: Colors.blue,
                    ),
                    const SizedBox(width: 8),
                    _buildInfoChip(
                      icon: Icons.stars,
                      label: '${session.totalPoints} pts',
                      color: Colors.amber,
                    ),
                    const SizedBox(width: 8),
                    _buildInfoChip(
                      icon: Icons.assignment,
                      label: '${session.exercises.length} exercises',
                      color: Colors.green,
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // Focus Areas
                if (session.focusAreas.isNotEmpty) ...[
                  Text(
                    'Focus Areas',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: Colors.grey[700],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: session.focusAreas.map((area) {
                      return Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: const Color(0xFF2196F3).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: const Color(
                              0xFF2196F3,
                            ).withValues(alpha: 0.3),
                          ),
                        ),
                        child: Text(
                          area.toUpperCase(),
                          style: const TextStyle(
                            color: Color(0xFF2196F3),
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 16),
                ],

                // AI Trainer Introduction
                if (session.trainerIntroduction != null) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.grey[50],
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.grey[200]!),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.smart_toy,
                          color: Colors.grey[600],
                          size: 20,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            session.trainerIntroduction!.message,
                            style: TextStyle(
                              color: Colors.grey[700],
                              fontSize: 13,
                              fontStyle: FontStyle.italic,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                ],

                // Progress Bar
                _buildProgressBar(session),

                const SizedBox(height: 12),

                // Action Button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: onTap,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF2196F3),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: Text(
                      _getActionButtonText(session.status),
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStatusBadge(SessionStatus status) {
    Color color;
    String text;
    IconData icon;

    switch (status) {
      case SessionStatus.notStarted:
        color = Colors.grey;
        text = 'New';
        icon = Icons.fiber_new;
        break;
      case SessionStatus.inProgress:
        color = Colors.orange;
        text = 'In Progress';
        icon = Icons.play_circle;
        break;
      case SessionStatus.completed:
        color = Colors.green;
        text = 'Completed';
        icon = Icons.check_circle;
        break;
      case SessionStatus.paused:
        color = Colors.blue;
        text = 'Paused';
        icon = Icons.pause_circle;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 4),
          Text(
            text,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoChip({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressBar(LearningSession session) {
    double progress = 0.0;

    switch (session.status) {
      case SessionStatus.notStarted:
        progress = 0.0;
        break;
      case SessionStatus.inProgress:
        progress = 0.4; // Mock progress
        break;
      case SessionStatus.completed:
        progress = 1.0;
        break;
      case SessionStatus.paused:
        progress = 0.6; // Mock progress
        break;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Progress',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: Colors.grey[600],
              ),
            ),
            Text(
              '${(progress * 100).round()}%',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: Colors.grey[700],
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: progress,
          backgroundColor: Colors.grey[200],
          valueColor: AlwaysStoppedAnimation<Color>(
            progress == 1.0 ? Colors.green : const Color(0xFF2196F3),
          ),
          minHeight: 4,
        ),
      ],
    );
  }

  List<Color> _getLevelGradient(DifficultyLevel level) {
    switch (level) {
      case DifficultyLevel.a1:
        return [Colors.green, Colors.lightGreen];
      case DifficultyLevel.a2:
        return [Colors.lightGreen, Colors.lime];
      case DifficultyLevel.b1:
        return [Colors.blue, Colors.lightBlue];
      case DifficultyLevel.b2:
        return [Colors.indigo, Colors.blue];
      case DifficultyLevel.c1:
        return [Colors.purple, Colors.deepPurple];
      case DifficultyLevel.c2:
        return [Colors.red, Colors.pink];
    }
  }

  String _getActionButtonText(SessionStatus status) {
    switch (status) {
      case SessionStatus.notStarted:
        return 'Start Session';
      case SessionStatus.inProgress:
        return 'Continue';
      case SessionStatus.completed:
        return 'Review';
      case SessionStatus.paused:
        return 'Resume';
    }
  }
}
