import 'package:flutter/material.dart';

import '../../data/models/admin_models.dart';

/// A simple bar chart that visualises daily activity summaries on the admin
/// dashboard. Uses only core Flutter widgets (no third-party charting library)
/// so the build stays lightweight.
class AdminActivityChart extends StatelessWidget {
  final List<UserActivitySummary> activity;

  const AdminActivityChart({super.key, required this.activity});

  @override
  Widget build(BuildContext context) {
    if (activity.isEmpty) {
      return const SizedBox.shrink();
    }

    // Determine the max value across all metrics so bars can be scaled.
    int maxValue = 1;
    for (final day in activity) {
      final dayMax = [
        day.activeUsers,
        day.newRegistrations,
        day.lessonsCompleted,
        day.exercisesCompleted,
      ].reduce((a, b) => a > b ? a : b);
      if (dayMax > maxValue) maxValue = dayMax;
    }

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Legend
            Wrap(
              spacing: 16,
              runSpacing: 4,
              children: [
                _legendDot(Colors.blue, 'Active'),
                _legendDot(Colors.green, 'New'),
                _legendDot(Colors.orange, 'Lessons'),
                _legendDot(Colors.purple, 'Exercises'),
              ],
            ),
            const SizedBox(height: 16),
            // Bars
            ...activity.map((day) => _buildRow(context, day, maxValue)),
          ],
        ),
      ),
    );
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
    );
  }

  Widget _buildRow(BuildContext context, UserActivitySummary day, int maxValue) {
    // Parse the date label – show only MM/DD
    String dateLabel = day.date;
    try {
      final dt = DateTime.parse(day.date);
      dateLabel = '${dt.month}/${dt.day}';
    } catch (_) {}

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 40,
            child: Text(
              dateLabel,
              style: TextStyle(fontSize: 11, color: Colors.grey[600]),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              children: [
                _bar(day.activeUsers, maxValue, Colors.blue),
                const SizedBox(height: 2),
                _bar(day.newRegistrations, maxValue, Colors.green),
                const SizedBox(height: 2),
                _bar(day.lessonsCompleted, maxValue, Colors.orange),
                const SizedBox(height: 2),
                _bar(day.exercisesCompleted, maxValue, Colors.purple),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _bar(int value, int maxValue, Color color) {
    final fraction = maxValue > 0 ? (value / maxValue).clamp(0.0, 1.0) : 0.0;
    return Row(
      children: [
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              return Align(
                alignment: Alignment.centerLeft,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 400),
                  curve: Curves.easeOut,
                  height: 6,
                  width: constraints.maxWidth * fraction,
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.75),
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
              );
            },
          ),
        ),
        const SizedBox(width: 6),
        SizedBox(
          width: 24,
          child: Text(
            '$value',
            style: TextStyle(fontSize: 10, color: Colors.grey[600]),
          ),
        ),
      ],
    );
  }
}
