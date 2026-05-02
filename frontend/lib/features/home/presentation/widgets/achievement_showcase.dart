import 'package:flutter/material.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';

class AchievementShowcase extends StatefulWidget {
  const AchievementShowcase({super.key});

  @override
  State<AchievementShowcase> createState() => _AchievementShowcaseState();
}

class _AchievementShowcaseState extends State<AchievementShowcase>
    with TickerProviderStateMixin {
  late AnimationController _shimmerController;
  late Animation<double> _shimmerAnimation;

  final List<Achievement> _achievements = [
    Achievement(
      title: 'First Steps',
      description: 'Complete your first lesson',
      icon: Icons.star,
      color: AppTheme.accentColor,
      isUnlocked: true,
    ),
    Achievement(
      title: 'Word Master',
      description: 'Learn 50 new words',
      icon: Icons.book,
      color: AppTheme.primaryColor,
      isUnlocked: true,
    ),
    Achievement(
      title: 'Grammar Guru',
      description: 'Complete 10 grammar exercises',
      icon: Icons.edit,
      color: AppTheme.secondaryColor,
      isUnlocked: true,
    ),
    Achievement(
      title: 'Streak Master',
      description: 'Maintain a 7-day streak',
      icon: Icons.local_fire_department,
      color: AppTheme.errorColor,
      isUnlocked: true,
    ),
    Achievement(
      title: 'Listening Pro',
      description: 'Complete 20 listening exercises',
      icon: Icons.headphones,
      color: AppTheme.warningColor,
      isUnlocked: false,
    ),
  ];

  @override
  void initState() {
    super.initState();
    _shimmerController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _shimmerAnimation = Tween<double>(begin: -1.0, end: 2.0).animate(
      CurvedAnimation(parent: _shimmerController, curve: Curves.easeInOut),
    );

    _shimmerController.repeat();
  }

  @override
  void dispose() {
    _shimmerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Achievements',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            TextButton(
              onPressed: () {
                // Navigate to achievements page
              },
              child: Text(
                'View All',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppTheme.primaryColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppConstants.paddingM),

        SizedBox(
          height: 120,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: _achievements.length,
            itemBuilder: (context, index) {
              final achievement = _achievements[index];
              return Padding(
                padding: EdgeInsets.only(
                  right: index == _achievements.length - 1
                      ? 0
                      : AppConstants.paddingM,
                ),
                child: _buildAchievementCard(achievement),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildAchievementCard(Achievement achievement) {
    return Container(
      width: 100,
      padding: const EdgeInsets.all(AppConstants.paddingM),
      decoration: BoxDecoration(
        gradient: achievement.isUnlocked
            ? LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  achievement.color.withValues(alpha: .1),
                  achievement.color.withValues(alpha: .05),
                ],
              )
            : LinearGradient(
                colors: [
                  AppTheme.borderColor.withValues(alpha: .5),
                  AppTheme.borderColor.withValues(alpha: 0.3),
                ],
              ),
        borderRadius: BorderRadius.circular(AppConstants.radiusL),
        border: Border.all(
          color: achievement.isUnlocked
              ? achievement.color.withValues(alpha: .3)
              : AppTheme.borderColor,
          width: 1,
        ),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Achievement Icon
          Stack(
            children: [
              Container(
                padding: const EdgeInsets.all(AppConstants.paddingM),
                decoration: BoxDecoration(
                  color: achievement.isUnlocked
                      ? achievement.color
                      : AppTheme.textTertiaryColor,
                  borderRadius: BorderRadius.circular(AppConstants.radiusM),
                  boxShadow: achievement.isUnlocked
                      ? [
                          BoxShadow(
                            color: achievement.color.withValues(alpha: 0.3),
                            blurRadius: 8,
                            offset: const Offset(0, 4),
                          ),
                        ]
                      : null,
                ),
                child: Icon(achievement.icon, color: Colors.white, size: 24),
              ),

              // Shimmer effect for unlocked achievements
              if (achievement.isUnlocked)
                Positioned.fill(
                  child: AnimatedBuilder(
                    animation: _shimmerAnimation,
                    builder: (context, child) {
                      return Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(
                            AppConstants.radiusM,
                          ),
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [
                              Colors.transparent,
                              Colors.white.withValues(alpha: 0.3),
                              Colors.transparent,
                            ],
                            stops: [
                              _shimmerAnimation.value - 0.3,
                              _shimmerAnimation.value,
                              _shimmerAnimation.value + 0.3,
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppConstants.paddingS),

          // Achievement Title
          Text(
            achievement.title,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: achievement.isUnlocked
                  ? AppTheme.textPrimaryColor
                  : AppTheme.textTertiaryColor,
            ),
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class Achievement {
  final String title;
  final String description;
  final IconData icon;
  final Color color;
  final bool isUnlocked;

  Achievement({
    required this.title,
    required this.description,
    required this.icon,
    required this.color,
    required this.isUnlocked,
  });
}
