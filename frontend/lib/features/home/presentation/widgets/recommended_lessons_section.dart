import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';

class RecommendedLessonsSection extends StatelessWidget {
  const RecommendedLessonsSection({super.key});

  final List<LessonCard> _lessons = const [
    LessonCard(
      title: 'Daily Conversations',
      subtitle: 'Essential phrases for everyday situations',
      level: 'B1',
      duration: '15 min',
      progress: 0.3,
      color: AppTheme.primaryColor,
      imageUrl: 'assets/images/conversation.png',
    ),
    LessonCard(
      title: 'Business English',
      subtitle: 'Professional communication skills',
      level: 'B2',
      duration: '20 min',
      progress: 0.0,
      color: AppTheme.secondaryColor,
      imageUrl: 'assets/images/business.png',
    ),
    LessonCard(
      title: 'Grammar Fundamentals',
      subtitle: 'Master the basic grammar rules',
      level: 'A2',
      duration: '12 min',
      progress: 0.8,
      color: AppTheme.accentColor,
      imageUrl: 'assets/images/grammar.png',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 200,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: _lessons.length,
        itemBuilder: (context, index) {
          final lesson = _lessons[index];
          return Padding(
            padding: EdgeInsets.only(
              right: index == _lessons.length - 1 ? 0 : AppConstants.paddingM,
            ),
            child: _buildLessonCard(context, lesson),
          );
        },
      ),
    );
  }

  Widget _buildLessonCard(BuildContext context, LessonCard lesson) {
    final levelColor = Color(
      AppConstants.levelColors[lesson.level] ?? 0xFF6366F1,
    );

    return GestureDetector(
      onTap: () => context.push(
        '/lessons/${lesson.title.toLowerCase().replaceAll(' ', '-')}',
      ),
      child: Container(
        width: 280,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              lesson.color.withValues(alpha: 0.1),
              lesson.color.withValues(alpha: 0.05),
            ],
          ),
          borderRadius: BorderRadius.circular(AppConstants.radiusL),
          border: Border.all(
            color: lesson.color.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with image placeholder and level badge
            Container(
              height: 100,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    lesson.color.withValues(alpha: 0.3),
                    lesson.color.withValues(alpha: 0.1),
                  ],
                ),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(AppConstants.radiusL),
                  topRight: Radius.circular(AppConstants.radiusL),
                ),
              ),
              child: Stack(
                children: [
                  // Placeholder for lesson image
                  Center(
                    child: Icon(
                      Icons.school,
                      size: 48,
                      color: lesson.color.withValues(alpha: 0.6),
                    ),
                  ),

                  // Level badge
                  Positioned(
                    top: AppConstants.paddingM,
                    right: AppConstants.paddingM,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppConstants.paddingS,
                        vertical: AppConstants.paddingXS,
                      ),
                      decoration: BoxDecoration(
                        color: levelColor,
                        borderRadius: BorderRadius.circular(
                          AppConstants.radiusS,
                        ),
                      ),
                      child: Text(
                        lesson.level,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),

                  // Progress indicator (if lesson is started)
                  if (lesson.progress > 0)
                    Positioned(
                      top: AppConstants.paddingM,
                      left: AppConstants.paddingM,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppConstants.paddingS,
                          vertical: AppConstants.paddingXS,
                        ),
                        decoration: BoxDecoration(
                          color: AppTheme.successColor,
                          borderRadius: BorderRadius.circular(
                            AppConstants.radiusS,
                          ),
                        ),
                        child: Text(
                          '${(lesson.progress * 100).toInt()}%',
                          style: Theme.of(context).textTheme.labelSmall
                              ?.copyWith(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                              ),
                        ),
                      ),
                    ),
                ],
              ),
            ),

            // Content
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(AppConstants.paddingM),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Title
                    Text(
                      lesson.title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimaryColor,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: AppConstants.paddingXS),

                    // Subtitle
                    Text(
                      lesson.subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTheme.textSecondaryColor,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),

                    const Spacer(),

                    // Duration and action
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.access_time,
                              size: 16,
                              color: AppTheme.textTertiaryColor,
                            ),
                            const SizedBox(width: AppConstants.paddingXS),
                            Text(
                              lesson.duration,
                              style: Theme.of(context).textTheme.bodySmall
                                  ?.copyWith(color: AppTheme.textTertiaryColor),
                            ),
                          ],
                        ),
                        Container(
                          padding: const EdgeInsets.all(AppConstants.paddingS),
                          decoration: BoxDecoration(
                            color: lesson.color.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(
                              AppConstants.radiusS,
                            ),
                          ),
                          child: Icon(
                            lesson.progress > 0
                                ? Icons.play_arrow
                                : Icons.play_circle_outline,
                            color: lesson.color,
                            size: 16,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class LessonCard {
  final String title;
  final String subtitle;
  final String level;
  final String duration;
  final double progress;
  final Color color;
  final String imageUrl;

  const LessonCard({
    required this.title,
    required this.subtitle,
    required this.level,
    required this.duration,
    required this.progress,
    required this.color,
    required this.imageUrl,
  });
}
