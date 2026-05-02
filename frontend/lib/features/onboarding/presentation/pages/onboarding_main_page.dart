import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:lottie/lottie.dart';

import '../../../../core/widgets/error_dialog.dart';
import '../../../../core/widgets/loading_overlay.dart';
import '../../../../core/services/auth_service.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/di/injection_container.dart' as di;
import '../../data/repositories/onboarding_repository.dart';
import '../bloc/onboarding_bloc.dart';
import '../widgets/assessment_intro_screen.dart';
import '../widgets/assessment_results_screen.dart';
import '../widgets/assessment_screen.dart';
import '../widgets/category_selection_screen.dart';
import '../widgets/learning_pace_screen.dart';
import '../widgets/learning_path_generation_screen.dart';
import '../widgets/learning_path_visualization_screen.dart';
import '../widgets/onboarding_complete_screen.dart';
import '../widgets/registration_screen.dart';
import '../widgets/welcome_screen.dart';

class OnboardingMainPage extends StatelessWidget {
  const OnboardingMainPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          OnboardingBloc(
            context.read<OnboardingRepository>(),
            di.sl<AuthService>(),
            di.sl<ApiClient>(),
          )..add(StartOnboardingEvent()),
      child: const OnboardingView(),
    );
  }
}

class OnboardingView extends StatelessWidget {
  const OnboardingView({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: BlocListener<OnboardingBloc, OnboardingState>(
        listener: (context, state) {
          if (state is OnboardingCompleteState || state is OnboardingCompletedNavigateHomeState) {
            // Navigate directly to home (Coach Center) after completing onboarding
            // This provides a seamless experience - the coach page shows the learning path
            context.go('/home');
          } else if (state is AssessmentCancelledNavigateHomeState) {
            // Navigate to home when assessment is cancelled - user can take it later
            context.go('/home');
          } else if (state is OnboardingErrorState) {
            _showErrorDialog(context, state);
          }
        },
        child: BlocBuilder<OnboardingBloc, OnboardingState>(
          builder: (context, state) {
            if (kDebugMode) {
              debugPrint('🔄 BlocBuilder: Rebuilding with state: ${state.runtimeType}');
            }
            return Stack(
              children: [
                _buildBackground(context),
                _buildContent(context, state),
                if (state is OnboardingLoadingState)
                  LoadingOverlay(
                    message: state.message,
                    progress: state.showProgress ? state.progress : null,
                    showProgress: state.showProgress,
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildBackground(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
            Theme.of(context).colorScheme.secondary.withValues(alpha: 0.1),
            Colors.white,
          ],
          stops: const [0.0, 0.3, 1.0],
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, OnboardingState state) {
    if (kDebugMode) {
      debugPrint('🎨 OnboardingView: Building content for state: ${state.runtimeType}');
    }
    return switch (state) {
      WelcomeState _ => const WelcomeScreen(),
      RegistrationState _ => const RegistrationScreen(),
      RegistrationSuccessState _ => _buildSuccessTransition(
          context,
          'Account Created! 🎉',
          'Welcome to your English learning journey',
        ),
      CategorySelectionState categoryState => CategorySelectionScreen(state: categoryState),
      LearningPaceSelectionState paceState => LearningPaceScreen(
          key: ValueKey('pace_${paceState.userId}_${paceState.hashCode}'),
          state: paceState,
        ),
      AssessmentIntroState introState => AssessmentIntroScreen(
          key: ValueKey('intro_${introState.userId}_${introState.hashCode}'),
          state: introState,
        ),
      AssessmentInProgressState assessmentState => AssessmentScreen(state: assessmentState),
      AssessmentResultsState resultsState => AssessmentResultsScreen(state: resultsState),
      LearningPathGenerationState genState => LearningPathGenerationScreen(state: genState),
      LearningPathVisualizationState vizState => LearningPathVisualizationScreen(state: vizState),
      OnboardingCompleteState completeState => OnboardingCompleteScreen(state: completeState),
      OnboardingCompletedNavigateHomeState _ => _buildLoadingScreen(context),
      _ => _buildLoadingScreen(context),
    };
  }

  Widget _buildLoadingScreen(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 24),
            Text(
              'Loading your learning journey...',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 32),
            // Add a button to go home if loading takes too long
            TextButton.icon(
              onPressed: () => context.go('/home'),
              icon: const Icon(Icons.home),
              label: const Text('Go to Home'),
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.primary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuccessTransition(
    BuildContext context,
    String title,
    String subtitle,
  ) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Success animation
          SizedBox(
            height: 200,
            width: 200,
            child: Lottie.asset(
              'assets/animations/success_checkmark.json',
              repeat: false,
              fit: BoxFit.contain,
            ),
          ),
          const SizedBox(height: 32),

          // Success title
          Text(
            title,
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.primary,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),

          // Success subtitle
          Text(
            subtitle,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 32),

          // Loading indicator
          CircularProgressIndicator(
            color: Theme.of(context).colorScheme.primary,
          ),
        ],
      ),
    );
  }

  void _showErrorDialog(BuildContext context, OnboardingErrorState state) {
    // Capture the bloc from the parent context to avoid ProviderNotFound in dialog builder
    final onboardingBloc = context.read<OnboardingBloc>();

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => ErrorDialog(
        title: 'Oops! Something went wrong',
        message: state.message,
        primaryButtonText: 'Try Again',
        onPrimaryPressed: () {
          Navigator.of(dialogContext).pop();
          onboardingBloc.add(RetryOnboardingStepEvent());
        },
        secondaryButtonText: 'Go Back',
        onSecondaryPressed: () {
          Navigator.of(dialogContext).pop();
          // Go back to previous step or welcome screen
        },
      ),
    );
  }
}

// Custom page transition animations
class SlidePageRoute<T> extends PageRouteBuilder<T> {
  final Widget child;
  final Offset direction;

  SlidePageRoute({
    required this.child,
    this.direction = const Offset(1.0, 0.0),
    super.settings,
  }) : super(
         pageBuilder: (context, animation, secondaryAnimation) => child,
         transitionDuration: const Duration(milliseconds: 500),
         reverseTransitionDuration: const Duration(milliseconds: 300),
         transitionsBuilder: (context, animation, secondaryAnimation, child) {
           var slideAnimation = Tween(begin: direction, end: Offset.zero)
               .animate(
                 CurvedAnimation(
                   parent: animation,
                   curve: Curves.easeInOutCubic,
                 ),
               );

           var fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
             CurvedAnimation(
               parent: animation,
               curve: const Interval(0.3, 1.0, curve: Curves.easeIn),
             ),
           );

           return SlideTransition(
             position: slideAnimation,
             child: FadeTransition(opacity: fadeAnimation, child: child),
           );
         },
       );
}

// Custom app bar for onboarding
class OnboardingAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final double progress;
  final VoidCallback? onBackPressed;
  final bool showProgress;

  const OnboardingAppBar({
    super.key,
    required this.title,
    this.progress = 0.0,
    this.onBackPressed,
    this.showProgress = false,
  });

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: Colors.transparent,
      elevation: 0,
      leading: onBackPressed != null
          ? IconButton(
              icon: Icon(
                Icons.arrow_back_ios,
                color: Theme.of(context).colorScheme.primary,
              ),
              onPressed: onBackPressed,
            )
          : null,
      title: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.onSurface,
        ),
      ),
      centerTitle: true,
      bottom: showProgress
          ? PreferredSize(
              preferredSize: const Size.fromHeight(4.0),
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 24),
                child: LinearProgressIndicator(
                  value: progress,
                  backgroundColor: Theme.of(
                    context,
                  ).colorScheme.outline.withValues(alpha: 0.2),
                  valueColor: AlwaysStoppedAnimation<Color>(
                    Theme.of(context).colorScheme.primary,
                  ),
                ),
              ),
            )
          : null,
    );
  }

  @override
  Size get preferredSize =>
      Size.fromHeight(kToolbarHeight + (showProgress ? 4.0 : 0.0));
}

// Onboarding step indicator
class OnboardingStepIndicator extends StatelessWidget {
  final int currentStep;
  final int totalSteps;
  final List<String> stepLabels;

  const OnboardingStepIndicator({
    super.key,
    required this.currentStep,
    required this.totalSteps,
    required this.stepLabels,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Row(
        children: List.generate(totalSteps, (index) {
          final isActive = index <= currentStep;

          return Expanded(
            child: Row(
              children: [
                Expanded(
                  child: Container(
                    height: 4,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(2),
                      color: isActive
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(
                              context,
                            ).colorScheme.outline.withValues(alpha: 0.3),
                    ),
                  ),
                ),
                if (index < totalSteps - 1) const SizedBox(width: 8),
              ],
            ),
          );
        }),
      ),
    );
  }
}

// Animated button widget
class AnimatedOnboardingButton extends StatefulWidget {
  final String text;
  final VoidCallback? onPressed;
  final bool isEnabled;
  final bool isLoading;
  final IconData? icon;

  const AnimatedOnboardingButton({
    super.key,
    required this.text,
    this.onPressed,
    this.isEnabled = true,
    this.isLoading = false,
    this.icon,
  });

  @override
  State<AnimatedOnboardingButton> createState() =>
      _AnimatedOnboardingButtonState();
}

class _AnimatedOnboardingButtonState extends State<AnimatedOnboardingButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 150),
      vsync: this,
    );
    _scaleAnimation = Tween<double>(begin: 1.0, end: 0.95).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _scaleAnimation,
      builder: (context, child) {
        return Transform.scale(
          scale: _scaleAnimation.value,
          child: SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: widget.isEnabled && !widget.isLoading
                  ? _onPressed
                  : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: Theme.of(context).colorScheme.primary,
                foregroundColor: Theme.of(context).colorScheme.onPrimary,
                elevation: widget.isEnabled ? 4 : 0,
                shadowColor: Theme.of(
                  context,
                ).colorScheme.primary.withValues(alpha: 0.3),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(28),
                ),
              ),
              child: widget.isLoading
                  ? SizedBox(
                      height: 24,
                      width: 24,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          Theme.of(context).colorScheme.onPrimary,
                        ),
                      ),
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        if (widget.icon != null) ...[
                          Icon(widget.icon),
                          const SizedBox(width: 8),
                        ],
                        Text(
                          widget.text,
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(
                                fontWeight: FontWeight.w600,
                                color: Theme.of(context).colorScheme.onPrimary,
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

  void _onPressed() {
    _animationController.forward().then((_) {
      _animationController.reverse();
    });
    widget.onPressed?.call();
  }
}
