import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../data/models/onboarding_models.dart';
import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';

class OnboardingCompleteScreen extends StatefulWidget {
  final OnboardingCompleteState state;

  const OnboardingCompleteScreen({super.key, required this.state});

  @override
  State<OnboardingCompleteScreen> createState() =>
      _OnboardingCompleteScreenState();
}

class _OnboardingCompleteScreenState extends State<OnboardingCompleteScreen>
    with TickerProviderStateMixin {
  late AnimationController _mainAnimationController;
  late AnimationController _celebrationController;
  late AnimationController _confettiController;
  late Animation<double> _fadeAnimation;
  late Animation<double> _scaleAnimation;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();

    _mainAnimationController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _celebrationController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    _confettiController = AnimationController(
      duration: const Duration(milliseconds: 3000),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainAnimationController,
        curve: const Interval(0.0, 0.6, curve: Curves.easeOut),
      ),
    );

    _scaleAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainAnimationController,
        curve: const Interval(0.2, 0.8, curve: Curves.elasticOut),
      ),
    );

    _slideAnimation =
        Tween<Offset>(begin: const Offset(0, 0.5), end: Offset.zero).animate(
          CurvedAnimation(
            parent: _mainAnimationController,
            curve: const Interval(0.4, 1.0, curve: Curves.elasticOut),
          ),
        );

    _startAnimations();
  }

  void _startAnimations() {
    _mainAnimationController.forward();
    _celebrationController.forward();
    _confettiController.forward();
  }

  @override
  void dispose() {
    _mainAnimationController.dispose();
    _celebrationController.dispose();
    _confettiController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final userProfile = widget.state.userProfile;
    final learningPath = widget.state.learningPath;

    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
              Theme.of(context).colorScheme.secondary.withValues(alpha: 0.1),
              Colors.white,
            ],
            stops: const [0.0, 0.4, 1.0],
          ),
        ),
        child: SafeArea(
          child: FadeTransition(
            opacity: _fadeAnimation,
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                children: [
                  const Spacer(flex: 1),

                  // Celebration Animation
                  ScaleTransition(
                    scale: _scaleAnimation,
                    child: _buildCelebrationSection(),
                  ),

                  const SizedBox(height: 32),

                  // Welcome Message
                  SlideTransition(
                    position: _slideAnimation,
                    child: _buildWelcomeMessage(userProfile),
                  ),

                  const SizedBox(height: 32),

                  // Learning Path Summary
                  _buildLearningPathSummary(learningPath),

                  const Spacer(flex: 2),

                  // Action Buttons
                  _buildActionButtons(),

                  const SizedBox(height: 16),

                  // Skip Option
                  _buildSkipOption(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCelebrationSection() {
    return Column(
      children: [
        // Success Animation
        Stack(
          alignment: Alignment.center,
          children: [
            // Confetti background
            SizedBox(
              height: 200,
              width: 200,
              child: AnimatedBuilder(
                animation: _confettiController,
                builder: (context, child) {
                  return CustomPaint(
                    painter: ConfettiPainter(_confettiController.value),
                    size: const Size(200, 200),
                  );
                },
              ),
            ),

            // Main celebration icon
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
                    blurRadius: 30,
                    offset: const Offset(0, 15),
                  ),
                ],
              ),
              child: Icon(
                Icons.celebration,
                size: 60,
                color: Theme.of(context).colorScheme.onPrimary,
              ),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // Success Title
        Text(
          'Welcome to Selm! 🎉',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: Theme.of(context).colorScheme.primary,
          ),
          textAlign: TextAlign.center,
        ),

        const SizedBox(height: 8),

        Text(
          'Your personalized learning journey is ready!',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  Widget _buildWelcomeMessage(UserProfile userProfile) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        children: [
          Icon(
            Icons.person_pin,
            size: 48,
            color: Theme.of(context).colorScheme.primary,
          ),

          const SizedBox(height: 16),

          Text(
            'Hello, ${userProfile.name}!',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),

          const SizedBox(height: 8),

          Text(
            'We\'ve created a learning path tailored specifically for your ${userProfile.currentLevel.name} level and ${userProfile.learningPace.name.toLowerCase()} pace.',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.5,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildLearningPathSummary(LearningPath learningPath) {
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
                Icons.route,
                color: Theme.of(context).colorScheme.secondary,
                size: 24,
              ),
              const SizedBox(width: 12),
              Text(
                'Your Learning Journey',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: Theme.of(context).colorScheme.secondary,
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Learning Path Stats
          Row(
            children: [
              Expanded(
                child: _buildPathStat(
                  Icons.school,
                  'Current Level',
                  learningPath.currentLevel.name,
                  Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildPathStat(
                  Icons.flag,
                  'Target Level',
                  learningPath.targetLevel.name,
                  Theme.of(context).colorScheme.tertiary,
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          Row(
            children: [
              Expanded(
                child: _buildPathStat(
                  Icons.library_books,
                  'Learning Modules',
                  '${learningPath.modules.length}',
                  Theme.of(context).colorScheme.secondary,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildPathStat(
                  Icons.category,
                  'Focus Areas',
                  '${learningPath.categories.length}',
                  Colors.orange,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPathStat(
    IconData icon,
    String label,
    String value,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons() {
    return Column(
      children: [
        // Primary Action - Start Learning
        AnimatedOnboardingButton(
          text: 'Start My Learning Journey',
          icon: Icons.rocket_launch,
          onPressed: () async {
            // Dispatch the complete event first
            context.read<OnboardingBloc>().add(CompleteOnboardingEvent());
            
            // Small delay to ensure event is processed
            await Future.delayed(const Duration(milliseconds: 100));
            
            // Navigate directly to home - use pushReplacement to clear stack
            if (mounted) {
              context.go('/home');
            }
          },
        ),

        const SizedBox(height: 12),

        // Secondary Action - View Learning Path
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: () {
              _showLearningPathDetails();
            },
            icon: Icon(
              Icons.visibility,
              color: Theme.of(context).colorScheme.primary,
            ),
            label: Text(
              'Preview My Learning Path',
              style: TextStyle(
                color: Theme.of(context).colorScheme.primary,
                fontWeight: FontWeight.w600,
              ),
            ),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 16),
              side: BorderSide(color: Theme.of(context).colorScheme.primary),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSkipOption() {
    return TextButton(
      onPressed: () async {
        // Dispatch the complete event first
        context.read<OnboardingBloc>().add(CompleteOnboardingEvent());
        
        // Small delay to ensure event is processed
        await Future.delayed(const Duration(milliseconds: 100));
        
        // Navigate directly to home
        if (mounted) {
          context.go('/home');
        }
      },
      child: Text(
        'I\'ll explore later',
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }

  void _showLearningPathDetails() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.9,
        minChildSize: 0.5,
        builder: (context, scrollController) => Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: Column(
            children: [
              // Handle
              Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: Theme.of(
                    context,
                  ).colorScheme.outline.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),

              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Row(
                  children: [
                    Text(
                      'Your Learning Path',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
              ),

              // Content
              Expanded(
                child: ListView.builder(
                  controller: scrollController,
                  padding: const EdgeInsets.all(24),
                  itemCount: widget.state.learningPath.modules.length,
                  itemBuilder: (context, index) {
                    final module = widget.state.learningPath.modules[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 16),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: Theme.of(
                            context,
                          ).colorScheme.primaryContainer,
                          child: Text('${index + 1}'),
                        ),
                        title: Text(
                          module.title,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        subtitle: Text(module.description),
                        trailing: Icon(
                          Icons.arrow_forward_ios,
                          size: 16,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Custom painter for confetti effect
class ConfettiPainter extends CustomPainter {
  final double progress;

  ConfettiPainter(this.progress);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..style = PaintingStyle.fill;

    final colors = [
      Colors.red,
      Colors.blue,
      Colors.green,
      Colors.yellow,
      Colors.purple,
      Colors.orange,
    ];

    for (int i = 0; i < 20; i++) {
      final colorIndex = i % colors.length;
      paint.color = colors[colorIndex];

      final x =
          (size.width * (i * 0.1 + 0.1)) +
          (20 * math.sin(progress * 2 * math.pi + i));
      final y = size.height * progress + (i * 10);

      if (y < size.height) {
        canvas.drawCircle(Offset(x, y), 3, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
