import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/di/injection_container.dart' as di;
import '../../../../core/network/api_client.dart';
import '../../../../core/services/auth_service.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_bottom_nav_bar.dart';
import '../../data/models/lesson_models.dart';
import '../../data/repositories/lessons_repository.dart';
import '../bloc/lessons_bloc.dart';
import 'ai_conversation_page.dart';
import 'ai_writing_page.dart';
import 'lesson_detail_page.dart';

class LessonsPage extends StatefulWidget {
  const LessonsPage({super.key});

  @override
  State<LessonsPage> createState() => _LessonsPageState();
}

class _LessonsPageState extends State<LessonsPage>
    with TickerProviderStateMixin {
  late LessonsBloc _lessonsBloc;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late ApiClient _apiClient;

  // User progress data
  int _completedLessons = 0;
  String _currentLevel = 'B1';
  int _weeklyStudyTime = 0;
  int _streakDays = 0;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient(SecureStorage());

    final lessonsRepository = LessonsRepositoryImpl(_apiClient);
    _lessonsBloc = LessonsBloc(lessonsRepository);

    _animationController = AnimationController(
      duration: AppConstants.longAnimation,
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _animationController.forward();
    _lessonsBloc.add(LoadLessonsData());
    _loadUserProgress();
  }

  Future<void> _loadUserProgress() async {
    try {
      final authService = di.sl<AuthService>();
      final userData = await authService.getUserData();

      if (userData != null) {
        setState(() {
          _currentLevel = userData['current_level'] ?? 'B1';
        });
      }

      final response = await _apiClient.get('/users/dashboard');
      if (response.statusCode == 200) {
        final data = response.data;
        setState(() {
          final weekSummary = data['week_summary'] ?? {};
          _weeklyStudyTime = weekSummary['total_study_time'] ?? 0;

          final overallStats = data['overall_stats'] ?? {};
          _completedLessons = overallStats['total_exercises'] ?? 0;
          _streakDays = overallStats['current_streak'] ?? 0;
        });
      }
    } catch (e) {
      debugPrint('Failed to load user progress: $e');
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    _lessonsBloc.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider<LessonsBloc>.value(
      value: _lessonsBloc,
      child: Scaffold(
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFFF8FAFF), Color(0xFFF0F4FF), Color(0xFFE8EFFF)],
            ),
          ),
          child: SafeArea(
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: RefreshIndicator(
                onRefresh: () async {
                  _lessonsBloc.add(LoadLessonsData());
                  await _loadUserProgress();
                },
                color: AppTheme.primaryColor,
                child: CustomScrollView(
                  physics: const BouncingScrollPhysics(
                    parent: AlwaysScrollableScrollPhysics(),
                  ),
                  slivers: [
                    _buildHeader(context),
                    SliverPadding(
                      padding: const EdgeInsets.all(AppConstants.paddingM),
                      sliver: SliverList(
                        delegate: SliverChildListDelegate([
                          // Progress Overview
                          _buildProgressOverview(context),
                          const SizedBox(height: AppConstants.paddingL),

                          // Today's Lessons Section
                          _buildSectionHeader(
                            context,
                            'Today\'s Lessons',
                            Icons.today,
                            AppTheme.primaryColor,
                          ),
                          const SizedBox(height: AppConstants.paddingM),
                          _buildTodaysLessons(context),
                          const SizedBox(height: AppConstants.paddingL),

                          // Quick Practice Section
                          _buildSectionHeader(
                            context,
                            'Quick Practice',
                            Icons.flash_on,
                            Colors.orange,
                          ),
                          const SizedBox(height: AppConstants.paddingM),
                          _buildQuickPracticeSection(context),
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
        floatingActionButton: _buildFAB(context),
        bottomNavigationBar: const AppBottomNavBar(
          currentIndex: 1,
          useDarkTheme: false,
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return SliverAppBar(
      expandedHeight: 160,
      floating: true,
      pinned: false,
      backgroundColor: Colors.transparent,
      elevation: 0,
      flexibleSpace: FlexibleSpaceBar(
        background: Container(
          decoration: BoxDecoration(
            gradient: AppTheme.primaryGradient,
            borderRadius: const BorderRadius.only(
              bottomLeft: Radius.circular(32),
              bottomRight: Radius.circular(32),
            ),
            boxShadow: [
              BoxShadow(
                color: AppTheme.primaryColor.withValues(alpha: 0.3),
                blurRadius: 20,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Padding(
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
                                  color: Colors.white.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: const Icon(
                                  Icons.school,
                                  color: Colors.white,
                                  size: 24,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Text(
                                'Learning Journey',
                                style: Theme.of(context)
                                    .textTheme
                                    .headlineMedium
                                    ?.copyWith(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                    ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Continue building your English skills',
                            style: Theme.of(context).textTheme.bodyLarge
                                ?.copyWith(
                                  color: Colors.white.withValues(alpha: 0.9),
                                ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: IconButton(
                        onPressed: () => _showStudyPlanSettings(context),
                        icon: const Icon(
                          Icons.settings_outlined,
                          color: Colors.white,
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

  Widget _buildProgressOverview(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 20,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.primaryColor.withValues(alpha: 0.3),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.trending_up,
                  color: Colors.white,
                  size: 28,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Level $_currentLevel',
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimaryColor,
                              ),
                        ),
                        if (_streakDays > 0)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.orange.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(
                                  Icons.local_fire_department,
                                  color: Colors.orange,
                                  size: 16,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  '$_streakDays',
                                  style: Theme.of(context).textTheme.bodySmall
                                      ?.copyWith(
                                        color: Colors.orange,
                                        fontWeight: FontWeight.bold,
                                      ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _weeklyStudyTime > 0
                          ? '${_formatMinutes(_weeklyStudyTime)} this week'
                          : 'Start learning today!',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppTheme.textSecondaryColor,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              _buildStatItem(
                context,
                Icons.check_circle,
                Colors.green,
                '$_completedLessons',
                'Completed',
              ),
              const SizedBox(width: 12),
              _buildStatItem(
                context,
                Icons.timer,
                Colors.blue,
                _formatMinutes(_weeklyStudyTime),
                'Study Time',
              ),
              const SizedBox(width: 12),
              _buildStatItem(
                context,
                Icons.whatshot,
                Colors.orange,
                '$_streakDays',
                'Day Streak',
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _formatMinutes(int minutes) {
    if (minutes < 60) return '${minutes}m';
    final hours = minutes ~/ 60;
    final mins = minutes % 60;
    if (mins == 0) return '${hours}h';
    return '${hours}h ${mins}m';
  }

  Widget _buildStatItem(
    BuildContext context,
    IconData icon,
    Color color,
    String value,
    String label,
  ) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
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
                color: AppTheme.textPrimaryColor,
              ),
            ),
            Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTheme.textSecondaryColor,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(
    BuildContext context,
    String title,
    IconData icon,
    Color color,
  ) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: color, size: 20),
        ),
        const SizedBox(width: 12),
        Text(
          title,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.bold,
            color: AppTheme.textPrimaryColor,
          ),
        ),
      ],
    );
  }

  Widget _buildTodaysLessons(BuildContext context) {
    return BlocBuilder<LessonsBloc, LessonsState>(
      builder: (context, state) {
        if (state is LessonsLoading) {
          return _buildLoadingCard();
        }

        if (state is LessonsError) {
          return _buildErrorCard(context, state.message);
        }

        if (state is LessonsLoaded) {
          final lessons = state.lessons;

          if (lessons.isEmpty) {
            return _buildEmptyLessonsCard(context);
          }

          return Column(
            children: lessons
                .take(5)
                .map(
                  (lesson) => Padding(
                    padding: const EdgeInsets.only(
                      bottom: AppConstants.paddingM,
                    ),
                    child: _LessonCard(lesson: lesson),
                  ),
                )
                .toList(),
          );
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildLoadingCard() {
    return Container(
      height: 120,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: AppTheme.primaryColor),
            const SizedBox(height: 12),
            Text(
              'Loading lessons...',
              style: TextStyle(color: AppTheme.textSecondaryColor),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorCard(BuildContext context, String message) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.red.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.red.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.error_outline, color: Colors.red),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Unable to load lessons',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Colors.red.shade700,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  message,
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: Colors.red.shade400),
                ),
              ],
            ),
          ),
          TextButton(
            onPressed: () => _lessonsBloc.add(LoadLessonsData()),
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyLessonsCard(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 20,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Icon(
              Icons.library_books_outlined,
              size: 48,
              color: AppTheme.primaryColor.withValues(alpha: 0.7),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'No lessons available yet',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimaryColor,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Complete the onboarding to generate your personalized lessons!',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTheme.textSecondaryColor,
            ),
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            onPressed: () => context.push('/onboarding'),
            icon: const Icon(Icons.rocket_launch),
            label: const Text('Get Started'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryColor,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickPracticeSection(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 20,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: _buildPracticeItem(
                  context,
                  'Speaking',
                  Icons.mic,
                  AppTheme.primaryColor,
                  () => _showQuickAIDialog(context),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildPracticeItem(
                  context,
                  'Writing',
                  Icons.edit,
                  AppTheme.secondaryColor,
                  () => _showQuickAIDialog(context),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _buildPracticeItem(
                  context,
                  'Vocabulary',
                  Icons.book,
                  Colors.purple,
                  () => context.push('/practice?type=vocabulary'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildPracticeItem(
                  context,
                  'Grammar',
                  Icons.spellcheck,
                  Colors.orange,
                  () => context.push('/practice?type=grammar'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPracticeItem(
    BuildContext context,
    String title,
    IconData icon,
    Color color,
    VoidCallback onTap,
  ) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              color.withValues(alpha: 0.1),
              color.withValues(alpha: 0.05),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: 0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Icon(icon, color: Colors.white, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                title,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: color.withValues(alpha: 0.9),
                ),
              ),
            ),
            Icon(
              Icons.arrow_forward_ios,
              size: 14,
              color: color.withValues(alpha: 0.5),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFAB(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: AppTheme.secondaryGradient,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppTheme.secondaryColor.withValues(alpha: 0.4),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: FloatingActionButton.extended(
        onPressed: () => _showQuickAIDialog(context),
        backgroundColor: Colors.transparent,
        elevation: 0,
        icon: const Icon(Icons.smart_toy_outlined, color: Colors.white),
        label: Text(
          'AI Practice',
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: Colors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  void _showQuickAIDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      backgroundColor: Colors.white,
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Icon(
                    Icons.smart_toy,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Text(
                  'Quick AI Practice',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimaryColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: _QuickPracticeButton(
                    icon: Icons.mic,
                    label: 'Speaking',
                    color: AppTheme.primaryColor,
                    onPressed: () {
                      Navigator.pop(context);
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (context) => AIConversationPage(
                            topic: ConversationTopic.dailyLife,
                          ),
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _QuickPracticeButton(
                    icon: Icons.edit,
                    label: 'Writing',
                    color: AppTheme.secondaryColor,
                    onPressed: () {
                      Navigator.pop(context);
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (context) =>
                              AIWritingPage(topic: ConversationTopic.dailyLife),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  void _showStudyPlanSettings(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      backgroundColor: Colors.white,
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.settings, color: AppTheme.primaryColor),
                ),
                const SizedBox(width: 12),
                Text(
                  'Study Settings',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimaryColor,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildSettingsItem(
              context,
              Icons.add_circle_outline,
              'Create New Study Plan',
              () => Navigator.pop(context),
            ),
            _buildSettingsItem(
              context,
              Icons.schedule,
              'Daily Study Reminders',
              () => Navigator.pop(context),
            ),
            _buildSettingsItem(
              context,
              Icons.analytics_outlined,
              'Progress Analytics',
              () {
                Navigator.pop(context);
                context.push('/progress');
              },
            ),
            _buildSettingsItem(
              context,
              Icons.help_outline,
              'Help & Support',
              () => Navigator.pop(context),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildSettingsItem(
    BuildContext context,
    IconData icon,
    String title,
    VoidCallback onTap,
  ) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppTheme.primaryColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, color: AppTheme.primaryColor, size: 20),
      ),
      title: Text(
        title,
        style: Theme.of(
          context,
        ).textTheme.bodyLarge?.copyWith(color: AppTheme.textPrimaryColor),
      ),
      trailing: const Icon(Icons.chevron_right, color: Colors.grey),
      onTap: onTap,
    );
  }
}

// Lesson Card Widget
class _LessonCard extends StatelessWidget {
  final Lesson lesson;

  const _LessonCard({required this.lesson});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) => LessonDetailPage(lesson: lesson),
        ),
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.05),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    _getLessonTypeColor(lesson.type),
                    _getLessonTypeColor(lesson.type).withValues(alpha: 0.7),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(14),
                boxShadow: [
                  BoxShadow(
                    color: _getLessonTypeColor(
                      lesson.type,
                    ).withValues(alpha: 0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Icon(
                _getLessonTypeIcon(lesson.type),
                color: Colors.white,
                size: 24,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          lesson.title,
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textPrimaryColor,
                              ),
                        ),
                      ),
                      if (lesson.isCompleted)
                        Container(
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(
                            color: Colors.green.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(
                            Icons.check_circle,
                            color: Colors.green,
                            size: 18,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    lesson.description,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondaryColor,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: _getLevelColor(
                            lesson.level,
                          ).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          lesson.level.name.toUpperCase(),
                          style: Theme.of(context).textTheme.labelSmall
                              ?.copyWith(
                                color: _getLevelColor(lesson.level),
                                fontWeight: FontWeight.bold,
                              ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Icon(
                        Icons.access_time,
                        size: 14,
                        color: AppTheme.textSecondaryColor,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        '${lesson.estimatedMinutes} min',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.textSecondaryColor,
                        ),
                      ),
                      const Spacer(),
                      Icon(
                        Icons.arrow_forward_ios,
                        size: 14,
                        color: AppTheme.textSecondaryColor.withValues(
                          alpha: 0.5,
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
    );
  }

  Color _getLessonTypeColor(LessonType type) {
    switch (type) {
      case LessonType.conversation:
        return const Color(0xFF4CAF50);
      case LessonType.writing:
        return const Color(0xFF2196F3);
      case LessonType.grammar:
        return const Color(0xFFFF9800);
      case LessonType.vocabulary:
        return const Color(0xFF9C27B0);
      case LessonType.pronunciation:
        return const Color(0xFFF44336);
      case LessonType.comprehension:
        return const Color(0xFF607D8B);
      case LessonType.mixed:
        return const Color(0xFF795548);
    }
  }

  IconData _getLessonTypeIcon(LessonType type) {
    switch (type) {
      case LessonType.conversation:
        return Icons.chat;
      case LessonType.writing:
        return Icons.edit;
      case LessonType.grammar:
        return Icons.spellcheck;
      case LessonType.vocabulary:
        return Icons.book;
      case LessonType.pronunciation:
        return Icons.record_voice_over;
      case LessonType.comprehension:
        return Icons.hearing;
      case LessonType.mixed:
        return Icons.extension;
    }
  }

  Color _getLevelColor(DifficultyLevel level) {
    switch (level) {
      case DifficultyLevel.a1:
      case DifficultyLevel.a2:
        return Colors.green;
      case DifficultyLevel.b1:
      case DifficultyLevel.b2:
        return Colors.orange;
      case DifficultyLevel.c1:
      case DifficultyLevel.c2:
        return Colors.red;
    }
  }
}

// Quick Practice Button
class _QuickPracticeButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onPressed;

  const _QuickPracticeButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [color, color.withValues(alpha: 0.8)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.3),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          children: [
            Icon(icon, color: Colors.white, size: 28),
            const SizedBox(height: 8),
            Text(
              label,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
