import 'package:flutter/material.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';

class LearningStreakCard extends StatefulWidget {
  final int currentStreak;
  final int longestStreak;
  final VoidCallback onTap;

  const LearningStreakCard({
    super.key,
    required this.currentStreak,
    required this.longestStreak,
    required this.onTap,
  });

  @override
  State<LearningStreakCard> createState() => _LearningStreakCardState();
}

class _LearningStreakCardState extends State<LearningStreakCard>
    with TickerProviderStateMixin {
  late AnimationController _fireAnimationController;
  late AnimationController _scaleAnimationController;
  late Animation<double> _fireAnimation;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();

    _fireAnimationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _scaleAnimationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _fireAnimation = Tween<double>(begin: 0.8, end: 1.2).animate(
      CurvedAnimation(
        parent: _fireAnimationController,
        curve: Curves.easeInOut,
      ),
    );

    _scaleAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _scaleAnimationController,
        curve: Curves.elasticOut,
      ),
    );

    _fireAnimationController.repeat(reverse: true);
    _scaleAnimationController.forward();
  }

  @override
  void dispose() {
    _fireAnimationController.dispose();
    _scaleAnimationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scaleAnimation,
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          padding: const EdgeInsets.all(AppConstants.paddingL),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                AppTheme.errorColor.withValues(alpha: 0.1),
                AppTheme.accentColor.withValues(alpha: 0.1),
              ],
            ),
            borderRadius: BorderRadius.circular(AppConstants.radiusL),
            border: Border.all(
              color: AppTheme.errorColor.withValues(alpha: 0.2),
              width: 1,
            ),
          ),
          child: Row(
            children: [
              // Fire Icon with Animation
              AnimatedBuilder(
                animation: _fireAnimation,
                builder: (context, child) {
                  return Transform.scale(
                    scale: _fireAnimation.value,
                    child: Container(
                      padding: const EdgeInsets.all(AppConstants.paddingM),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [AppTheme.errorColor, AppTheme.accentColor],
                        ),
                        borderRadius: BorderRadius.circular(
                          AppConstants.radiusM,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: AppTheme.errorColor.withValues(alpha: 0.3),
                            blurRadius: 8,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.local_fire_department,
                        color: Colors.white,
                        size: 32,
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(width: AppConstants.paddingL),

              // Streak Information
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Learning Streak',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppTheme.textSecondaryColor,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: AppConstants.paddingXS),
                    Row(
                      children: [
                        Text(
                          '${widget.currentStreak}',
                          style: Theme.of(context).textTheme.displaySmall
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.errorColor,
                              ),
                        ),
                        const SizedBox(width: AppConstants.paddingS),
                        Text(
                          'days',
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(
                                color: AppTheme.textPrimaryColor,
                                fontWeight: FontWeight.w500,
                              ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppConstants.paddingXS),
                    Row(
                      children: [
                        Icon(
                          Icons.emoji_events_outlined,
                          size: 16,
                          color: AppTheme.accentColor,
                        ),
                        const SizedBox(width: AppConstants.paddingXS),
                        Text(
                          'Best: ${widget.longestStreak} days',
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(color: AppTheme.textSecondaryColor),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // Achievement Badge
              if (widget.currentStreak >= 7)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppConstants.paddingM,
                    vertical: AppConstants.paddingS,
                  ),
                  decoration: BoxDecoration(
                    color: AppTheme.successColor.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(AppConstants.radiusM),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.star, color: AppTheme.successColor, size: 20),
                      const SizedBox(height: AppConstants.paddingXS),
                      Text(
                        'Hot!',
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppTheme.successColor,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
