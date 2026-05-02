import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/models/onboarding_models.dart';
import '../bloc/onboarding_bloc.dart';

class LearningPathGenerationScreen extends StatefulWidget {
  final LearningPathGenerationState state;

  const LearningPathGenerationScreen({super.key, required this.state});

  @override
  State<LearningPathGenerationScreen> createState() =>
      _LearningPathGenerationScreenState();
}

class _LearningPathGenerationScreenState
    extends State<LearningPathGenerationScreen>
    with TickerProviderStateMixin {
  late AnimationController _mainAnimationController;
  late AnimationController _rotationController;
  late AnimationController _pulseController;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;
  late Animation<double> _rotationAnimation;
  late Animation<double> _pulseAnimation;

  final List<String> _generationSteps = [
    'Analyzing your assessment results...',
    'Identifying your strengths and areas for improvement...',
    'Selecting personalized content based on your interests...',
    'Creating adaptive learning modules...',
    'Optimizing difficulty progression...',
    'Finalizing your personalized learning journey...',
  ];

  int _currentStepIndex = 0;
  Timer? _fallbackTimer;

  @override
  void initState() {
    super.initState();

    _mainAnimationController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );

    _rotationController = AnimationController(
      duration: const Duration(seconds: 3),
      vsync: this,
    );

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _mainAnimationController, curve: Curves.easeOut),
    );

    _scaleAnimation = Tween<double>(begin: 0.8, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainAnimationController,
        curve: Curves.elasticOut,
      ),
    );

    _rotationAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _rotationController, curve: Curves.linear),
    );

    _pulseAnimation = Tween<double>(begin: 0.95, end: 1.05).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    _startAnimations();
    _simulateGenerationSteps();

    // Add fallback timer - if generation takes too long, force completion
    _fallbackTimer = Timer(const Duration(seconds: 15), () {
      if (mounted) {
        _forceCompleteGeneration();
      }
    });
  }

  void _startAnimations() {
    _mainAnimationController.forward();
    _rotationController.repeat();
    _pulseController.repeat(reverse: true);
  }

  void _simulateGenerationSteps() {
    // Simulate the step-by-step generation process
    for (int i = 0; i < _generationSteps.length; i++) {
      Future.delayed(Duration(seconds: 2 + i * 2), () {
        if (mounted) {
          setState(() {
            _currentStepIndex = i;
          });
        }
      });
    }
  }

  void _forceCompleteGeneration() {
    // If generation is taking too long, dispatch the event again or use fallback
    if (kDebugMode) {
      print('⏰ Learning path generation timeout - forcing completion');
    }
    context.read<OnboardingBloc>().add(GenerateLearningPathEvent());
  }

  @override
  void dispose() {
    _mainAnimationController.dispose();
    _rotationController.dispose();
    _pulseController.dispose();
    _fallbackTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final userProfile = widget.state.userProfile;

    return BlocListener<OnboardingBloc, OnboardingState>(
      listener: (context, state) {
        if (state is LearningPathVisualizationState) {
          // Generation completed successfully
          _fallbackTimer?.cancel();
          if (kDebugMode) {
            print('✅ Learning path generation completed successfully');
          }
        } else if (state is OnboardingErrorState) {
          // Generation failed
          _fallbackTimer?.cancel();
          if (kDebugMode) {
            print('❌ Learning path generation failed: ${state.message}');
          }
        }
      },
      child: Scaffold(
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Theme.of(context).colorScheme.primary.withValues(alpha: 0.05),
                Theme.of(context).colorScheme.secondary.withValues(alpha: 0.05),
                Colors.white,
              ],
              stops: const [0.0, 0.3, 1.0],
            ),
          ),
          child: SafeArea(
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  children: [
                    // Header
                    _buildHeader(),

                    const Spacer(flex: 2),

                    // AI Generation Animation
                    ScaleTransition(
                      scale: _scaleAnimation,
                      child: _buildGenerationAnimation(),
                    ),

                    const SizedBox(height: 32),

                    // Current Step Text
                    _buildCurrentStepText(),

                    const Spacer(flex: 2),

                    // User Profile Summary
                    _buildUserProfileSummary(userProfile),

                    const Spacer(flex: 1),

                    // Progress Indicator
                    _buildProgressIndicator(),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        Text(
          'Creating Your Learning Path',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.primary,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          'Our AI is crafting a personalized learning journey just for you',
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  Widget _buildGenerationAnimation() {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Outer rotating ring
        AnimatedBuilder(
          animation: _rotationAnimation,
          builder: (context, child) {
            return Transform.rotate(
              angle: _rotationAnimation.value * 2 * 3.14159,
              child: Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: Theme.of(
                      context,
                    ).colorScheme.primary.withValues(alpha: 0.3),
                    width: 2,
                  ),
                ),
                child: Stack(
                  children: [
                    // Animated dots around the ring
                    for (int i = 0; i < 8; i++)
                      Positioned(
                        top: 95 + 85 * math.cos((i * 45) * math.pi / 180),
                        left: 95 + 85 * math.sin((i * 45) * math.pi / 180),
                        child: AnimatedBuilder(
                          animation: _pulseController,
                          builder: (context, child) {
                            return Transform.scale(
                              scale: _pulseAnimation.value,
                              child: Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: Theme.of(context).colorScheme.primary,
                                  shape: BoxShape.circle,
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                  ],
                ),
              ),
            );
          },
        ),

        // Center AI brain icon
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
          child: AnimatedBuilder(
            animation: _pulseController,
            builder: (context, child) {
              return Transform.scale(
                scale: _pulseAnimation.value,
                child: Icon(
                  Icons.psychology,
                  size: 60,
                  color: Theme.of(context).colorScheme.onPrimary,
                ),
              );
            },
          ),
        ),

        // Floating particles
        for (int i = 0; i < 6; i++) _buildFloatingParticle(i),
      ],
    );
  }

  Widget _buildFloatingParticle(int index) {
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 2000 + (index * 300)),
      tween: Tween<double>(begin: 0.0, end: 1.0),
      curve: Curves.easeInOut,
      builder: (context, value, child) {
        final angle = (index * 60) * math.pi / 180;
        final radius = 150 + (30 * math.sin(value * 2 * math.pi));

        return Positioned(
          top: 100 + radius * math.cos(angle + value * 2 * math.pi),
          left: 100 + radius * math.sin(angle + value * 2 * math.pi),
          child: Opacity(
            opacity: (0.3 + (0.4 * math.sin(value * 4 * math.pi))).clamp(
              0.0,
              1.0,
            ),
            child: Container(
              width: 4,
              height: 4,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.tertiary,
                shape: BoxShape.circle,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildCurrentStepText() {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 500),
      child: Container(
        key: ValueKey(_currentStepIndex),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(
                  Theme.of(context).colorScheme.primary,
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                _currentStepIndex < _generationSteps.length
                    ? _generationSteps[_currentStepIndex]
                    : 'Almost ready...',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUserProfileSummary(UserProfile userProfile) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
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
                Icons.person,
                color: Theme.of(context).colorScheme.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Your Learning Profile',
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Current Level
          _buildProfileItem(
            Icons.school,
            'Current Level',
            userProfile.currentLevel.name,
            Theme.of(context).colorScheme.primary,
          ),

          const SizedBox(height: 12),

          // Learning Pace
          _buildProfileItem(
            Icons.speed,
            'Learning Pace',
            userProfile.learningPace.name,
            Theme.of(context).colorScheme.secondary,
          ),

          const SizedBox(height: 12),

          // Interests
          _buildProfileItem(
            Icons.favorite,
            'Focus Areas',
            userProfile.preferredCategories.map((c) => c.name).join(', '),
            Theme.of(context).colorScheme.tertiary,
          ),
        ],
      ),
    );
  }

  Widget _buildProfileItem(
    IconData icon,
    String label,
    String value,
    Color color,
  ) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: color),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              Text(
                value,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildProgressIndicator() {
    return Column(
      children: [
        Text(
          'This may take a few moments...',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 16),
        LinearProgressIndicator(
          backgroundColor: Theme.of(
            context,
          ).colorScheme.outline.withValues(alpha: 0.2),
          valueColor: AlwaysStoppedAnimation<Color>(
            Theme.of(context).colorScheme.primary,
          ),
        ),
      ],
    );
  }
}
