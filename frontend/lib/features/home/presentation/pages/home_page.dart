import 'dart:ui';

import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/di/injection_container.dart' as di;
import '../../../../core/network/api_client.dart';
import '../../../../core/services/auth_service.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/ai_coach_widget.dart';
import '../../../../core/widgets/enhanced_ai_coach_widget.dart';
import '../../../../core/widgets/rive_coach_widget.dart';
import '../../../../core/widgets/app_bottom_nav_bar.dart';
import '../../../onboarding/data/models/onboarding_models.dart';
import '../../../onboarding/data/repositories/onboarding_repository.dart';
import '../../../onboarding/presentation/widgets/lesson_loading_screen.dart';
import '../widgets/learning_path_section.dart';
import '../widgets/skill_practice_grid.dart';

/// Coach Center - The unified home screen for the app
/// Combines AI coach, training goals, skill practice, and learning path
class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage>
    with TickerProviderStateMixin, WidgetsBindingObserver, RouteAware {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  late ApiClient _apiClient;

  // Route observer for detecting navigation (reserved for future use)
  // ignore: unused_field
  RouteObserver<ModalRoute<void>>? _routeObserver;

  // User state
  String _userName = 'Learner';
  bool _onboardingCompleted = false;
  bool _isLoading = true;

  // Modules state
  List<LearningModule> _modules = [];

  // Stats from dashboard
  int _currentStreak = 0;
  int _todayMinutes = 0;
  int _dailyGoal = 30;
  int _exercisesCompleted = 0;
  String _currentLevel = 'A1';
  int _totalPoints = 0;

  // Skill levels for recommendations
  Map<String, double> _skillLevels = {};
  String? _weakestSkill;

  // Track if we need to refresh on next visibility (reserved for future use)
  // ignore: unused_field, prefer_final_fields
  bool _needsRefresh = false;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient(SecureStorage());

    // Add observer for app lifecycle (background/foreground)
    WidgetsBinding.instance.addObserver(this);

    _animationController = AnimationController(
      duration: AppConstants.longAnimation,
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _slideAnimation =
        Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero).animate(
          CurvedAnimation(
            parent: _animationController,
            curve: Curves.easeOutCubic,
          ),
        );

    _animationController.forward();

    WidgetsBinding.instance.addPostFrameCallback((_) => _loadUserData());
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Subscribe to route observer for navigation events
    _routeObserver = ModalRoute.of(context)?.settings.name != null
        ? null // Will be properly set up in production with GoRouter observer
        : null;
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _animationController.dispose();
    super.dispose();
  }

  /// Called when app lifecycle changes (foreground/background)
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    if (state == AppLifecycleState.resumed) {
      // App came back to foreground - refresh data
      if (kDebugMode) {
        print('🔄 HomePage: App resumed, refreshing data...');
      }
      _refreshData();
    }
  }

  /// Called when this route becomes the top route again (user navigated back)
  @override
  void didPopNext() {
    super.didPopNext();
    // User navigated back to this page - refresh data
    if (kDebugMode) {
      print('🔄 HomePage: Navigated back to home, refreshing data...');
    }
    _refreshData();
  }

  Future<void> _loadUserData() async {
    try {
      final authService = di.sl<AuthService>();
      final userData = await authService.getUserData();

      if (userData != null) {
        final onboardingCompleted =
            (userData['onboarding_completed'] ??
                userData['onboardingCompleted'] ??
                false) ==
            true;

        setState(() {
          _userName =
              userData['full_name'] ?? userData['username'] ?? 'Learner';
          _onboardingCompleted = onboardingCompleted;
          _currentLevel = userData['current_level'] ?? 'A1';
          _dailyGoal = userData['daily_goal_minutes'] ?? 30;
          _isLoading = false;
        });

        // Fetch all data in parallel
        await Future.wait([
          _fetchDashboardData(),
          if (onboardingCompleted) _fetchModules(),
          _fetchSkillLevels(),
        ]);
      } else {
        setState(() {
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchDashboardData() async {
    try {
      final response = await _apiClient.get('/users/dashboard');

      if (response.statusCode == 200) {
        final data = response.data;

        setState(() {
          // Daily progress
          final dailyProgress = data['daily_progress'] ?? {};
          _todayMinutes = dailyProgress['completed_minutes'] ?? 0;
          _dailyGoal = dailyProgress['goal_minutes'] ?? 30;

          // Overall stats
          final overallStats = data['overall_stats'] ?? {};
          _currentStreak = overallStats['current_streak'] ?? 0;
          _exercisesCompleted = overallStats['total_exercises'] ?? 0;
          _totalPoints = overallStats['total_points'] ?? 0;

          // User info
          final userInfo = data['user_info'] ?? {};
          _currentLevel = userInfo['current_level'] ?? _currentLevel;
        });
      }
    } catch (e) {
      if (kDebugMode) {
        print('Failed to fetch dashboard data: $e');
      }
    }
  }

  Future<void> _fetchSkillLevels() async {
    try {
      final response = await _apiClient.get('/progress/');

      if (response.statusCode == 200) {
        final data = response.data as Map<String, dynamic>;
        final skillStats =
            data['skill_statistics'] as Map<String, dynamic>? ?? {};

        final newSkillLevels = <String, double>{};
        String? weakest;
        double weakestLevel = 100;

        skillStats.forEach((key, value) {
          if (value is Map) {
            final level =
                ((value['mastery_percentage'] ?? value['accuracy'] ?? 50)
                        as num)
                    .toDouble();
            newSkillLevels[key.toLowerCase()] = level;
            if (level < weakestLevel) {
              weakestLevel = level;
              weakest = key.toLowerCase();
            }
          }
        });

        setState(() {
          _skillLevels = newSkillLevels;
          _weakestSkill = weakest;
        });
      }
    } catch (e) {
      if (kDebugMode) {
        print('Failed to fetch skill levels: $e');
      }
    }
  }

  Future<void> _fetchModules() async {
    if (!_onboardingCompleted) return;

    setState(() {});

    try {
      final repo = RepositoryProvider.of<OnboardingRepository>(context);

      final userProfile = await repo.getUserProfile('me');
      if (userProfile == null) {
        setState(() {
          _modules = [];
        });
        return;
      }

      LearningPath? path = await repo.loadLearningPath();

      if (path == null || path.modules.isEmpty) {
        path = await repo.generateLearningPath(userProfile);
        await repo.saveLearningPath(path);
      }

      // Ensure first module is unlocked
      final modules = path.modules.map((m) {
        if (path!.modules.indexOf(m) == 0 && !m.isUnlocked) {
          return m.copyWith(isUnlocked: true);
        }
        return m;
      }).toList();

      setState(() {
        _userName = userProfile.name;
        _modules = modules.take(8).toList();
      });
    } catch (e) {
      if (kDebugMode) {
        print('Error fetching modules: $e');
      }
      setState(() {});
    }
  }

  Future<void> _refreshData() async {
    await Future.wait([
      _fetchDashboardData(),
      _fetchModules(),
      _fetchSkillLevels(),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        body: Container(
          decoration: _buildBackgroundDecoration(),
          child: const Center(
            child: CircularProgressIndicator(color: Colors.white),
          ),
        ),
      );
    }

    return Scaffold(
      body: Container(
        decoration: _buildBackgroundDecoration(),
        child: SafeArea(
          child: FadeTransition(
            opacity: _fadeAnimation,
            child: SlideTransition(
              position: _slideAnimation,
              child: RefreshIndicator(
                onRefresh: _refreshData,
                color: AppTheme.primaryColor,
                child: CustomScrollView(
                  physics: const AlwaysScrollableScrollPhysics(
                    parent: BouncingScrollPhysics(),
                  ),
                  slivers: [
                    _buildHeader(context),
                    SliverPadding(
                      padding: const EdgeInsets.all(AppConstants.paddingM),
                      sliver: SliverList(
                        delegate: SliverChildListDelegate([
                          if (!_onboardingCompleted) ...[
                            _buildWelcomeCard(context),
                            const SizedBox(height: AppConstants.paddingL),
                            _buildStartAssessmentCard(context),
                          ] else ...[
                            // AI Coach Card with personalized message
                            _buildCoachCard(context),
                            const SizedBox(height: AppConstants.paddingL),

                            // Today's Training Progress
                            _buildTodaysTrainingCard(context),
                            const SizedBox(height: AppConstants.paddingL),

                            // Stats Row
                            _buildStatsRow(context),
                            const SizedBox(height: AppConstants.paddingL),

                            // Continue Learning (if modules available)
                            if (_modules.isNotEmpty) ...[
                              _buildSectionTitle(context, 'Continue Learning'),
                              const SizedBox(height: AppConstants.paddingM),
                              _buildContinueLearningCard(context),
                              const SizedBox(height: AppConstants.paddingL),
                            ],

                            // Skill Practice Grid
                            _buildSectionTitle(context, 'Practice Skills'),
                            const SizedBox(height: AppConstants.paddingM),
                            SkillPracticeGrid(skillLevels: _skillLevels),
                            const SizedBox(height: AppConstants.paddingL),

                            // Learning Path Section (integrated from Journey)
                            if (_onboardingCompleted) ...[
                              _buildSectionTitle(context, 'Your Learning Path'),
                              const SizedBox(height: AppConstants.paddingM),
                              LearningPathSection(
                                onModuleCompleted: _refreshData,
                              ),
                              const SizedBox(height: AppConstants.paddingL),
                            ],

                            // Coach Tips
                            _buildCoachTipCard(context),
                          ],
                          const SizedBox(height: AppConstants.paddingXL),
                        ]),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
      bottomNavigationBar: const AppBottomNavBar(currentIndex: 0),
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

  Widget _buildHeader(BuildContext context) {
    return SliverAppBar(
      expandedHeight: 130,
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
                    child: Row(
                      children: [
                        // Coach Avatar
                        Stack(
                          children: [
                            Container(
                              width: 52,
                              height: 52,
                              decoration: BoxDecoration(
                                gradient: AppTheme.primaryGradient,
                                borderRadius: BorderRadius.circular(16),
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
                              child: const Center(
                                child: Text(
                                  '🎯',
                                  style: TextStyle(fontSize: 26),
                                ),
                              ),
                            ),
                            Positioned(
                              right: 0,
                              bottom: 0,
                              child: Container(
                                width: 14,
                                height: 14,
                                decoration: BoxDecoration(
                                  color: Colors.green,
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: const Color(0xFF1a1a2e),
                                    width: 2,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _getGreeting(),
                                style: Theme.of(context).textTheme.bodyMedium
                                    ?.copyWith(
                                      color: Colors.white.withValues(
                                        alpha: 0.7,
                                      ),
                                    ),
                              ),
                              const SizedBox(height: 2),
                              Row(
                                children: [
                                  Flexible(
                                    child: Text(
                                      _userName,
                                      style: Theme.of(context)
                                          .textTheme
                                          .headlineSmall
                                          ?.copyWith(
                                            color: Colors.white,
                                            fontWeight: FontWeight.bold,
                                          ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  if (_currentStreak > 0)
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 3,
                                      ),
                                      decoration: BoxDecoration(
                                        gradient: const LinearGradient(
                                          colors: [
                                            Colors.orange,
                                            Colors.deepOrange,
                                          ],
                                        ),
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          const Icon(
                                            Icons.local_fire_department,
                                            color: Colors.white,
                                            size: 12,
                                          ),
                                          const SizedBox(width: 2),
                                          Text(
                                            '$_currentStreak',
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontSize: 11,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  _GlassIconButton(
                    icon: Icons.person_outline,
                    onPressed: () => context.push('/profile'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _getGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return '☀️ Good Morning';
    if (hour < 17) return '🌤️ Good Afternoon';
    return '🌙 Good Evening';
  }

  Widget _buildSectionTitle(BuildContext context, String title) {
    return Text(
      title,
      style: Theme.of(context).textTheme.titleLarge?.copyWith(
        fontWeight: FontWeight.bold,
        color: Colors.white,
      ),
    );
  }

  Widget _buildCoachCard(BuildContext context) {
    final coachState = _currentStreak >= 7
        ? CoachState.celebrating
        : _todayMinutes >= _dailyGoal
            ? CoachState.happy
            : _weakestSkill != null
                ? CoachState.speaking
                : CoachState.idle;

    String message;
    if (_currentStreak >= 7) {
      message = CoachMessages.getEncouragement(_currentStreak);
    } else if (_todayMinutes >= _dailyGoal) {
      message =
          'Amazing work today! You\'ve hit your daily goal! Ready for a bonus round? 🏆';
    } else if (_weakestSkill != null) {
      message =
          'Hey $_userName! I noticed your ${_weakestSkill!} could use some practice. Want to work on it together? 💪';
    } else {
      message = CoachMessages.getGreeting(_userName, DateTime.now().hour);
    }

    return EnhancedAICoachCard(
      message: message,
      state: coachState,
      showPulse: _currentStreak >= 7,
      compact: true,
      onTap: () => _showCoachChat(context),
    );
  }

  Widget _buildTodaysTrainingCard(BuildContext context) {
    final progressPercent = _dailyGoal > 0
        ? (_todayMinutes / _dailyGoal * 100).clamp(0, 100)
        : 0;
    final isGoalMet = progressPercent >= 100;

    return _GlassCard(
      gradient: LinearGradient(
        colors: isGoalMet
            ? [
                Colors.green.withValues(alpha: 0.4),
                Colors.teal.withValues(alpha: 0.25),
              ]
            : [
                AppTheme.primaryColor.withValues(alpha: 0.4),
                Colors.blue.withValues(alpha: 0.25),
              ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  gradient: isGoalMet
                      ? const LinearGradient(
                          colors: [Colors.green, Colors.teal],
                        )
                      : AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  isGoalMet ? Icons.check_circle : Icons.fitness_center,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isGoalMet ? '🎉 Goal Achieved!' : '💪 Today\'s Training',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      isGoalMet
                          ? 'You\'ve completed your daily goal!'
                          : 'Train for $_dailyGoal min to complete your goal',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white.withValues(alpha: 0.8),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Progress bar
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '$_todayMinutes of $_dailyGoal minutes',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.white.withValues(alpha: 0.8),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${progressPercent.toInt()}%',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Stack(
            children: [
              Container(
                height: 10,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(5),
                ),
              ),
              FractionallySizedBox(
                widthFactor: (progressPercent / 100).clamp(0.0, 1.0),
                child: Container(
                  height: 10,
                  decoration: BoxDecoration(
                    gradient: isGoalMet
                        ? const LinearGradient(
                            colors: [Colors.green, Colors.teal],
                          )
                        : const LinearGradient(
                            colors: [Colors.white, Color(0xFFE0E0E0)],
                          ),
                    borderRadius: BorderRadius.circular(5),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Quick training options
          const QuickActionsRow(),
        ],
      ),
    );
  }

  Widget _buildStatsRow(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _StatCard(
            icon: Icons.local_fire_department,
            iconColor: Colors.orange,
            value: '$_currentStreak',
            label: 'Day Streak',
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatCard(
            icon: Icons.star,
            iconColor: Colors.amber,
            value: '$_totalPoints',
            label: 'Points',
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatCard(
            icon: Icons.check_circle,
            iconColor: Colors.green,
            value: '$_exercisesCompleted',
            label: 'Exercises',
          ),
        ),
      ],
    );
  }

  Widget _buildContinueLearningCard(BuildContext context) {
    if (_modules.isEmpty) return const SizedBox.shrink();

    final nextModule = _modules.firstWhere(
      (m) => m.isUnlocked && !m.isCompleted,
      orElse: () => _modules.first,
    );

    return GestureDetector(
      onTap: () => _startModule(nextModule),
      child: _GlassCard(
        gradient: LinearGradient(
          colors: [
            AppTheme.primaryColor.withValues(alpha: 0.4),
            AppTheme.secondaryColor.withValues(alpha: 0.3),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: AppTheme.primaryGradient,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.play_circle_fill,
                color: Colors.white,
                size: 32,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    nextModule.title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(
                        Icons.schedule,
                        size: 14,
                        color: Colors.white.withValues(alpha: 0.7),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '${nextModule.estimatedMinutes} min',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.white.withValues(alpha: 0.7),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Icon(
                        Icons.auto_awesome,
                        size: 14,
                        color: Colors.white.withValues(alpha: 0.7),
                      ),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text(
                          nextModule.skills.take(2).join(', '),
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(
                                color: Colors.white.withValues(alpha: 0.7),
                              ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                'Continue',
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCoachTipCard(BuildContext context) {
    String tip;
    if (_weakestSkill != null) {
      tip = CoachMessages.getExerciseTip(_weakestSkill!);
    } else {
      tip = CoachMessages.getMotivation();
    }

    return _GlassCard(
      gradient: LinearGradient(
        colors: [
          Colors.purple.withValues(alpha: 0.3),
          Colors.indigo.withValues(alpha: 0.2),
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Text('💡', style: TextStyle(fontSize: 24)),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Coach\'s Tip',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  tip,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.9),
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWelcomeCard(BuildContext context) {
    return _GlassCard(
      gradient: LinearGradient(
        colors: [
          AppTheme.primaryColor.withValues(alpha: 0.4),
          Colors.purple.withValues(alpha: 0.3),
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.3),
                    width: 2,
                  ),
                ),
                child: const Center(
                  child: Text('👋', style: TextStyle(fontSize: 32)),
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
                          'Hey there!',
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.green,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Text(
                            'NEW',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'I\'m ${AppConstants.coachName}, your AI English trainer!',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.9),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '💬 "Let me get to know your English level so I can create the perfect training plan for you!"',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white,
                    height: 1.5,
                    fontStyle: FontStyle.italic,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  '• Quick 5-minute assessment\n• Personalized learning path\n• Daily training sessions',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.8),
                    height: 1.6,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStartAssessmentCard(BuildContext context) {
    return GestureDetector(
      onTap: () => context.push('/onboarding'),
      child: Container(
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Colors.green, Colors.teal],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(24),
          boxShadow: [
            BoxShadow(
              color: Colors.green.withValues(alpha: 0.4),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: const Center(
                  child: Text('🚀', style: TextStyle(fontSize: 28)),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Start Training!',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Take a quick assessment to begin your journey',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.9),
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.arrow_forward,
                  color: Colors.green,
                  size: 22,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _startModule(LearningModule module) async {
    if (!module.isUnlocked) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Complete previous modules to unlock this one'),
        ),
      );
      return;
    }

    final dayNumber =
        int.tryParse(module.id.replaceFirst(RegExp(r'^day_'), '')) ?? 1;

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            LessonLoadingScreen(moduleId: module.id, dayNumber: dayNumber),
      ),
    );

    if (mounted) {
      _refreshData();
    }
  }

  void _showCoachChat(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => _CoachChatSheet(
        userName: _userName,
        streak: _currentStreak,
        todayMinutes: _todayMinutes,
        dailyGoal: _dailyGoal,
        weakestSkill: _weakestSkill,
      ),
    );
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
              Icon(icon, color: iconColor, size: 24),
              const SizedBox(height: 8),
              Text(
                value,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 2),
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

// Coach Chat Sheet
class _CoachChatSheet extends StatelessWidget {
  final String userName;
  final int streak;
  final int todayMinutes;
  final int dailyGoal;
  final String? weakestSkill;

  const _CoachChatSheet({
    required this.userName,
    required this.streak,
    required this.todayMinutes,
    required this.dailyGoal,
    this.weakestSkill,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.8,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1a1a2e), Color(0xFF16213e), Color(0xFF0f3460)],
        ),
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: Column(
        children: [
          Container(
            margin: const EdgeInsets.only(top: 12),
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Container(
            padding: const EdgeInsets.all(20),
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: AppTheme.primaryGradient,
              borderRadius: BorderRadius.circular(24),
            ),
            child: Row(
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Center(
                    child: Text('🎯', style: TextStyle(fontSize: 32)),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Text(
                            AppConstants.coachDisplayName,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.green,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Text(
                              'Online',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Your Personal English Trainer',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.9),
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                _buildCoachMessage(
                  context,
                  '👋',
                  'Hey $userName! Great to see you here!',
                ),
                _buildCoachMessage(
                  context,
                  streak > 0 ? '🔥' : '💪',
                  streak > 0
                      ? 'You\'re on a $streak-day streak! That\'s what I call dedication!'
                      : 'Ready to start a new streak? Just one exercise today will do!',
                ),
                _buildCoachMessage(
                  context,
                  '📊',
                  todayMinutes >= dailyGoal
                      ? 'You\'ve already hit your $dailyGoal-minute goal today! Want to keep going?'
                      : 'You\'ve trained for $todayMinutes minutes today. ${dailyGoal - todayMinutes} more to hit your goal!',
                ),
                if (weakestSkill != null)
                  _buildCoachMessage(
                    context,
                    '🎯',
                    'I\'ve noticed your ${weakestSkill!} skills could use some extra attention. Let\'s work on that!',
                  ),
                _buildCoachMessage(
                  context,
                  '💡',
                  CoachMessages.getMotivation(),
                ),
                const SizedBox(height: 16),
                Text(
                  'Quick Actions',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 12),
                _buildQuickAction(
                  context,
                  Icons.play_arrow,
                  'Start a Quick Session',
                  'Perfect 5-minute vocabulary boost',
                  () {
                    Navigator.pop(context);
                    context.push('/practice?type=vocabulary');
                  },
                ),
                if (weakestSkill != null)
                  _buildQuickAction(
                    context,
                    Icons.trending_up,
                    'Practice $weakestSkill',
                    'Improve your weakest skill',
                    () {
                      Navigator.pop(context);
                      context.push('/practice?type=$weakestSkill');
                    },
                  ),
                _buildQuickAction(
                  context,
                  Icons.mic,
                  'Practice Speaking',
                  'Improve your pronunciation',
                  () {
                    Navigator.pop(context);
                    context.push('/practice?type=speaking');
                  },
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCoachMessage(
    BuildContext context,
    String emoji,
    String message,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text(emoji, style: const TextStyle(fontSize: 20)),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.1),
                borderRadius: const BorderRadius.only(
                  topRight: Radius.circular(16),
                  bottomLeft: Radius.circular(16),
                  bottomRight: Radius.circular(16),
                ),
              ),
              child: Text(
                message,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white,
                  height: 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickAction(
    BuildContext context,
    IconData icon,
    String title,
    String subtitle,
    VoidCallback onTap,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: Colors.white, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white.withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.arrow_forward_ios,
                size: 16,
                color: Colors.white.withValues(alpha: 0.5),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
