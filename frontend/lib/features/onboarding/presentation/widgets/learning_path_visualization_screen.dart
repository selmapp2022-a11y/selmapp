import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lottie/lottie.dart';

import '../../data/models/onboarding_models.dart';
import '../../data/repositories/onboarding_repository.dart';
import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';
import 'lesson_loading_screen.dart';

class LearningPathVisualizationScreen extends StatefulWidget {
  final LearningPathVisualizationState state;

  const LearningPathVisualizationScreen({super.key, required this.state});

  @override
  State<LearningPathVisualizationScreen> createState() =>
      _LearningPathVisualizationScreenState();
}

class _LearningPathVisualizationScreenState
    extends State<LearningPathVisualizationScreen>
    with TickerProviderStateMixin {
  LearningPath? _learningPath;
  late AnimationController _mainAnimationController;
  late Animation<double> _fadeAnimation;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _learningPath = widget.state.learningPath;

    _mainAnimationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _mainAnimationController, curve: Curves.easeOut),
    );

    _mainAnimationController.forward();

    // Load persisted learning path
    _loadPersistedLearningPath();
  }

  Future<void> _loadPersistedLearningPath() async {
    try {
      final repo = context.read<OnboardingRepository>();
      final persistedPath = await repo.loadLearningPath();
      if (persistedPath != null && mounted) {
        setState(() => _learningPath = persistedPath);
      }
    } catch (e) {
      // Use the state path if loading fails
      debugPrint('Failed to load persisted learning path: $e');
    }
  }

  @override
  void dispose() {
    _mainAnimationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final learningPath = _learningPath ?? widget.state.learningPath;
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: OnboardingAppBar(
        title: 'Your Learning Path',
        showProgress: true,
        progress: 1.0,
      ),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      const SizedBox(height: 16),

                      // Success Header Card
                      _buildSuccessHeader(theme, colorScheme),

                      const SizedBox(height: 24),

                      // Quick Stats Row
                      _buildQuickStats(learningPath, theme, colorScheme),

                      const SizedBox(height: 24),

                      // Learning Path Overview
                      if (learningPath.modules.isEmpty)
                        _buildEmptyModulesState(theme, colorScheme)
                      else
                        _buildModulesSection(learningPath, theme, colorScheme),

                      const SizedBox(height: 24),

                      // Tips Card
                      _buildTipsCard(theme, colorScheme),

                      const SizedBox(height: 100), // Space for bottom button
                    ],
                  ),
                ),
              ),

              // Bottom Action Button
              _buildBottomAction(theme, colorScheme),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSuccessHeader(ThemeData theme, ColorScheme colorScheme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            colorScheme.primaryContainer,
            colorScheme.secondaryContainer,
          ],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: colorScheme.primary.withValues(alpha: 0.2),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        children: [
          // Celebration Animation
          SizedBox(
            height: 100,
            width: 100,
            child: Lottie.asset(
              'assets/animations/celebration.json',
              repeat: true,
              fit: BoxFit.contain,
              errorBuilder: (context, error, stackTrace) {
                // Fallback if animation fails to load
                return Container(
                  decoration: BoxDecoration(
                    color: colorScheme.primary.withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.celebration,
                    size: 48,
                    color: colorScheme.primary,
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: 16),

          Text(
            'Your Learning Path is Ready! 🎉',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: colorScheme.onPrimaryContainer,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 12),

          Text(
            'We\'ve created a personalized journey based on your goals. Let\'s start learning!',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colorScheme.onPrimaryContainer.withValues(alpha: 0.8),
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildQuickStats(
    LearningPath learningPath,
    ThemeData theme,
    ColorScheme colorScheme,
  ) {
    final totalMinutes = learningPath.modules.fold<int>(
      0,
      (sum, module) => sum + module.estimatedMinutes,
    );
    final totalHours = (totalMinutes / 60).ceil();

    return Row(
      children: [
        Expanded(
          child: _buildStatCard(
            icon: Icons.school_outlined,
            value: '${learningPath.modules.length}',
            label: 'Modules',
            color: colorScheme.primary,
            theme: theme,
            colorScheme: colorScheme,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard(
            icon: Icons.timer_outlined,
            value: '${totalHours}h',
            label: 'Total Time',
            color: colorScheme.secondary,
            theme: theme,
            colorScheme: colorScheme,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildStatCard(
            icon: Icons.trending_up,
            value: learningPath.targetLevel.code,
            label: 'Target',
            color: colorScheme.tertiary,
            theme: theme,
            colorScheme: colorScheme,
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard({
    required IconData icon,
    required String value,
    required String label,
    required Color color,
    required ThemeData theme,
    required ColorScheme colorScheme,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyModulesState(ThemeData theme, ColorScheme colorScheme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: colorScheme.outline.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(
            Icons.hourglass_empty,
            size: 48,
            color: colorScheme.primary.withValues(alpha: 0.6),
          ),
          const SizedBox(height: 16),
          Text(
            'Finalizing Your Modules',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'We\'re preparing your personalized learning content. This might take a moment.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: () {
              context.read<OnboardingBloc>().add(GenerateLearningPathEvent());
            },
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModulesSection(
    LearningPath learningPath,
    ThemeData theme,
    ColorScheme colorScheme,
  ) {
    final modules = learningPath.modules;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.route, color: colorScheme.primary, size: 20),
            const SizedBox(width: 8),
            Text(
              'Your Learning Journey',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),

        // Module List
        ...modules.asMap().entries.map((entry) {
          final index = entry.key;
          final module = entry.value;
          final isFirst = index == 0;
          final isLast = index == modules.length - 1;

          return TweenAnimationBuilder<double>(
            duration: Duration(milliseconds: 400 + (index * 100)),
            tween: Tween<double>(begin: 0.0, end: 1.0),
            curve: Curves.easeOut,
            builder: (context, value, child) {
              return Opacity(
                opacity: value.clamp(0.0, 1.0),
                child: Transform.translate(
                  offset: Offset(0, 20 * (1 - value.clamp(0.0, 1.0))),
                  child: child,
                ),
              );
            },
            child: _buildModuleCard(
              module: module,
              index: index,
              isFirst: isFirst,
              isLast: isLast,
              theme: theme,
              colorScheme: colorScheme,
            ),
          );
        }),
      ],
    );
  }

  Widget _buildModuleCard({
    required LearningModule module,
    required int index,
    required bool isFirst,
    required bool isLast,
    required ThemeData theme,
    required ColorScheme colorScheme,
  }) {
    final isUnlocked = module.isUnlocked || isFirst;
    final categoryColor = _getCategoryColor(module.category);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timeline indicator
          Column(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: isUnlocked
                      ? categoryColor
                      : colorScheme.surfaceContainerHighest,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isUnlocked
                        ? categoryColor
                        : colorScheme.outline.withValues(alpha: 0.3),
                    width: 2,
                  ),
                ),
                child: Center(
                  child: isUnlocked
                      ? Text(
                          '${index + 1}',
                          style: theme.textTheme.titleSmall?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                          ),
                        )
                      : Icon(
                          Icons.lock,
                          size: 18,
                          color: colorScheme.onSurfaceVariant,
                        ),
                ),
              ),
              if (!isLast)
                Container(
                  width: 2,
                  height: 60,
                  color: isUnlocked
                      ? categoryColor.withValues(alpha: 0.3)
                      : colorScheme.outline.withValues(alpha: 0.2),
                ),
            ],
          ),

          const SizedBox(width: 16),

          // Module content
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: isUnlocked
                    ? colorScheme.surface
                    : colorScheme.surfaceContainerHighest.withValues(
                        alpha: 0.5,
                      ),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: isUnlocked
                      ? categoryColor.withValues(alpha: 0.3)
                      : colorScheme.outline.withValues(alpha: 0.2),
                ),
                boxShadow: isUnlocked
                    ? [
                        BoxShadow(
                          color: categoryColor.withValues(alpha: 0.1),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ]
                    : null,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header row
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              module.title,
                              style: theme.textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w600,
                                color: isUnlocked
                                    ? colorScheme.onSurface
                                    : colorScheme.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              module.description,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: colorScheme.onSurfaceVariant,
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: categoryColor.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          '${module.estimatedMinutes} min',
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: categoryColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),

                  // Progress bar for unlocked modules
                  if (isUnlocked && module.progressPercentage > 0) ...[
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(4),
                            child: LinearProgressIndicator(
                              value: module.progressPercentage / 100,
                              backgroundColor:
                                  colorScheme.surfaceContainerHighest,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                categoryColor,
                              ),
                              minHeight: 6,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${module.progressPercentage.toInt()}%',
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: categoryColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ],

                  // Action button for unlocked modules
                  if (isUnlocked) ...[
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _isLoading
                            ? null
                            : () => _startLesson(module),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: categoryColor,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              module.progressPercentage > 0
                                  ? Icons.play_arrow
                                  : Icons.play_circle_outline,
                              size: 18,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              module.progressPercentage > 0
                                  ? 'Continue'
                                  : 'Start',
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _startLesson(LearningModule module) async {
    setState(() => _isLoading = true);
    try {
      final repo = context.read<OnboardingRepository>();
      final result = await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) =>
              LessonLoadingScreen(moduleId: module.id, dayNumber: 1),
        ),
      );

      if (!mounted) return;

      if (result is Map) {
        final progress =
            (result['updated_progress_percentage'] as num?)?.toDouble() ?? 0.0;
        final unlocked = result['unlocked_next_module'] == true;

        await repo.updateModuleProgress(module.id, progress, unlocked);
        await _loadPersistedLearningPath();

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                unlocked
                    ? 'Lesson completed! Next module unlocked. 🎉'
                    : 'Great progress! Keep it up! 💪',
              ),
              behavior: SnackBarBehavior.floating,
              backgroundColor: Theme.of(context).colorScheme.primary,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to start lesson: $e'),
            behavior: SnackBarBehavior.floating,
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Widget _buildTipsCard(ThemeData theme, ColorScheme colorScheme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: colorScheme.tertiaryContainer.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: colorScheme.tertiary.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.lightbulb_outline,
                color: colorScheme.tertiary,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Tips for Success',
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colorScheme.tertiary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildTipItem(
            '📅',
            'Practice daily for best results',
            theme,
            colorScheme,
          ),
          const SizedBox(height: 8),
          _buildTipItem(
            '🎯',
            'Complete modules in order to unlock new content',
            theme,
            colorScheme,
          ),
          const SizedBox(height: 8),
          _buildTipItem(
            '🔄',
            'Review previous lessons to reinforce learning',
            theme,
            colorScheme,
          ),
        ],
      ),
    );
  }

  Widget _buildTipItem(
    String emoji,
    String text,
    ThemeData theme,
    ColorScheme colorScheme,
  ) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(emoji, style: const TextStyle(fontSize: 16)),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: theme.textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildBottomAction(ThemeData theme, ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: colorScheme.shadow.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: AnimatedOnboardingButton(
          text: 'Start My Journey',
          icon: Icons.rocket_launch,
          onPressed: () {
            context.read<OnboardingBloc>().add(
              CompleteLearningPathVisualizationEvent(),
            );
          },
        ),
      ),
    );
  }

  Color _getCategoryColor(LearningCategory category) {
    switch (category) {
      case LearningCategory.business:
        return Colors.blue.shade600;
      case LearningCategory.travel:
        return Colors.orange.shade600;
      case LearningCategory.education:
        return Colors.purple.shade600;
      case LearningCategory.dailyLife:
        return Colors.green.shade600;
      case LearningCategory.entertainment:
        return Colors.pink.shade600;
      case LearningCategory.technology:
        return Colors.teal.shade600;
      case LearningCategory.health:
        return Colors.red.shade600;
      case LearningCategory.culture:
        return Colors.amber.shade700;
      case LearningCategory.food:
        return Colors.brown.shade600;
      case LearningCategory.shopping:
        return Colors.indigo.shade500;
    }
  }
}
