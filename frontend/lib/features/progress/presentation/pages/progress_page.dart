import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_bottom_nav_bar.dart';
import '../../data/models/progress_models.dart';
import '../../data/repositories/progress_repository.dart';
import '../bloc/progress_bloc.dart';

class ProgressPage extends StatefulWidget {
  const ProgressPage({super.key});

  @override
  State<ProgressPage> createState() => _ProgressPageState();
}

class _ProgressPageState extends State<ProgressPage>
    with TickerProviderStateMixin {
  late ProgressBloc _progressBloc;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    final progressRepository = ProgressRepositoryImpl(
      ApiClient(SecureStorage()),
    );
    _progressBloc = ProgressBloc(progressRepository);

    _animationController = AnimationController(
      duration: AppConstants.longAnimation,
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _animationController.forward();
    _progressBloc.add(LoadProgressData());
  }

  @override
  void dispose() {
    _animationController.dispose();
    _progressBloc.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider<ProgressBloc>.value(
      value: _progressBloc,
      child: Scaffold(
        body: Container(
          decoration: _buildBackgroundDecoration(),
          child: SafeArea(
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: BlocBuilder<ProgressBloc, ProgressState>(
                builder: (context, state) {
                  if (state is ProgressLoading) {
                    return _buildLoadingState();
                  }

                  if (state is ProgressError) {
                    return _buildErrorState(context, state.message);
                  }

                  if (state is ProgressLoaded) {
                    return RefreshIndicator(
                      onRefresh: () async {
                        _progressBloc.add(RefreshProgressData());
                      },
                      color: Colors.white,
                      backgroundColor: AppTheme.primaryColor,
                      child: CustomScrollView(
                        physics: const BouncingScrollPhysics(
                          parent: AlwaysScrollableScrollPhysics(),
                        ),
                        slivers: [
                          _buildHeader(context, state),
                          SliverPadding(
                            padding: const EdgeInsets.all(
                              AppConstants.paddingM,
                            ),
                            sliver: SliverList(
                              delegate: SliverChildListDelegate([
                                // Streak Card
                                _buildStreakCard(context, state),
                                const SizedBox(height: AppConstants.paddingL),

                                // Level Progress
                                _buildLevelProgressCard(context, state),
                                const SizedBox(height: AppConstants.paddingL),

                                // Weekly Activity Chart
                                _buildWeeklyActivityCard(context, state),
                                const SizedBox(height: AppConstants.paddingL),

                                // Stats Grid
                                _buildStatsGrid(context, state),
                                const SizedBox(height: AppConstants.paddingL),

                                // Achievements Section
                                _buildAchievementsSection(context, state),
                                const SizedBox(height: AppConstants.paddingL),

                                // Learning Goals
                                if (state.learningGoals.isNotEmpty) ...[
                                  _buildLearningGoalsSection(context, state),
                                  const SizedBox(height: AppConstants.paddingL),
                                ],

                                // Skill Breakdown
                                _buildSkillBreakdownCard(context, state),

                                const SizedBox(height: AppConstants.paddingXL),
                              ]),
                            ),
                          ),
                        ],
                      ),
                    );
                  }

                  return _buildEmptyState(context);
                },
              ),
            ),
          ),
        ),
        bottomNavigationBar: const AppBottomNavBar(currentIndex: 1),
      ),
    );
  }

  BoxDecoration _buildBackgroundDecoration() {
    return const BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFF1a1a2e), Color(0xFF16213e), Color(0xFF0f3460)],
        stops: [0.0, 0.5, 1.0],
      ),
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const CircularProgressIndicator(
              color: Colors.white,
              strokeWidth: 3,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Loading your progress...',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.8),
              fontSize: 16,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.paddingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(
                Icons.analytics_outlined,
                size: 64,
                color: Colors.white.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Start Your Journey!',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Complete exercises and lessons to see your progress here.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Colors.white.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () => _progressBloc.add(LoadProgressData()),
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 32,
                  vertical: 16,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, ProgressLoaded state) {
    final progress = state.userProgress;
    return SliverAppBar(
      expandedHeight: 160,
      floating: true,
      pinned: false,
      backgroundColor: Colors.transparent,
      elevation: 0,
      flexibleSpace: FlexibleSpaceBar(
        background: Container(
          padding: const EdgeInsets.all(AppConstants.paddingL),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                gradient: AppTheme.primaryGradient,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.insights,
                                color: Colors.white,
                                size: 24,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Your Progress',
                              style: Theme.of(context).textTheme.headlineMedium
                                  ?.copyWith(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          progress != null
                              ? '🎯 ${progress.totalPointsEarned} total points earned'
                              : 'Track your learning journey',
                          style: Theme.of(context).textTheme.bodyLarge
                              ?.copyWith(
                                color: Colors.white.withValues(alpha: 0.8),
                              ),
                        ),
                      ],
                    ),
                  ),
                  _GlassIconButton(
                    icon: Icons.refresh,
                    onPressed: () => _progressBloc.add(RefreshProgressData()),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildErrorState(BuildContext context, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppConstants.paddingL),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(
                Icons.error_outline,
                size: 64,
                color: Colors.red.shade300,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Unable to load progress',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.white.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () => _progressBloc.add(LoadProgressData()),
              icon: const Icon(Icons.refresh),
              label: const Text('Try Again'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 32,
                  vertical: 16,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStreakCard(BuildContext context, ProgressLoaded state) {
    final streak = state.streakInfo;
    final currentStreak =
        streak?.currentStreak ?? state.userProgress?.currentStreakDays ?? 0;
    final longestStreak =
        streak?.longestStreak ?? state.userProgress?.longestStreakDays ?? 0;
    final nextMilestone =
        streak?.nextMilestone ?? _getNextMilestone(currentStreak);
    final daysToMilestone =
        streak?.daysToNextMilestone ?? (nextMilestone - currentStreak);

    return _GlassCard(
      gradient: LinearGradient(
        colors: [
          Colors.orange.withValues(alpha: 0.4),
          Colors.deepOrange.withValues(alpha: 0.3),
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Colors.orange, Colors.deepOrange],
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.orange.withValues(alpha: 0.4),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.local_fire_department,
                  color: Colors.white,
                  size: 32,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          '$currentStreak',
                          style: Theme.of(context).textTheme.headlineLarge
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'Day Streak!',
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                        ),
                        if (currentStreak >= 7)
                          const Padding(
                            padding: EdgeInsets.only(left: 8),
                            child: Text('🔥', style: TextStyle(fontSize: 24)),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      currentStreak > 0
                          ? '$daysToMilestone days to $nextMilestone-day milestone!'
                          : 'Start learning today to begin your streak!',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white.withValues(alpha: 0.85),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStreakStat(
                  context,
                  'Current',
                  currentStreak.toString(),
                  Icons.whatshot,
                ),
                Container(
                  width: 1,
                  height: 40,
                  color: Colors.white.withValues(alpha: 0.2),
                ),
                _buildStreakStat(
                  context,
                  'Longest',
                  longestStreak.toString(),
                  Icons.emoji_events,
                ),
                Container(
                  width: 1,
                  height: 40,
                  color: Colors.white.withValues(alpha: 0.2),
                ),
                _buildStreakStat(context, 'Goal', '$nextMilestone', Icons.flag),
              ],
            ),
          ),
        ],
      ),
    );
  }

  int _getNextMilestone(int currentStreak) {
    final milestones = [7, 14, 30, 60, 100, 365];
    for (final milestone in milestones) {
      if (currentStreak < milestone) return milestone;
    }
    return (currentStreak / 100).ceil() * 100 + 100;
  }

  Widget _buildStreakStat(
    BuildContext context,
    String label,
    String value,
    IconData icon,
  ) {
    return Column(
      children: [
        Icon(icon, color: Colors.white.withValues(alpha: 0.7), size: 18),
        const SizedBox(height: 4),
        Text(
          value,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Colors.white.withValues(alpha: 0.7),
          ),
        ),
      ],
    );
  }

  Widget _buildLevelProgressCard(BuildContext context, ProgressLoaded state) {
    final progress = state.userProgress;
    final level =
        progress?.currentLevel ??
        state.dashboard?.levelProgress.currentLevel ??
        'A1';

    // Calculate percentage from multiple sources for accuracy
    double percentage =
        progress?.levelProgressPercentage ??
        state.dashboard?.levelProgress.progressPercentage ??
        0.0;

    // If percentage is 0, try to calculate from exercises completed
    if (percentage == 0 && progress != null) {
      // Estimate progress based on exercises completed (assume 100 exercises per level)
      final exercisesPerLevel = 100;
      percentage =
          ((progress.totalExercisesCompleted % exercisesPerLevel) /
                  exercisesPerLevel *
                  100)
              .clamp(0.0, 99.0);
    }

    final nextLevel = _getNextLevel(level);

    return _GlassCard(
      gradient: LinearGradient(
        colors: [
          AppTheme.primaryColor.withValues(alpha: 0.4),
          AppTheme.secondaryColor.withValues(alpha: 0.3),
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Current Level',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.white.withValues(alpha: 0.7),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 20,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          gradient: AppTheme.primaryGradient,
                          borderRadius: BorderRadius.circular(20),
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.primaryColor.withValues(
                                alpha: 0.4,
                              ),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Text(
                          level.toUpperCase(),
                          style: Theme.of(context).textTheme.headlineSmall
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Icon(
                        Icons.arrow_forward,
                        color: Colors.white.withValues(alpha: 0.5),
                        size: 20,
                      ),
                      const SizedBox(width: 12),
                      Text(
                        nextLevel,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w600,
                          color: Colors.white.withValues(alpha: 0.5),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  '${percentage.toInt()}%',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Progress to $nextLevel',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.white.withValues(alpha: 0.7),
                ),
              ),
              const SizedBox(height: 8),
              Stack(
                children: [
                  Container(
                    height: 12,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                  FractionallySizedBox(
                    widthFactor: (percentage / 100).clamp(0.0, 1.0),
                    child: Container(
                      height: 12,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Colors.white, Color(0xFFE0E0E0)],
                        ),
                        borderRadius: BorderRadius.circular(6),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.white.withValues(alpha: 0.4),
                            blurRadius: 8,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildLevelStat(
                context,
                Icons.menu_book,
                '${progress?.vocabularyMastered ?? 0}',
                'Words',
                Colors.purple,
              ),
              _buildLevelStat(
                context,
                Icons.spellcheck,
                '${progress?.grammarRulesLearned ?? 0}',
                'Grammar',
                Colors.blue,
              ),
              _buildLevelStat(
                context,
                Icons.check_circle,
                '${progress?.totalExercisesCompleted ?? 0}',
                'Exercises',
                Colors.green,
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _getNextLevel(String currentLevel) {
    const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
    final currentIndex = levels.indexOf(currentLevel.toUpperCase());
    if (currentIndex >= 0 && currentIndex < levels.length - 1) {
      return levels[currentIndex + 1];
    }
    return 'C2';
  }

  Widget _buildLevelStat(
    BuildContext context,
    IconData icon,
    String value,
    String label,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(height: 6),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.white.withValues(alpha: 0.7),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWeeklyActivityCard(BuildContext context, ProgressLoaded state) {
    final dailyProgress = state.dailyProgress;

    return _GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.teal.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.calendar_today,
                      color: Colors.teal,
                      size: 18,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    'This Week\'s Activity',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
              _buildTotalMinutes(context, dailyProgress),
            ],
          ),
          const SizedBox(height: 24),
          SizedBox(
            height: 140,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: _buildWeekBars(context, dailyProgress),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildLegendItem(context, Colors.teal, 'Study time'),
              const SizedBox(width: 24),
              _buildLegendItem(context, Colors.amber, 'Goal met'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTotalMinutes(
    BuildContext context,
    List<DailyProgressData> dailyProgress,
  ) {
    final totalMinutes = dailyProgress.fold(
      0,
      (sum, p) => sum + p.studyTimeMinutes,
    );
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.teal.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '${_formatMinutes(totalMinutes)} total',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: Colors.teal,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  List<Widget> _buildWeekBars(
    BuildContext context,
    List<DailyProgressData> dailyProgress,
  ) {
    final days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final now = DateTime.now();

    return List.generate(7, (index) {
      final dayOffset = index - now.weekday + 1;
      final date = now.add(Duration(days: dayOffset));

      final dayProgress = dailyProgress.where((p) {
        return p.date.year == date.year &&
            p.date.month == date.month &&
            p.date.day == date.day;
      }).firstOrNull;

      final minutes = dayProgress?.studyTimeMinutes ?? 0;
      final goalMet = dayProgress?.dailyGoalMet ?? false;
      final maxMinutes = 60.0;
      final height = minutes > 0
          ? (minutes / maxMinutes * 80).clamp(8.0, 80.0)
          : 4.0;
      final isToday =
          date.day == now.day &&
          date.month == now.month &&
          date.year == now.year;

      return Column(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          if (minutes > 0)
            Text(
              '${minutes}m',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.white.withValues(alpha: 0.7),
                fontSize: 10,
              ),
            ),
          const SizedBox(height: 4),
          AnimatedContainer(
            duration: const Duration(milliseconds: 500),
            width: 36,
            height: height,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.bottomCenter,
                end: Alignment.topCenter,
                colors: goalMet
                    ? [Colors.amber, Colors.orange]
                    : [Colors.teal, Colors.cyan],
              ),
              borderRadius: BorderRadius.circular(8),
              boxShadow: minutes > 0
                  ? [
                      BoxShadow(
                        color: (goalMet ? Colors.amber : Colors.teal)
                            .withValues(alpha: 0.4),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ]
                  : null,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: isToday
                ? BoxDecoration(
                    color: AppTheme.primaryColor.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(8),
                  )
                : null,
            child: Text(
              days[index],
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: isToday
                    ? Colors.white
                    : Colors.white.withValues(alpha: 0.6),
                fontWeight: isToday ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ),
        ],
      );
    });
  }

  Widget _buildLegendItem(BuildContext context, Color color, String label) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Colors.white.withValues(alpha: 0.7),
          ),
        ),
      ],
    );
  }

  Widget _buildStatsGrid(BuildContext context, ProgressLoaded state) {
    final progress = state.userProgress;

    return Row(
      children: [
        Expanded(
          child: _StatCard(
            icon: Icons.timer,
            iconColor: Colors.blue,
            value: _formatMinutes(progress?.totalStudyTimeMinutes ?? 0),
            label: 'Study Time',
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatCard(
            icon: Icons.check_circle,
            iconColor: Colors.green,
            value: '${progress?.totalExercisesCompleted ?? 0}',
            label: 'Exercises',
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatCard(
            icon: Icons.track_changes,
            iconColor: Colors.purple,
            value: '${((progress?.averageAccuracy ?? 0) * 100).toInt()}%',
            label: 'Accuracy',
          ),
        ),
      ],
    );
  }

  String _formatMinutes(int minutes) {
    if (minutes < 60) return '${minutes}m';
    final hours = minutes ~/ 60;
    final mins = minutes % 60;
    if (mins == 0) return '${hours}h';
    return '${hours}h ${mins}m';
  }

  Widget _buildAchievementsSection(BuildContext context, ProgressLoaded state) {
    final earned = state.earnedAchievements;
    final all = state.allAchievements;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.amber.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.emoji_events,
                    color: Colors.amber,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  'Achievements',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.amber.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '${earned.length}/${all.isEmpty ? earned.length : all.length}',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.amber,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (earned.isEmpty && all.isEmpty)
          _GlassCard(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.amber.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Icon(
                        Icons.emoji_events_outlined,
                        size: 48,
                        color: Colors.amber.withValues(alpha: 0.5),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'No achievements yet',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Complete exercises to earn your first achievement!',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          )
        else
          SizedBox(
            height: 130,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: all.isEmpty ? earned.length : all.length,
              separatorBuilder: (_, _) => const SizedBox(width: 12),
              itemBuilder: (context, index) {
                final achievement = all.isEmpty ? earned[index] : all[index];
                final isEarned = earned.any((e) => e.id == achievement.id);
                return _AchievementCard(
                  achievement: achievement,
                  isEarned: isEarned,
                );
              },
            ),
          ),
      ],
    );
  }

  Widget _buildLearningGoalsSection(
    BuildContext context,
    ProgressLoaded state,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.flag, color: Colors.green, size: 20),
            ),
            const SizedBox(width: 12),
            Text(
              'Learning Goals',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        ...state.learningGoals
            .take(3)
            .map(
              (goal) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _LearningGoalCard(goal: goal),
              ),
            ),
      ],
    );
  }

  Widget _buildSkillBreakdownCard(BuildContext context, ProgressLoaded state) {
    final stats = state.exerciseStats;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.purple.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(
                Icons.pie_chart,
                color: Colors.purple,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Text(
              'Skill Breakdown',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        _GlassCard(
          child: stats == null || stats.accuracyByType.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      children: [
                        Icon(
                          Icons.pie_chart_outline,
                          size: 48,
                          color: Colors.white.withValues(alpha: 0.4),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Complete exercises to see your skill breakdown',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: Colors.white.withValues(alpha: 0.7),
                              ),
                        ),
                      ],
                    ),
                  ),
                )
              : Column(
                  children: stats.accuracyByType.entries
                      .map(
                        (entry) => Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: _SkillProgressBar(
                            skill: _formatSkillName(entry.key),
                            progress: entry.value / 100,
                            color: _getSkillColor(entry.key),
                          ),
                        ),
                      )
                      .toList(),
                ),
        ),
      ],
    );
  }

  String _formatSkillName(String skill) {
    return skill
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) {
          if (word.isEmpty) return word;
          return word[0].toUpperCase() + word.substring(1).toLowerCase();
        })
        .join(' ');
  }

  Color _getSkillColor(String skill) {
    switch (skill.toLowerCase()) {
      case 'vocabulary':
        return Colors.purple;
      case 'grammar':
        return Colors.blue;
      case 'reading':
        return Colors.green;
      case 'listening':
        return Colors.orange;
      case 'speaking':
        return Colors.red;
      case 'writing':
        return Colors.teal;
      default:
        return Colors.grey;
    }
  }
}

// Glass Card Widget
class _GlassCard extends StatelessWidget {
  final Widget child;
  final Gradient? gradient;

  const _GlassCard({required this.child, this.gradient});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          decoration: BoxDecoration(
            gradient:
                gradient ??
                LinearGradient(
                  colors: [
                    Colors.white.withValues(alpha: 0.15),
                    Colors.white.withValues(alpha: 0.05),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.2),
              width: 1.5,
            ),
          ),
          padding: const EdgeInsets.all(20),
          child: child,
        ),
      ),
    );
  }
}

// Glass Icon Button
class _GlassIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onPressed;

  const _GlassIconButton({required this.icon, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
          ),
          child: IconButton(
            onPressed: onPressed,
            icon: Icon(icon, color: Colors.white),
          ),
        ),
      ),
    );
  }
}

// Stat Card Widget
class _StatCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String value;
  final String label;

  const _StatCard({
    required this.icon,
    required this.iconColor,
    required this.value,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
          ),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: iconColor, size: 22),
              ),
              const SizedBox(height: 10),
              Text(
                value,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.white.withValues(alpha: 0.7),
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Achievement Card
class _AchievementCard extends StatelessWidget {
  final AchievementData achievement;
  final bool isEarned;

  const _AchievementCard({required this.achievement, required this.isEarned});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          width: 110,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            gradient: isEarned
                ? LinearGradient(
                    colors: [
                      Colors.amber.withValues(alpha: 0.4),
                      Colors.orange.withValues(alpha: 0.3),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  )
                : LinearGradient(
                    colors: [
                      Colors.grey.withValues(alpha: 0.3),
                      Colors.grey.withValues(alpha: 0.1),
                    ],
                  ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isEarned
                  ? Colors.amber.withValues(alpha: 0.5)
                  : Colors.grey.withValues(alpha: 0.3),
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isEarned
                      ? Colors.amber.withValues(alpha: 0.2)
                      : Colors.grey.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.emoji_events,
                  size: 28,
                  color: isEarned ? Colors.amber : Colors.grey,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                achievement.name,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: isEarned ? Colors.white : Colors.grey,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '+${achievement.pointsReward} pts',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: isEarned
                      ? Colors.amber.withValues(alpha: 0.8)
                      : Colors.grey.withValues(alpha: 0.6),
                  fontSize: 10,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Learning Goal Card
class _LearningGoalCard extends StatelessWidget {
  final LearningGoalData goal;

  const _LearningGoalCard({required this.goal});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Row(
                      children: [
                        Icon(
                          goal.isCompleted
                              ? Icons.check_circle
                              : Icons.flag_outlined,
                          color: goal.isCompleted
                              ? Colors.green
                              : Colors.white.withValues(alpha: 0.7),
                          size: 20,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            goal.title,
                            style: Theme.of(context).textTheme.titleSmall
                                ?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w600,
                                ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: goal.isCompleted
                          ? Colors.green.withValues(alpha: 0.2)
                          : AppTheme.primaryColor.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '${goal.currentValue}/${goal.targetValue}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: goal.isCompleted
                            ? Colors.green
                            : AppTheme.primaryColor,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Stack(
                children: [
                  Container(
                    height: 8,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                  FractionallySizedBox(
                    widthFactor: (goal.progressPercentage / 100).clamp(
                      0.0,
                      1.0,
                    ),
                    child: Container(
                      height: 8,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: goal.isCompleted
                              ? [Colors.green, Colors.green.shade300]
                              : [
                                  AppTheme.primaryColor,
                                  AppTheme.secondaryColor,
                                ],
                        ),
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Skill Progress Bar
class _SkillProgressBar extends StatelessWidget {
  final String skill;
  final double progress;
  final Color color;

  const _SkillProgressBar({
    required this.skill,
    required this.progress,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Icon(_getSkillIcon(skill), color: color, size: 16),
                ),
                const SizedBox(width: 10),
                Text(
                  skill,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
            Text(
              '${(progress * 100).toInt()}%',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Stack(
          children: [
            Container(
              height: 8,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            FractionallySizedBox(
              widthFactor: progress.clamp(0.0, 1.0),
              child: Container(
                height: 8,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [color, color.withValues(alpha: 0.7)],
                  ),
                  borderRadius: BorderRadius.circular(4),
                  boxShadow: [
                    BoxShadow(
                      color: color.withValues(alpha: 0.4),
                      blurRadius: 6,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  IconData _getSkillIcon(String skill) {
    switch (skill.toLowerCase()) {
      case 'vocabulary':
        return Icons.menu_book;
      case 'grammar':
        return Icons.spellcheck;
      case 'reading':
        return Icons.article;
      case 'listening':
        return Icons.headphones;
      case 'speaking':
        return Icons.mic;
      case 'writing':
        return Icons.edit;
      default:
        return Icons.school;
    }
  }
}
