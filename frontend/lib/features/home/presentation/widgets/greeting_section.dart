import 'package:flutter/material.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';

class GreetingSection extends StatelessWidget {
  const GreetingSection({super.key});

  @override
  Widget build(BuildContext context) {
    final hour = DateTime.now().hour;
    final greeting = _getGreeting(hour);
    final motivationalMessage = _getMotivationalMessage();

    return Container(
      padding: const EdgeInsets.all(AppConstants.paddingL),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppTheme.accentColor.withValues(alpha: 0.1),
            AppTheme.secondaryColor.withValues(alpha: 0.1),
          ],
        ),
        borderRadius: BorderRadius.circular(AppConstants.radiusL),
        border: Border.all(
          color: AppTheme.accentColor.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(AppConstants.paddingM),
            decoration: BoxDecoration(
              color: AppTheme.accentColor,
              borderRadius: BorderRadius.circular(AppConstants.radiusM),
            ),
            child: Icon(_getGreetingIcon(hour), color: Colors.white, size: 32),
          ),
          const SizedBox(width: AppConstants.paddingM),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$greeting!',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimaryColor,
                  ),
                ),
                const SizedBox(height: AppConstants.paddingXS),
                Text(
                  motivationalMessage,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppTheme.textSecondaryColor,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(AppConstants.paddingS),
            decoration: BoxDecoration(
              color: AppTheme.successColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(AppConstants.radiusS),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.local_fire_department,
                  color: AppTheme.errorColor,
                  size: 16,
                ),
                const SizedBox(width: AppConstants.paddingXS),
                Text(
                  '7',
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.errorColor,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _getGreeting(int hour) {
    if (hour < 12) {
      return 'Good Morning';
    } else if (hour < 17) {
      return 'Good Afternoon';
    } else {
      return 'Good Evening';
    }
  }

  IconData _getGreetingIcon(int hour) {
    if (hour < 12) {
      return Icons.wb_sunny;
    } else if (hour < 17) {
      return Icons.wb_cloudy;
    } else {
      return Icons.nights_stay;
    }
  }

  String _getMotivationalMessage() {
    final messages = [
      'Ready to boost your English today?',
      'Let\'s continue your learning journey!',
      'Time to practice and improve!',
      'Your English skills are growing!',
      'Every lesson brings you closer to fluency!',
      'Keep up the amazing progress!',
    ];

    final now = DateTime.now();
    final index = now.day % messages.length;
    return messages[index];
  }
}
