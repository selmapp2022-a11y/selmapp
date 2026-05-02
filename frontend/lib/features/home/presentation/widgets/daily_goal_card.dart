import 'package:flutter/material.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';

class DailyGoalCard extends StatefulWidget {
  final int goalMinutes;
  final int completedMinutes;
  final VoidCallback onTap;

  const DailyGoalCard({
    super.key,
    required this.goalMinutes,
    required this.completedMinutes,
    required this.onTap,
  });

  @override
  State<DailyGoalCard> createState() => _DailyGoalCardState();
}

class _DailyGoalCardState extends State<DailyGoalCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _progressAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );

    final progress = widget.completedMinutes / widget.goalMinutes;
    _progressAnimation =
        Tween<double>(begin: 0.0, end: progress.clamp(0.0, 1.0)).animate(
          CurvedAnimation(
            parent: _animationController,
            curve: Curves.easeOutCubic,
          ),
        );

    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final progress = widget.completedMinutes / widget.goalMinutes;
    final isCompleted = progress >= 1.0;
    final progressColor = isCompleted
        ? AppTheme.successColor
        : AppTheme.primaryColor;

    return GestureDetector(
      onTap: widget.onTap,
      child: Container(
        padding: const EdgeInsets.all(AppConstants.paddingL),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              progressColor.withValues(alpha: 0.1),
              progressColor.withValues(alpha: 0.05),
            ],
          ),
          borderRadius: BorderRadius.circular(AppConstants.radiusL),
          border: Border.all(
            color: progressColor.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with icon
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.all(AppConstants.paddingS),
                  decoration: BoxDecoration(
                    color: progressColor,
                    borderRadius: BorderRadius.circular(AppConstants.radiusS),
                  ),
                  child: Icon(
                    isCompleted ? Icons.check : Icons.access_time,
                    color: Colors.white,
                    size: 16,
                  ),
                ),
                if (isCompleted)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppConstants.paddingS,
                      vertical: AppConstants.paddingXS,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.successColor.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(AppConstants.radiusS),
                    ),
                    child: Text(
                      'Done!',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: AppTheme.successColor,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: AppConstants.paddingM),

            // Title
            Text(
              'Daily Goal',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondaryColor,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: AppConstants.paddingXS),

            // Progress text
            Text(
              '${widget.completedMinutes}/${widget.goalMinutes}',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            Text(
              'minutes',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondaryColor,
              ),
            ),
            const SizedBox(height: AppConstants.paddingM),

            // Circular Progress Indicator
            Center(
              child: SizedBox(
                width: 60,
                height: 60,
                child: AnimatedBuilder(
                  animation: _progressAnimation,
                  builder: (context, child) {
                    return Stack(
                      children: [
                        // Background circle
                        Container(
                          width: 60,
                          height: 60,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: progressColor.withValues(alpha: 0.2),
                          ),
                        ),
                        // Progress circle
                        CircularProgressIndicator(
                          value: _progressAnimation.value,
                          strokeWidth: 6,
                          backgroundColor: Colors.transparent,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            progressColor,
                          ),
                        ),
                        // Center text
                        Center(
                          child: Text(
                            '${(_progressAnimation.value * 100).toInt()}%',
                            style: Theme.of(context).textTheme.labelMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: progressColor,
                                ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
            const SizedBox(height: AppConstants.paddingS),

            // Remaining time
            if (!isCompleted)
              Center(
                child: Text(
                  '${widget.goalMinutes - widget.completedMinutes} min left',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textTertiaryColor,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
