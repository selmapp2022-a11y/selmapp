import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lottie/lottie.dart';

import '../../data/models/onboarding_models.dart';
import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';

class LearningPaceScreen extends StatefulWidget {
  final LearningPaceSelectionState state;

  const LearningPaceScreen({super.key, required this.state});

  @override
  State<LearningPaceScreen> createState() => _LearningPaceScreenState();
}

class _LearningPaceScreenState extends State<LearningPaceScreen>
    with TickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late List<AnimationController> _cardAnimationControllers;

  LearningPace? _selectedPace;

  bool _hasUserInteracted = false;

  @override
  void initState() {
    super.initState();
    if (kDebugMode) {
      print('🎯 LearningPaceScreen: initState called - hashCode: $hashCode');
      print('📊 LearningPaceScreen: UserId: ${widget.state.userId}');
      print(
        '📋 LearningPaceScreen: Categories: ${widget.state.selectedCategories}',
      );
      print(
        '🏃 LearningPaceScreen: Initial pace: ${widget.state.selectedPace}',
      );
      print(
        '🔄 LearningPaceScreen: Widget state hashCode: ${widget.state.hashCode}',
      );
    }

    _selectedPace = widget.state.selectedPace;
    _hasUserInteracted = widget.state.selectedPace != null;

    // Don't pre-select any pace - user must explicitly choose
    // This ensures the user understands they need to make a selection

    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOut),
    );

    // Animation controllers for each pace card
    _cardAnimationControllers = LearningPace.values.map((pace) {
      return AnimationController(
        duration: const Duration(milliseconds: 200),
        vsync: this,
      );
    }).toList();

    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    for (var controller in _cardAnimationControllers) {
      controller.dispose();
    }
    if (kDebugMode) {
      print('🗑️ LearningPaceScreen: disposed - hashCode: $hashCode');
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode) {
      print('🎨 LearningPaceScreen: Building widget - hashCode: $hashCode');
    }
    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Learning Pace',
        showProgress: true,
        progress: 0.5, // 50% through onboarding
        onBackPressed: () => Navigator.of(context).pop(),
      ),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: Column(
            children: [
              // Header Section
              Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    // Animation
                    SizedBox(
                      height: 120,
                      child: Lottie.asset(
                        'assets/animations/clock_time.json',
                        fit: BoxFit.contain,
                      ),
                    ),

                    const SizedBox(height: 24),

                    // Title
                    Text(
                      'How much time do you have? ⏰',
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                      textAlign: TextAlign.center,
                    ),

                    const SizedBox(height: 16),

                    // Subtitle
                    Text(
                      'Choose your preferred daily study time. You can always adjust this later in settings.',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),

              // Hint text when no selection made
              if (!_hasUserInteracted && _selectedPace == null)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 12,
                    ),
                    decoration: BoxDecoration(
                      color: Theme.of(
                        context,
                      ).colorScheme.primaryContainer.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: Theme.of(
                          context,
                        ).colorScheme.primary.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.touch_app,
                          color: Theme.of(context).colorScheme.primary,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Tap on a pace option below to select it',
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(
                                  color: Theme.of(context).colorScheme.primary,
                                  fontWeight: FontWeight.w500,
                                ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              if (!_hasUserInteracted && _selectedPace == null)
                const SizedBox(height: 16),

              // Learning Pace Options - Responsive for web
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final screenWidth = constraints.maxWidth;
                    final isWideScreen = screenWidth >= 600;
                    final maxContentWidth = isWideScreen
                        ? 600.0
                        : double.infinity;

                    return SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: BoxConstraints(
                            maxWidth: maxContentWidth,
                          ),
                          child: Column(
                            children: List.generate(LearningPace.values.length, (
                              index,
                            ) {
                              final pace = LearningPace.values[index];
                              final isSelected = _selectedPace == pace;

                              return TweenAnimationBuilder<double>(
                                duration: Duration(
                                  milliseconds: 600 + (index * 200),
                                ),
                                tween: Tween<double>(begin: 0.0, end: 1.0),
                                curve: Curves.elasticOut,
                                builder: (context, value, child) {
                                  // Clamp value to ensure it stays within 0.0 to 1.0 range
                                  final clampedValue = value.clamp(0.0, 1.0);
                                  return Transform.translate(
                                    offset: Offset(50 * (1 - clampedValue), 0),
                                    child: Opacity(
                                      opacity: clampedValue,
                                      child: child,
                                    ),
                                  );
                                },
                                child: Padding(
                                  padding: const EdgeInsets.only(bottom: 16),
                                  child: _buildPaceCard(
                                    pace,
                                    isSelected,
                                    index,
                                  ),
                                ),
                              );
                            }),
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),

              // Continue Button
              Padding(
                padding: const EdgeInsets.all(24),
                child: AnimatedOnboardingButton(
                  text: _selectedPace != null
                      ? 'Continue to Assessment'
                      : 'Choose Your Pace',
                  icon: _selectedPace != null ? Icons.quiz : Icons.schedule,
                  isEnabled: _selectedPace != null,
                  onPressed: _selectedPace != null
                      ? _continueToAssessment
                      : null,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPaceCard(LearningPace pace, bool isSelected, int index) {
    return AnimatedBuilder(
      animation: _cardAnimationControllers[index],
      builder: (context, child) {
        return Transform.scale(
          scale: 1.0 - (_cardAnimationControllers[index].value * 0.05),
          child: GestureDetector(
            onTap: () => _selectPace(pace, index),
            onTapDown: (_) => _cardAnimationControllers[index].forward(),
            onTapUp: (_) => _cardAnimationControllers[index].reverse(),
            onTapCancel: () => _cardAnimationControllers[index].reverse(),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeInOutCubic,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isSelected
                      ? Theme.of(context).colorScheme.primary
                      : Theme.of(
                          context,
                        ).colorScheme.outline.withValues(alpha: 0.3),
                  width: isSelected ? 2 : 1,
                ),
                gradient: isSelected
                    ? LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          Theme.of(
                            context,
                          ).colorScheme.primary.withValues(alpha: 0.1),
                          Theme.of(
                            context,
                          ).colorScheme.primary.withValues(alpha: 0.05),
                        ],
                      )
                    : null,
                color: isSelected
                    ? null
                    : Theme.of(context).colorScheme.surface,
                boxShadow: [
                  BoxShadow(
                    color: isSelected
                        ? Theme.of(
                            context,
                          ).colorScheme.primary.withValues(alpha: 0.2)
                        : Theme.of(
                            context,
                          ).colorScheme.shadow.withValues(alpha: 0.1),
                    blurRadius: isSelected ? 8 : 4,
                    offset: Offset(0, isSelected ? 4 : 2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  // Pace Icon
                  Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      color: isSelected
                          ? Theme.of(
                              context,
                            ).colorScheme.primary.withValues(alpha: 0.2)
                          : Theme.of(context).colorScheme.primaryContainer
                                .withValues(alpha: 0.3),
                      borderRadius: BorderRadius.circular(30),
                    ),
                    child: Center(
                      child: Text(
                        pace.icon,
                        style: const TextStyle(fontSize: 24),
                      ),
                    ),
                  ),

                  const SizedBox(width: 16),

                  // Pace Details
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              pace.title,
                              style: Theme.of(context).textTheme.titleLarge
                                  ?.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: isSelected
                                        ? Theme.of(context).colorScheme.primary
                                        : Theme.of(
                                            context,
                                          ).colorScheme.onSurface,
                                  ),
                            ),
                            const Spacer(),
                            if (isSelected)
                              AnimatedScale(
                                scale: 1.0,
                                duration: const Duration(milliseconds: 200),
                                child: Container(
                                  width: 24,
                                  height: 24,
                                  decoration: BoxDecoration(
                                    color: Theme.of(
                                      context,
                                    ).colorScheme.primary,
                                    shape: BoxShape.circle,
                                  ),
                                  child: Icon(
                                    Icons.check,
                                    size: 16,
                                    color: Theme.of(
                                      context,
                                    ).colorScheme.onPrimary,
                                  ),
                                ),
                              ),
                          ],
                        ),

                        const SizedBox(height: 4),

                        Text(
                          pace.duration,
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(
                                color: isSelected
                                    ? Theme.of(context).colorScheme.primary
                                          .withValues(alpha: 0.8)
                                    : Theme.of(context).colorScheme.primary,
                                fontWeight: FontWeight.w500,
                              ),
                        ),

                        const SizedBox(height: 8),

                        Text(
                          pace.description,
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: Theme.of(
                                  context,
                                ).colorScheme.onSurfaceVariant,
                                height: 1.3,
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
      },
    );
  }

  void _selectPace(LearningPace pace, int index) {
    if (kDebugMode) {
      print('🎯 LearningPaceScreen: _selectPace called with pace: $pace');
    }
    setState(() {
      _selectedPace = pace;
      _hasUserInteracted = true;
    });
    if (kDebugMode) {
      print('✅ LearningPaceScreen: _selectedPace updated to: $_selectedPace');
    }

    // Haptic feedback
    // HapticFeedback.lightImpact();

    // Update the bloc
    if (kDebugMode) {
      print(
        '📤 LearningPaceScreen: Dispatching SelectLearningPaceEvent with pace: $pace',
      );
    }
    context.read<OnboardingBloc>().add(SelectLearningPaceEvent(pace));
    if (kDebugMode) {
      print('✅ LearningPaceScreen: SelectLearningPaceEvent dispatched');
    }
  }

  void _continueToAssessment() {
    // Dispatch StartAssessmentEvent to move to assessment intro
    if (kDebugMode) {
      print('🎯 LearningPaceScreen: Dispatching StartAssessmentEvent');
      print('📍 LearningPaceScreen: Current selected pace: $_selectedPace');
      print('🔍 LearningPaceScreen: Button enabled: ${_selectedPace != null}');
      print('🔄 LearningPaceScreen: Widget hashCode: $hashCode');
    }

    if (_selectedPace != null) {
      // Always dispatch - let BLoC handle state validation
      final currentState = context.read<OnboardingBloc>().state;
      if (kDebugMode) {
        print(
          '📊 LearningPaceScreen: Current BLoC state: ${currentState.runtimeType}',
        );
      }

      context.read<OnboardingBloc>().add(StartAssessmentEvent());
      if (kDebugMode) {
        print('✅ LearningPaceScreen: StartAssessmentEvent dispatched');
      }
    } else {
      if (kDebugMode) {
        print('❌ LearningPaceScreen: No pace selected, not dispatching event');
      }
    }
  }
}

// Reusable Progress Indicator Widget
class LearningPathProgressIndicator extends StatelessWidget {
  final double progress;
  final Color? color;

  const LearningPathProgressIndicator({
    super.key,
    required this.progress,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 4,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(2),
        color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
      ),
      child: FractionallySizedBox(
        alignment: Alignment.centerLeft,
        widthFactor: progress.clamp(0.0, 1.0),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(2),
            color: color ?? Theme.of(context).colorScheme.primary,
          ),
        ),
      ),
    );
  }
}

// Learning Pace Statistics Widget
class LearningPaceStats extends StatelessWidget {
  final LearningPace pace;

  const LearningPaceStats({super.key, required this.pace});

  @override
  Widget build(BuildContext context) {
    final stats = _getStatsForPace(pace);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Expected Progress:',
            style: Theme.of(
              context,
            ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          ...stats.entries.map(
            (stat) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(stat.key, style: Theme.of(context).textTheme.bodyMedium),
                  Text(
                    stat.value,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Map<String, String> _getStatsForPace(LearningPace pace) {
    switch (pace) {
      case LearningPace.relaxed:
        return {
          'Weekly Sessions': '5-6 sessions',
          'Level Up Time': '3-4 months',
          'Skills Focus': 'Vocabulary & Reading',
        };
      case LearningPace.steady:
        return {
          'Weekly Sessions': '7 sessions',
          'Level Up Time': '2-3 months',
          'Skills Focus': 'All skills balanced',
        };
      case LearningPace.intensive:
        return {
          'Weekly Sessions': '7 sessions',
          'Level Up Time': '1-2 months',
          'Skills Focus': 'Speaking & Writing',
        };
    }
  }
}
