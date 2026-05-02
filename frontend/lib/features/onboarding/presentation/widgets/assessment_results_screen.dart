import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lottie/lottie.dart';

import '../../data/models/onboarding_models.dart';
import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';

class AssessmentResultsScreen extends StatefulWidget {
  final AssessmentResultsState state;

  const AssessmentResultsScreen({super.key, required this.state});

  @override
  State<AssessmentResultsScreen> createState() =>
      _AssessmentResultsScreenState();
}

class _AssessmentResultsScreenState extends State<AssessmentResultsScreen>
    with TickerProviderStateMixin {
  late AnimationController _mainAnimationController;
  late AnimationController _celebrationController;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();

    _mainAnimationController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );

    _celebrationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainAnimationController,
        curve: const Interval(0.0, 0.6, curve: Curves.easeOut),
      ),
    );

    _scaleAnimation = Tween<double>(begin: 0.8, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainAnimationController,
        curve: const Interval(0.2, 0.8, curve: Curves.elasticOut),
      ),
    );

    _slideAnimation =
        Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero).animate(
          CurvedAnimation(
            parent: _mainAnimationController,
            curve: const Interval(0.4, 1.0, curve: Curves.elasticOut),
          ),
        );

    _mainAnimationController.forward();
    _celebrationController.forward();
  }

  @override
  void dispose() {
    _mainAnimationController.dispose();
    _celebrationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final result = widget.state.assessmentResult;

    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Assessment Results',
        showProgress: true,
        progress: 0.9, // 90% through onboarding
      ),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                // Celebration Animation & Level
                ScaleTransition(
                  scale: _scaleAnimation,
                  child: _buildLevelDisplay(result),
                ),

                const SizedBox(height: 32),

                // Overall Score
                SlideTransition(
                  position: _slideAnimation,
                  child: _buildOverallScore(result),
                ),

                const SizedBox(height: 24),

                // Skill Breakdown
                _buildSkillBreakdown(result),

                const SizedBox(height: 24),

                // AI Feedback
                _buildAIFeedback(result),

                const SizedBox(height: 24),

                // Recommendations
                _buildRecommendations(result),

                const SizedBox(height: 32),

                // Action Button
                AnimatedOnboardingButton(
                  text: 'Create My Learning Plan',
                  icon: Icons.auto_awesome,
                  onPressed: () {
                    context.read<OnboardingBloc>().add(
                      GenerateLearningPathEvent(),
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLevelDisplay(AssessmentResult result) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
            Theme.of(context).colorScheme.secondary.withValues(alpha: 0.1),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        children: [
          // Celebration Animation
          SizedBox(
            height: 100,
            child: Lottie.asset(
              'assets/animations/celebration.json',
              controller: _celebrationController,
              fit: BoxFit.contain,
            ),
          ),

          const SizedBox(height: 16),

          // Level Badge
          Container(
            width: 120,
            height: 120,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Theme.of(context).colorScheme.primary,
                  Theme.of(context).colorScheme.secondary,
                ],
              ),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Theme.of(
                    context,
                  ).colorScheme.primary.withValues(alpha: 0.3),
                  blurRadius: 20,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Center(
              child: Text(
                result.determinedLevel.code,
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                  color: Theme.of(context).colorScheme.onPrimary,
                  fontWeight: FontWeight.bold,
                  fontSize: 36,
                ),
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Level Name
          Text(
            result.determinedLevel.name,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),

          const SizedBox(height: 8),

          // Level Description
          Text(
            result.determinedLevel.description,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildOverallScore(AssessmentResult result) {
    final safeScore = _normalizeScore(result.overallScore);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(
            Icons.emoji_events,
            size: 48,
            color: Theme.of(context).colorScheme.primary,
          ),

          const SizedBox(width: 16),

          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Overall Score',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '${safeScore.round()}',
                      style: Theme.of(context).textTheme.headlineMedium
                          ?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                    ),
                    Text(
                      ' / 100',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Score Indicator
          SizedBox(
            width: 60,
            height: 60,
            child: CircularProgressIndicator(
              value: (safeScore / 100).clamp(0.0, 1.0),
              strokeWidth: 6,
              backgroundColor: Theme.of(
                context,
              ).colorScheme.outline.withValues(alpha: 0.3),
              valueColor: AlwaysStoppedAnimation<Color>(
                Theme.of(context).colorScheme.primary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSkillBreakdown(AssessmentResult result) {
    final skillEntries = result.skillScores.entries
        .where((entry) => entry.value.isFinite && !entry.value.isNaN)
        .toList();

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.bar_chart,
                color: Theme.of(context).colorScheme.primary,
                size: 24,
              ),
              const SizedBox(width: 12),
              Text(
                'Skill Breakdown',
                style: Theme.of(
                  context,
                ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
              ),
            ],
          ),

          const SizedBox(height: 20),

          if (skillEntries.isEmpty)
            Text(
              'We\'ll show per-skill performance once the assessment provides enough data.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            )
          else
            ...skillEntries.map((entry) {
              final skill = entry.key;
              final scoreValue = _normalizeScore(
                entry.value,
                fallback: _normalizeScore(result.overallScore),
              );
              final targetProgress = (scoreValue / 100).clamp(0.0, 1.0);

              return TweenAnimationBuilder<double>(
                duration: const Duration(milliseconds: 800),
                tween: Tween<double>(begin: 0.0, end: targetProgress),
                curve: Curves.easeInOut,
                builder: (context, value, child) {
                  final clampedValue = value.clamp(0.0, 1.0);
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  _getSkillIcon(skill),
                                  size: 20,
                                  color: _getSkillColor(skill),
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  _capitalizeSkill(skill),
                                  style: Theme.of(context).textTheme.titleSmall
                                      ?.copyWith(fontWeight: FontWeight.w500),
                                ),
                              ],
                            ),
                            Text(
                              '${scoreValue.round()}%',
                              style: Theme.of(context).textTheme.titleSmall
                                  ?.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: _getSkillColor(skill),
                                  ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        LinearProgressIndicator(
                          value: clampedValue,
                          backgroundColor: Theme.of(
                            context,
                          ).colorScheme.outline.withValues(alpha: 0.2),
                          valueColor: AlwaysStoppedAnimation<Color>(
                            _getSkillColor(skill),
                          ),
                        ),
                      ],
                    ),
                  );
                },
              );
            }),
        ],
      ),
    );
  }

  Widget _buildAIFeedback(AssessmentResult result) {
    final feedbackText = _feedbackText(result);
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Theme.of(
              context,
            ).colorScheme.tertiaryContainer.withValues(alpha: 0.3),
            Theme.of(
              context,
            ).colorScheme.tertiaryContainer.withValues(alpha: 0.1),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.tertiary.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.psychology,
                color: Theme.of(context).colorScheme.tertiary,
                size: 24,
              ),
              const SizedBox(width: 12),
              Text(
                'AI Feedback',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: Theme.of(context).colorScheme.tertiary,
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          Text(
            feedbackText,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendations(AssessmentResult result) {
    final sanitizedRecommendations = result.recommendations
        .map((r) => r.trim())
        .where((r) => r.isNotEmpty)
        .toList();

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.lightbulb,
                color: Theme.of(context).colorScheme.secondary,
                size: 24,
              ),
              const SizedBox(width: 12),
              Text(
                'Personalized Recommendations',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: Theme.of(context).colorScheme.secondary,
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          if (sanitizedRecommendations.isEmpty)
            Text(
              'We\'ll add personalized tips once the AI has more insights from your study history.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
            )
          else
            ...sanitizedRecommendations.asMap().entries.map((entry) {
              final index = entry.key;
              final recommendation = entry.value;

              return TweenAnimationBuilder<double>(
                duration: Duration(milliseconds: 600 + (index * 200)),
                tween: Tween<double>(begin: 0.0, end: 1.0),
                curve: Curves.elasticOut,
                builder: (context, value, child) {
                  final clampedValue = value.clamp(0.0, 1.0);
                  return Transform.translate(
                    offset: Offset(20 * (1 - clampedValue), 0),
                    child: Opacity(opacity: clampedValue, child: child),
                  );
                },
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 24,
                        height: 24,
                        margin: const EdgeInsets.only(top: 2),
                        decoration: BoxDecoration(
                          color: Theme.of(
                            context,
                          ).colorScheme.secondary.withValues(alpha: 0.2),
                          shape: BoxShape.circle,
                        ),
                        // ),
                        child: Center(
                          child: Text(
                            '${index + 1}',
                            style: Theme.of(context).textTheme.bodySmall
                                ?.copyWith(
                                  fontWeight: FontWeight.w600,
                                  color: Theme.of(
                                    context,
                                  ).colorScheme.secondary,
                                ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          recommendation,
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: Theme.of(
                                  context,
                                ).colorScheme.onSurfaceVariant,
                                height: 1.4,
                              ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }

  double _normalizeScore(double? value, {double fallback = 0}) {
    if (value == null || value.isNaN || value.isInfinite) {
      return fallback;
    }
    return value.clamp(0.0, 100.0).toDouble();
  }

  String _feedbackText(AssessmentResult result) {
    final trimmed = result.feedback.trim();
    if (trimmed.isEmpty) {
      return 'We\'re still generating detailed insights for you. Please check back shortly.';
    }
    return trimmed;
  }

  Color _getSkillColor(String skill) {
    switch (skill.toLowerCase()) {
      case 'grammar':
        return Colors.blue;
      case 'vocabulary':
        return Colors.purple;
      case 'reading':
        return Colors.green;
      case 'listening':
        return Colors.orange;
      case 'writing':
        return Colors.red;
      case 'speaking':
        return Colors.teal;
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }

  IconData _getSkillIcon(String skill) {
    switch (skill.toLowerCase()) {
      case 'grammar':
        return Icons.spellcheck;
      case 'vocabulary':
        return Icons.translate;
      case 'reading':
        return Icons.menu_book;
      case 'listening':
        return Icons.hearing;
      case 'writing':
        return Icons.edit;
      case 'speaking':
        return Icons.record_voice_over;
      default:
        return Icons.star;
    }
  }

  String _capitalizeSkill(String skill) {
    return skill[0].toUpperCase() + skill.substring(1);
  }
}
