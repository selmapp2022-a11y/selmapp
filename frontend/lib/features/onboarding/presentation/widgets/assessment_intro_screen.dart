import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/models/onboarding_models.dart';
import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';

class AssessmentIntroScreen extends StatefulWidget {
  final AssessmentIntroState state;

  const AssessmentIntroScreen({super.key, required this.state});

  @override
  State<AssessmentIntroScreen> createState() => _AssessmentIntroScreenState();
}

class _AssessmentIntroScreenState extends State<AssessmentIntroScreen>
    with TickerProviderStateMixin {
  late AnimationController _animationController;
  late AnimationController _floatingController;
  late Animation<double> _fadeAnimation;
  late Animation<double> _slideAnimation;
  late Animation<double> _floatingAnimation;

  @override
  void initState() {
    super.initState();
    if (kDebugMode) {
      debugPrint('🎯 AssessmentIntroScreen: initState called');
    }

    _animationController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );

    _floatingController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOut),
    );

    _slideAnimation = Tween<double>(begin: 0.3, end: 0.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.elasticOut),
    );

    _floatingAnimation = Tween<double>(begin: 0.0, end: 10.0).animate(
      CurvedAnimation(parent: _floatingController, curve: Curves.easeInOut),
    );

    _animationController.forward();
    _floatingController.repeat(reverse: true);
  }

  @override
  void dispose() {
    if (kDebugMode) {
      print('🗑️ AssessmentIntroScreen: disposed - hashCode: $hashCode');
    }
    _animationController.dispose();
    _floatingController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode) {
      print('🎨 AssessmentIntroScreen: Building widget - hashCode: $hashCode');
    }
    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Level Assessment',
        showProgress: true,
        progress: 0.7, // 70% through onboarding
        onBackPressed: () {
          // Use bloc-driven back to avoid popping last route
          context.read<OnboardingBloc>().add(CancelAssessmentEvent());
        },
      ),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      children: [
                        const SizedBox(height: 20),

                        // Floating Assessment Icon
                        AnimatedBuilder(
                          animation: _floatingAnimation,
                          builder: (context, child) {
                            return Transform.translate(
                              offset: Offset(0, _floatingAnimation.value),
                              child: Container(
                                width: 120,
                                height: 120,
                                decoration: BoxDecoration(
                                  gradient: RadialGradient(
                                    colors: [
                                      Theme.of(context).colorScheme.primary
                                          .withValues(alpha: 0.2),
                                      Theme.of(context).colorScheme.primary
                                          .withValues(alpha: 0.05),
                                      Colors.transparent,
                                    ],
                                  ),
                                  shape: BoxShape.circle,
                                ),
                                child: Center(
                                  child: Container(
                                    width: 80,
                                    height: 80,
                                    decoration: BoxDecoration(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .primary
                                          .withValues(alpha: 0.1),
                                      shape: BoxShape.circle,
                                    ),
                                    child: Icon(
                                      Icons.quiz,
                                      size: 40,
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.primary,
                                    ),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),

                        const SizedBox(height: 40),

                        // Title
                        AnimatedBuilder(
                          animation: _slideAnimation,
                          builder: (context, child) {
                            return Transform.translate(
                              offset: Offset(0, _slideAnimation.value * 50),
                              child: Text(
                                'Let\'s find your level! 🎯',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineMedium
                                    ?.copyWith(
                                      fontWeight: FontWeight.bold,
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.onSurface,
                                    ),
                                textAlign: TextAlign.center,
                              ),
                            );
                          },
                        ),

                        const SizedBox(height: 16),

                        // Subtitle
                        Text(
                          'We\'ll create a personalized assessment based on your selected topics to determine your current English level.',
                          style: Theme.of(context).textTheme.bodyLarge
                              ?.copyWith(
                                color: Theme.of(
                                  context,
                                ).colorScheme.onSurfaceVariant,
                              ),
                          textAlign: TextAlign.center,
                        ),

                        const SizedBox(height: 40),

                        // Assessment Features
                        _buildFeaturesList(),

                        const SizedBox(height: 32),

                        // Selected Categories Summary
                        _buildCategoriesSummary(),

                        const SizedBox(height: 40),

                        // Assessment Info Card
                        _buildAssessmentInfoCard(),
                      ],
                    ),
                  ),
                ),

                // Action Buttons
                Column(
                  children: [
                    // Start Assessment Button
                    BlocBuilder<OnboardingBloc, OnboardingState>(
                      builder: (context, state) {
                        return AnimatedOnboardingButton(
                          text: 'Start Assessment',
                          icon: Icons.play_arrow,
                          isLoading: state is OnboardingLoadingState,
                          onPressed: () {
                            if (kDebugMode) {
                              print(
                                '🎯 AssessmentIntroScreen: Start Assessment button pressed',
                              );
                            }
                            if (kDebugMode) {
                              print(
                                '📍 AssessmentIntroScreen: Current BLoC state: ${context.read<OnboardingBloc>().state.runtimeType}',
                              );
                            }
                            context.read<OnboardingBloc>().add(
                              StartAssessmentEvent(),
                            );
                            if (kDebugMode) {
                              print(
                                '✅ AssessmentIntroScreen: StartAssessmentEvent dispatched',
                              );
                            }
                          },
                        );
                      },
                    ),

                    const SizedBox(height: 16),

                    // Skip Assessment Option
                    TextButton.icon(
                      onPressed: () {
                        // 1. Get the BLoC instance BEFORE showing the dialog
                        final onboardingBloc = context.read<OnboardingBloc>();

                        // 2. Pass it to the dialog function
                        _showSkipAssessmentDialog(context, onboardingBloc);
                      },
                      icon: Icon(
                        Icons.skip_next,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      label: Text(
                        'Skip and choose my level',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.primary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildFeaturesList() {
    final features = [
      {
        'icon': Icons.psychology,
        'title': 'AI-Powered Questions',
        'description': 'Questions tailored to your interests',
      },
      {
        'icon': Icons.timer,
        'title': '15-20 Minutes',
        'description': 'Quick and comprehensive assessment',
      },
      {
        'icon': Icons.trending_up,
        'title': 'Accurate Level Detection',
        'description': 'Determines your CEFR level (A1-C2)',
      },
      {
        'icon': Icons.insights,
        'title': 'Detailed Feedback',
        'description': 'Know your strengths and areas to improve',
      },
    ];

    return Column(
      children: features.asMap().entries.map((entry) {
        final index = entry.key;
        final feature = entry.value;

        return TweenAnimationBuilder<double>(
          duration: Duration(milliseconds: 800 + (index * 200)),
          tween: Tween<double>(begin: 0.0, end: 1.0),
          curve: Curves.elasticOut,
          builder: (context, value, child) {
            // Clamp value to ensure it stays within 0.0 to 1.0 range
            final clampedValue = value.clamp(0.0, 1.0);
            return Transform.translate(
              offset: Offset(30 * (1 - clampedValue), 0),
              child: Opacity(opacity: clampedValue, child: child),
            );
          },
          child: Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: Theme.of(
                      context,
                    ).colorScheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(
                    feature['icon'] as IconData,
                    color: Theme.of(context).colorScheme.primary,
                    size: 24,
                  ),
                ),

                const SizedBox(width: 16),

                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        feature['title'] as String,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                          color: Theme.of(context).colorScheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        feature['description'] as String,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildCategoriesSummary() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.primaryContainer.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.category,
                color: Theme.of(context).colorScheme.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Your Selected Topics',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: widget.state.selectedCategories.map((category) {
              return Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: Theme.of(
                    context,
                  ).colorScheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(category.icon, style: const TextStyle(fontSize: 16)),
                    const SizedBox(width: 6),
                    Text(
                      category.title,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildAssessmentInfoCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Theme.of(
              context,
            ).colorScheme.secondaryContainer.withValues(alpha: 0.3),
            Theme.of(
              context,
            ).colorScheme.tertiaryContainer.withValues(alpha: 0.3),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Icon(
            Icons.lightbulb,
            color: Theme.of(context).colorScheme.secondary,
            size: 32,
          ),
          const SizedBox(height: 12),
          Text(
            'Assessment Tips',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '• Answer honestly for accurate level detection\n'
            '• Take your time - there\'s no time pressure\n'
            '• Don\'t worry about difficult questions\n'
            '• You can retake the assessment anytime',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.5,
            ),
            textAlign: TextAlign.left,
          ),
        ],
      ),
    );
  }

  void _showSkipAssessmentDialog(BuildContext context, OnboardingBloc bloc) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Skip Assessment?'),
        content: SizedBox(
          width: double.maxFinite,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'You can manually select your English level instead of taking the assessment. Choose your current level:',
              ),
              const SizedBox(height: 20),
              // Wrap level options in a scrollable container with constrained height
              Flexible(
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: CEFRLevel.values.map((level) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: InkWell(
                          onTap: () {
                            Navigator.of(dialogContext).pop();
                            bloc.add(SkipAssessmentEvent(level));
                          },
                          borderRadius: BorderRadius.circular(8),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              border: Border.all(
                                color: Theme.of(
                                  dialogContext,
                                ).colorScheme.outline.withValues(alpha: 0.5),
                              ),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Row(
                              children: [
                                Container(
                                  width: 40,
                                  height: 40,
                                  decoration: BoxDecoration(
                                    color: Theme.of(dialogContext)
                                        .colorScheme
                                        .primary
                                        .withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Center(
                                    child: Text(
                                      level.code,
                                      style: Theme.of(dialogContext)
                                          .textTheme
                                          .titleSmall
                                          ?.copyWith(
                                            color: Theme.of(
                                              dialogContext,
                                            ).colorScheme.primary,
                                            fontWeight: FontWeight.bold,
                                          ),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        level.name,
                                        style: Theme.of(dialogContext)
                                            .textTheme
                                            .titleSmall
                                            ?.copyWith(
                                              fontWeight: FontWeight.w600,
                                            ),
                                      ),
                                      Text(
                                        level.description,
                                        style: Theme.of(dialogContext)
                                            .textTheme
                                            .bodySmall
                                            ?.copyWith(
                                              color: Theme.of(
                                                dialogContext,
                                              ).colorScheme.onSurfaceVariant,
                                            ),
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }
}
