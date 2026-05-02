import 'package:flutter/material.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';

class ProgressOverviewCard extends StatefulWidget {
  final String currentLevel;
  final double progress;
  final VoidCallback onTap;

  const ProgressOverviewCard({
    super.key,
    required this.currentLevel,
    required this.progress,
    required this.onTap,
  });

  @override
  State<ProgressOverviewCard> createState() => _ProgressOverviewCardState();
}

class _ProgressOverviewCardState extends State<ProgressOverviewCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _progressAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _progressAnimation = Tween<double>(begin: 0.0, end: widget.progress)
        .animate(
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
    final levelColor = Color(
      AppConstants.levelColors[widget.currentLevel] ?? 0xFF6366F1,
    );

    return GestureDetector(
      onTap: widget.onTap,
      child: Container(
        padding: const EdgeInsets.all(AppConstants.paddingL),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              levelColor.withValues(alpha: 0.1),
              levelColor.withValues(alpha: 0.05),
            ],
          ),
          borderRadius: BorderRadius.circular(AppConstants.radiusL),
          border: Border.all(
            color: levelColor.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppConstants.paddingM,
                    vertical: AppConstants.paddingS,
                  ),
                  decoration: BoxDecoration(
                    color: levelColor,
                    borderRadius: BorderRadius.circular(AppConstants.radiusM),
                  ),
                  child: Text(
                    widget.currentLevel,
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Icon(Icons.trending_up, color: levelColor, size: 20),
              ],
            ),
            const SizedBox(height: AppConstants.paddingM),
            Text(
              'Current Level',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondaryColor,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: AppConstants.paddingXS),
            Text(
              '${(widget.progress * 100).toInt()}% Complete',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            const SizedBox(height: AppConstants.paddingM),

            // Progress Bar
            Container(
              height: 8,
              decoration: BoxDecoration(
                color: levelColor.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(4),
              ),
              child: AnimatedBuilder(
                animation: _progressAnimation,
                builder: (context, child) {
                  return FractionallySizedBox(
                    alignment: Alignment.centerLeft,
                    widthFactor: _progressAnimation.value,
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            levelColor,
                            levelColor.withValues(alpha: 0.8),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: AppConstants.paddingS),

            // Next Level Info
            Row(
              children: [
                Icon(
                  Icons.flag_outlined,
                  size: 14,
                  color: AppTheme.textTertiaryColor,
                ),
                const SizedBox(width: AppConstants.paddingXS),
                Text(
                  'Next: ${_getNextLevel(widget.currentLevel)}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textTertiaryColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _getNextLevel(String currentLevel) {
    final levels = AppConstants.cefrLevels;
    final currentIndex = levels.indexOf(currentLevel);
    if (currentIndex >= 0 && currentIndex < levels.length - 1) {
      return levels[currentIndex + 1];
    }
    return 'Mastery';
  }
}
