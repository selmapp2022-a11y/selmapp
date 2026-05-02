import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';

class QuickActionsGrid extends StatelessWidget {
  const QuickActionsGrid({super.key});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      crossAxisSpacing: AppConstants.paddingM,
      mainAxisSpacing: AppConstants.paddingM,
      childAspectRatio: 1.2,
      children: [
        // Personal Learning Path - Featured at the top
        _buildFeaturedActionCard(
          context,
          'Personal Path',
          'Your learning journey',
          Icons.route,
          const LinearGradient(
            colors: [Color(0xFF667eea), Color(0xFF764ba2)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          () => context.push('/journey'),
        ),
        _buildActionCard(
          context,
          'Vocabulary',
          'Learn new words',
          Icons.book,
          AppTheme.primaryColor,
          () => context.push('/lessons?type=vocabulary'),
        ),
        _buildActionCard(
          context,
          'Grammar',
          'Master the rules',
          Icons.edit,
          AppTheme.secondaryColor,
          () => context.push('/lessons?type=grammar'),
        ),
        _buildActionCard(
          context,
          'Listening',
          'Train your ear',
          Icons.headphones,
          AppTheme.accentColor,
          () => context.push('/exercises?type=listening'),
        ),
        _buildActionCard(
          context,
          'Speaking',
          'Practice pronunciation',
          Icons.mic,
          AppTheme.errorColor,
          () => context.push('/exercises?type=speaking'),
        ),
        _buildActionCard(
          context,
          'Practice',
          'Mixed exercises',
          Icons.fitness_center,
          Colors.deepPurple,
          () => context.push('/practice'),
        ),
      ],
    );
  }

  Widget _buildFeaturedActionCard(
    BuildContext context,
    String title,
    String subtitle,
    IconData icon,
    Gradient gradient,
    VoidCallback onTap,
  ) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(AppConstants.paddingL),
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(AppConstants.radiusL),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 15,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Icon with special styling for featured card
            Container(
              padding: const EdgeInsets.all(AppConstants.paddingM),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(AppConstants.radiusM),
              ),
              child: Icon(icon, color: Colors.white, size: 28),
            ),
            const SizedBox(height: AppConstants.paddingM),

            // Title
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: AppConstants.paddingXS),

            // Subtitle
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.white.withValues(alpha: 0.8),
              ),
            ),

            const Spacer(),

            // Special indicator for featured card
            Align(
              alignment: Alignment.centerRight,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppConstants.paddingM,
                  vertical: AppConstants.paddingS,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(AppConstants.radiusM),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Start',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(width: 4),
                    const Icon(Icons.arrow_forward, color: Colors.white, size: 16),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionCard(
    BuildContext context,
    String title,
    String subtitle,
    IconData icon,
    Color color,
    VoidCallback onTap,
  ) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(AppConstants.paddingL),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              color.withValues(alpha: 0.1),
              color.withValues(alpha: 0.05),
            ],
          ),
          borderRadius: BorderRadius.circular(AppConstants.radiusL),
          border: Border.all(color: color.withValues(alpha: 0.2), width: 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Icon
            Container(
              padding: const EdgeInsets.all(AppConstants.paddingM),
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(AppConstants.radiusM),
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: 0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Icon(icon, color: Colors.white, size: 24),
            ),
            const SizedBox(height: AppConstants.paddingM),

            // Title
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            const SizedBox(height: AppConstants.paddingXS),

            // Subtitle
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondaryColor,
              ),
            ),

            const Spacer(),

            // Arrow indicator
            Align(
              alignment: Alignment.centerRight,
              child: Container(
                padding: const EdgeInsets.all(AppConstants.paddingS),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(AppConstants.radiusS),
                ),
                child: Icon(Icons.arrow_forward_ios, color: color, size: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
