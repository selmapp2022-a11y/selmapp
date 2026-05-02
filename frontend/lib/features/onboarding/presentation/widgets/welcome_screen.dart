import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lottie/lottie.dart';

import '../../../../core/widgets/gradient_text.dart';
import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen>
    with TickerProviderStateMixin {
  late AnimationController _fadeController;
  late AnimationController _slideController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();

    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _slideController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _fadeController,
        curve: const Interval(0.0, 0.8, curve: Curves.easeOut),
      ),
    );

    _slideAnimation =
        Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero).animate(
          CurvedAnimation(parent: _slideController, curve: Curves.elasticOut),
        );

    // Start animations
    _fadeController.forward();
    _slideController.forward();
  }

  @override
  void dispose() {
    _fadeController.dispose();
    _slideController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            Expanded(
              child: FadeTransition(
                opacity: _fadeAnimation,
                child: SlideTransition(
                  position: _slideAnimation,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      // Hero Animation with Lottie
                      Hero(
                        tag: 'app_logo',
                        child: Container(
                          height: 280,
                          width: 280,
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              colors: [
                                Theme.of(
                                  context,
                                ).colorScheme.primary.withValues(alpha: 0.1),
                                Colors.transparent,
                              ],
                            ),
                          ),
                          child: Lottie.asset(
                            'assets/animations/welcome_learning.json',
                            fit: BoxFit.contain,
                            repeat: true,
                          ),
                        ),
                      ),

                      const SizedBox(height: 48),

                      // App Title with Gradient
                      GradientText(
                        'Welcome to Selm',
                        style: Theme.of(context).textTheme.headlineLarge
                            ?.copyWith(
                              fontWeight: FontWeight.bold,
                              fontSize: 32,
                            ),
                        gradient: LinearGradient(
                          colors: [
                            Theme.of(context).colorScheme.primary,
                            Theme.of(context).colorScheme.secondary,
                          ],
                        ),
                      ),

                      const SizedBox(height: 16),

                      // Subtitle
                      Text(
                        'Your AI-powered English learning companion',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(
                              color: Theme.of(
                                context,
                              ).colorScheme.onSurfaceVariant,
                              fontWeight: FontWeight.w500,
                            ),
                        textAlign: TextAlign.center,
                      ),

                      const SizedBox(height: 32),

                      // Feature highlights
                      _buildFeatureList(context),
                    ],
                  ),
                ),
              ),
            ),

            // Get Started Button
            FadeTransition(
              opacity: _fadeAnimation,
              child: Column(
                children: [
                  AnimatedOnboardingButton(
                    text: 'Get Started',
                    icon: Icons.rocket_launch,
                    onPressed: () {
                      if (kDebugMode) {
                        print('🚀 WelcomeScreen: Get Started button pressed');
                      }
                      // Start onboarding process - move to category selection
                      context.read<OnboardingBloc>().add(
                        StartOnboardingEvent(),
                      );
                      if (kDebugMode) {
                        print(
                          '📤 WelcomeScreen: StartOnboardingEvent dispatched',
                        );
                      }
                      // Note: The onboarding bloc will handle state transitions
                      // No manual navigation needed - bloc manages the flow
                    },
                  ),

                  const SizedBox(height: 16),

                  // Terms and Privacy
                  Text.rich(
                    TextSpan(
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                      children: [
                        const TextSpan(
                          text: 'By continuing, you agree to our ',
                        ),
                        TextSpan(
                          text: 'Terms of Service',
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const TextSpan(text: ' and '),
                        TextSpan(
                          text: 'Privacy Policy',
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.primary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureList(BuildContext context) {
    final features = [
      {
        'icon': Icons.psychology,
        'title': 'AI Personal Trainer',
        'description': 'Get personalized lessons tailored to your needs',
      },
      {
        'icon': Icons.mic,
        'title': 'Speech Recognition',
        'description': 'Practice pronunciation with advanced AI analysis',
      },
      {
        'icon': Icons.timeline,
        'title': 'Adaptive Learning',
        'description': 'Content that evolves with your progress',
      },
    ];

    return Column(
      children: features
          .map(
            (feature) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
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
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(
                                fontWeight: FontWeight.w600,
                                color: Theme.of(context).colorScheme.onSurface,
                              ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          feature['description'] as String,
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(
                                color: Theme.of(
                                  context,
                                ).colorScheme.onSurfaceVariant,
                              ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          )
          .toList(),
    );
  }
}
