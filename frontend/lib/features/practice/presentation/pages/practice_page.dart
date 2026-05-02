import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../bloc/practice_bloc.dart';
import '../../data/models/exercise_models.dart';
import '../../data/repositories/practice_repository.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../../core/widgets/ai_coach_widget.dart';
import 'skill_practice_page.dart';
import 'learning_session_detail_page.dart';
import 'grammar_exercise_page.dart';
import 'vocabulary_exercise_page.dart';
import 'speaking_exercise_page.dart';
import 'writing_exercise_page.dart';

class PracticePage extends StatefulWidget {
  /// Optional initial skill type to filter content (e.g., 'vocabulary', 'grammar', 'listening', 'speaking')
  final String? initialSkillType;
  
  const PracticePage({super.key, this.initialSkillType});

  @override
  State<PracticePage> createState() => _PracticePageState();
}

class _PracticePageState extends State<PracticePage>
    with TickerProviderStateMixin {
  late TabController _tabController;
  late PracticeBloc _practiceBloc;
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    
    _animationController = AnimationController(
      duration: AppConstants.longAnimation,
      vsync: this,
    );
    
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );
    
    _animationController.forward();
    
    final practiceRepository = PracticeRepositoryImpl(ApiClient(SecureStorage()));
    _practiceBloc = PracticeBloc(practiceRepository);
    _practiceBloc.add(LoadPracticeData());
    
    // If an initial skill type is provided, navigate to Skills tab and then to that skill
    if (widget.initialSkillType != null) {
      // Set tab to Skills (index 1) after the widget is built
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _tabController.animateTo(1); // Go to Skills tab
        // Navigate to the specific skill after a short delay to let the tab switch
        Future.delayed(const Duration(milliseconds: 100), () {
          if (mounted) {
            final skillType = _mapSkillTypeToExerciseType(widget.initialSkillType!);
            if (skillType != null) {
              _navigateToSkillPractice(skillType);
            }
          }
        });
      });
    }
  }
  
  ExerciseType? _mapSkillTypeToExerciseType(String skillType) {
    switch (skillType.toLowerCase()) {
      case 'vocabulary':
        return ExerciseType.vocabulary;
      case 'grammar':
        return ExerciseType.grammar;
      case 'listening':
        return ExerciseType.listening;
      case 'speaking':
        return ExerciseType.speaking;
      case 'reading':
        return ExerciseType.reading;
      case 'writing':
        return ExerciseType.writing;
      default:
        return null;
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    _animationController.dispose();
    _practiceBloc.close();
    super.dispose();
  }

  BoxDecoration _buildBackgroundDecoration() {
    return const BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color(0xFF1a1a2e),
          Color(0xFF16213e),
          Color(0xFF0f3460),
        ],
        stops: [0.0, 0.5, 1.0],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider<PracticeBloc>.value(
      value: _practiceBloc,
      child: Scaffold(
        body: Container(
          decoration: _buildBackgroundDecoration(),
          child: SafeArea(
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: NestedScrollView(
                headerSliverBuilder: (context, innerBoxIsScrolled) {
                  return [
                    _buildAppBar(context),
                    SliverToBoxAdapter(
                      child: BlocBuilder<PracticeBloc, PracticeState>(
                        builder: (context, state) {
                          if (state is PracticeLoaded) {
                            return Column(
                              children: [
                                _buildProgressHeader(context, state),
                                _buildAITrainerCard(context, state),
                              ],
                            );
                          }
                          return const SizedBox(height: 20);
                        },
                      ),
                    ),
                    SliverPersistentHeader(
                      pinned: true,
                      delegate: _SliverTabBarDelegate(
                        TabBar(
                          controller: _tabController,
                          indicator: BoxDecoration(
                            borderRadius: BorderRadius.circular(25),
                            gradient: AppTheme.primaryGradient,
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.primaryColor.withValues(alpha: 0.4),
                                blurRadius: 8,
                                offset: const Offset(0, 2),
                              ),
                            ],
                          ),
                          labelColor: Colors.white,
                          unselectedLabelColor: Colors.white.withValues(alpha: 0.6),
                          labelStyle: const TextStyle(fontWeight: FontWeight.w600),
                          tabs: const [
                            Tab(text: 'Sessions'),
                            Tab(text: 'Skills'),
                            Tab(text: 'Exercises'),
                          ],
                        ),
                      ),
                    ),
                  ];
                },
                body: BlocBuilder<PracticeBloc, PracticeState>(
                  builder: (context, state) {
                    if (state is PracticeLoading) {
                      return _buildLoadingState();
                    }

                    if (state is PracticeError) {
                      return _buildErrorState(context, state.message);
                    }

                    if (state is PracticeLoaded) {
                      return TabBarView(
                        controller: _tabController,
                        children: [
                          _buildSessionsTab(context, state.learningSessions),
                          _buildSkillsTab(context),
                          _buildExercisesTab(context, state.exercises),
                        ],
                      );
                    }

                    return _buildEmptyState(context);
                  },
                ),
              ),
            ),
          ),
        ),
        // No bottom nav on practice page - it's a drill-down from Home
      ),
    );
  }

  Widget _buildAppBar(BuildContext context) {
    return SliverAppBar(
      expandedHeight: 140,
      floating: true,
      pinned: false,
      backgroundColor: Colors.transparent,
      elevation: 0,
      leading: Padding(
        padding: const EdgeInsets.only(left: 8),
        child: _GlassIconButton(
          icon: Icons.arrow_back,
          onPressed: () => context.go('/home'),
        ),
      ),
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
                        Container(
                          width: 56,
                          height: 56,
                          decoration: BoxDecoration(
                            gradient: AppTheme.primaryGradient,
                            borderRadius: BorderRadius.circular(18),
                            border: Border.all(
                              color: Colors.white.withValues(alpha: 0.3),
                              width: 2,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.primaryColor.withValues(alpha: 0.4),
                                blurRadius: 16,
                                offset: const Offset(0, 6),
                              ),
                            ],
                          ),
                          child: const Center(
                            child: Text('💪', style: TextStyle(fontSize: 28)),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    'Training Zone',
                                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      gradient: const LinearGradient(colors: [Colors.orange, Colors.deepOrange]),
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: const Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.local_fire_department, color: Colors.white, size: 12),
                                        SizedBox(width: 2),
                                        Text(
                                          'LIVE',
                                          style: TextStyle(
                                            color: Colors.white,
                                            fontSize: 9,
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
                                '${AppConstants.coachDisplayName} is ready to train with you!',
                                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                  color: Colors.white.withValues(alpha: 0.8),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  _GlassIconButton(
                    icon: Icons.settings_outlined,
                    onPressed: () => _showSettingsBottomSheet(context),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildProgressHeader(BuildContext context, PracticeLoaded state) {
    final progress = state.userProgress;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppConstants.paddingM),
      child: Row(
        children: [
          Expanded(
            child: _StatCard(
              icon: Icons.star,
              iconColor: Colors.amber,
              value: '${progress.totalPoints}',
              label: 'Points',
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _StatCard(
              icon: Icons.local_fire_department,
              iconColor: Colors.deepOrange,
              value: '${progress.streakDays}',
              label: 'Streak',
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _StatCard(
              icon: Icons.school,
              iconColor: AppTheme.primaryColor,
              value: progress.currentLevel.name.toUpperCase(),
              label: 'Level',
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _StatCard(
              icon: Icons.check_circle,
              iconColor: Colors.green,
              value: '${progress.completedExercises.length}',
              label: 'Done',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAITrainerCard(BuildContext context, PracticeLoaded state) {
    final message = state.currentTrainerMessage;
    
    // Map message type to coach mood
    final mood = _getCoachMood(message.type);
    final coachMessage = CoachMessages.getSessionStart();
    
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppConstants.paddingM),
      child: AICoachWidget(
        message: coachMessage,
        mood: mood,
        compact: true,
        showPulse: true,
        onTap: () => _showTrainerChat(context),
      ),
    );
  }
  
  CoachMood _getCoachMood(AITrainerMessageType type) {
    switch (type) {
      case AITrainerMessageType.welcome:
        return CoachMood.friendly;
      case AITrainerMessageType.encouragement:
        return CoachMood.encouraging;
      case AITrainerMessageType.correction:
        return CoachMood.coaching;
      case AITrainerMessageType.feedback:
        return CoachMood.coaching;
      case AITrainerMessageType.celebration:
        return CoachMood.celebrating;
      case AITrainerMessageType.instruction:
        return CoachMood.focused;
      case AITrainerMessageType.question:
        return CoachMood.friendly;
    }
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
            'Loading exercises...',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.8),
              fontSize: 16,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState(BuildContext context, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
            ),
            const SizedBox(height: 24),
            Text(
              'Something went wrong',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.white.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => _practiceBloc.add(LoadPracticeData()),
              icon: const Icon(Icons.refresh),
              label: const Text('Try Again'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Icon(
                Icons.fitness_center,
                size: 56,
                color: Colors.white.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Ready to practice?',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Start exercising to improve your skills!',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.white.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => _practiceBloc.add(LoadPracticeData()),
              icon: const Icon(Icons.play_arrow),
              label: const Text('Get Started'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSessionsTab(BuildContext context, List<LearningSession> sessions) {
    if (sessions.isEmpty) {
      return _buildEmptyTabContent(
        context,
        Icons.school_outlined,
        'No sessions available',
        'Complete exercises to unlock learning sessions',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(AppConstants.paddingM),
      itemCount: sessions.length,
      itemBuilder: (context, index) {
        final session = sessions[index];
        return _SessionCard(
          session: session,
          onTap: () => _startLearningSession(session),
        );
      },
    );
  }

  Widget _buildSkillsTab(BuildContext context) {
    final skills = [
      _SkillItem(ExerciseType.vocabulary, 'Vocabulary', Icons.menu_book, Colors.purple),
      _SkillItem(ExerciseType.grammar, 'Grammar', Icons.spellcheck, Colors.blue),
      _SkillItem(ExerciseType.reading, 'Reading', Icons.article, Colors.green),
      _SkillItem(ExerciseType.listening, 'Listening', Icons.headphones, Colors.orange),
      _SkillItem(ExerciseType.speaking, 'Speaking', Icons.mic, Colors.red),
      _SkillItem(ExerciseType.writing, 'Writing', Icons.edit, Colors.teal),
    ];

    return Padding(
      padding: const EdgeInsets.all(AppConstants.paddingM),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Choose a skill to practice',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: GridView.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 1.3,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
              ),
              itemCount: skills.length,
              itemBuilder: (context, index) {
                final skill = skills[index];
                return _SkillCard(
                  skill: skill,
                  onTap: () => _navigateToSkillPractice(skill.type),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExercisesTab(BuildContext context, List<Exercise> exercises) {
    if (exercises.isEmpty) {
      return _buildEmptyTabContent(
        context,
        Icons.quiz_outlined,
        'No exercises available',
        'Check back later for new exercises',
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(AppConstants.paddingM),
      itemCount: exercises.length,
      itemBuilder: (context, index) {
        final exercise = exercises[index];
        return _ExerciseCard(
          exercise: exercise,
          onTap: () => _startExercise(exercise),
        );
      },
    );
  }

  Widget _buildEmptyTabContent(BuildContext context, IconData icon, String title, String subtitle) {
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
            child: Icon(icon, size: 48, color: Colors.white.withValues(alpha: 0.6)),
          ),
          const SizedBox(height: 20),
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Colors.white.withValues(alpha: 0.7),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _startLearningSession(LearningSession session) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => LearningSessionDetailPage(session: session),
      ),
    );

    if (!mounted) return;
    _practiceBloc.add(LoadPracticeData());
  }

  Future<void> _navigateToSkillPractice(ExerciseType exerciseType) async {
    final state = _practiceBloc.state;
    List<Exercise> exercises = [];
    
    if (state is PracticeLoaded) {
      exercises = state.exercises.where((e) => e.type == exerciseType).toList();
    }
    
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => SkillPracticePage(
          exerciseType: exerciseType,
          exercises: exercises,
        ),
      ),
    );

    if (!mounted) return;
    _practiceBloc.add(LoadPracticeData());
  }

  Future<void> _startExercise(Exercise exercise) async {
    Widget exercisePage;
    
    switch (exercise.type) {
      case ExerciseType.vocabulary:
        exercisePage = VocabularyExercisePage(exercise: exercise as VocabularyExercise);
        break;
      case ExerciseType.grammar:
        exercisePage = GrammarExercisePage(exercise: exercise as GrammarExercise);
        break;
      case ExerciseType.speaking:
        exercisePage = SpeakingExercisePage(exercise: exercise as SpeakingExercise);
        break;
      case ExerciseType.writing:
        exercisePage = WritingExercisePage(exercise: exercise as WritingExercise);
        break;
      default:
        exercisePage = _GenericExercisePage(exercise: exercise);
        break;
    }
    
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (context) => exercisePage),
    );

    if (!mounted) return;
    _practiceBloc.add(LoadPracticeData());
  }

  void _showTrainerChat(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => const _AITrainerChatSheet(),
    );
  }

  void _showSettingsBottomSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      backgroundColor: const Color(0xFF1a1a2e),
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryColor.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(Icons.settings, color: AppTheme.primaryColor),
                ),
                const SizedBox(width: 14),
                Text(
                  'Practice Settings',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            _buildSettingsItem(context, Icons.volume_up, 'Audio Settings'),
            _buildSettingsItem(context, Icons.notifications, 'Reminder Settings'),
            _buildSettingsItem(context, Icons.speed, 'Difficulty Level'),
            _buildSettingsItem(context, Icons.help, 'Help & Support'),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildSettingsItem(BuildContext context, IconData icon, String title) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, color: Colors.white.withValues(alpha: 0.8), size: 20),
      ),
      title: Text(
        title,
        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
          color: Colors.white,
        ),
      ),
      trailing: Icon(Icons.chevron_right, color: Colors.white.withValues(alpha: 0.5)),
      onTap: () {},
    );
  }
}

// Skill Item Model
class _SkillItem {
  final ExerciseType type;
  final String name;
  final IconData icon;
  final Color color;

  _SkillItem(this.type, this.name, this.icon, this.color);
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
      borderRadius: BorderRadius.circular(14),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
          ),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: iconColor.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: iconColor, size: 18),
              ),
              const SizedBox(height: 6),
              Text(
                value,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.white.withValues(alpha: 0.7),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Session Card
class _SessionCard extends StatelessWidget {
  final LearningSession session;
  final VoidCallback onTap;

  const _SessionCard({required this.session, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GestureDetector(
        onTap: onTap,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.white.withValues(alpha: 0.15),
                    Colors.white.withValues(alpha: 0.05),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      borderRadius: BorderRadius.circular(14),
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.primaryColor.withValues(alpha: 0.4),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: const Icon(Icons.play_arrow, color: Colors.white, size: 24),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          session.title,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(Icons.timer_outlined, size: 14, color: Colors.white.withValues(alpha: 0.7)),
                            const SizedBox(width: 4),
                            Text(
                              '${session.totalDurationMinutes} min',
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Colors.white.withValues(alpha: 0.7),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Icon(Icons.star_outline, size: 14, color: Colors.amber),
                            const SizedBox(width: 4),
                            Text(
                              '${session.totalPoints} pts',
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Colors.amber,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Icon(Icons.arrow_forward_ios, size: 16, color: Colors.white.withValues(alpha: 0.5)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// Skill Card
class _SkillCard extends StatelessWidget {
  final _SkillItem skill;
  final VoidCallback onTap;

  const _SkillCard({required this.skill, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  skill.color.withValues(alpha: 0.4),
                  skill.color.withValues(alpha: 0.2),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: skill.color.withValues(alpha: 0.3)),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(14),
                    boxShadow: [
                      BoxShadow(
                        color: skill.color.withValues(alpha: 0.3),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Icon(skill.icon, color: Colors.white, size: 26),
                ),
                const SizedBox(height: 12),
                Text(
                  skill.name,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// Exercise Card
class _ExerciseCard extends StatelessWidget {
  final Exercise exercise;
  final VoidCallback onTap;

  const _ExerciseCard({required this.exercise, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GestureDetector(
        onTap: onTap,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.white.withValues(alpha: 0.15),
                    Colors.white.withValues(alpha: 0.05),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _getTypeColor(exercise.type).withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(_getTypeIcon(exercise.type), color: _getTypeColor(exercise.type), size: 22),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          exercise.title,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: _getLevelColor(exercise.level).withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                exercise.level.name.toUpperCase(),
                                style: TextStyle(
                                  color: _getLevelColor(exercise.level),
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Icon(Icons.star, size: 12, color: Colors.amber),
                            const SizedBox(width: 2),
                            Text(
                              '${exercise.points}',
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Colors.white.withValues(alpha: 0.7),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Icon(Icons.play_circle, color: AppTheme.primaryColor, size: 28),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Color _getTypeColor(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary: return Colors.purple;
      case ExerciseType.grammar: return Colors.blue;
      case ExerciseType.reading: return Colors.green;
      case ExerciseType.listening: return Colors.orange;
      case ExerciseType.speaking: return Colors.red;
      case ExerciseType.writing: return Colors.teal;
      case ExerciseType.conversation: return Colors.indigo;
    }
  }

  IconData _getTypeIcon(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary: return Icons.menu_book;
      case ExerciseType.grammar: return Icons.spellcheck;
      case ExerciseType.reading: return Icons.article;
      case ExerciseType.listening: return Icons.headphones;
      case ExerciseType.speaking: return Icons.mic;
      case ExerciseType.writing: return Icons.edit;
      case ExerciseType.conversation: return Icons.chat;
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

// Generic Exercise Page
class _GenericExercisePage extends StatelessWidget {
  final Exercise exercise;

  const _GenericExercisePage({required this.exercise});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFF1a1a2e),
              Color(0xFF16213e),
              Color(0xFF0f3460),
            ],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // App Bar
              Padding(
                padding: const EdgeInsets.all(AppConstants.paddingM),
                child: Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: BackdropFilter(
                        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                        child: Container(
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
                          ),
                          child: IconButton(
                            onPressed: () => Navigator.pop(context),
                            icon: const Icon(Icons.arrow_back, color: Colors.white),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Text(
                        exercise.title,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
              // Content
              Expanded(
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
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
                            Icons.construction,
                            size: 56,
                            color: Colors.white.withValues(alpha: 0.7),
                          ),
                        ),
                        const SizedBox(height: 24),
                        Text(
                          exercise.title,
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'This exercise type is coming soon!',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Colors.white.withValues(alpha: 0.7),
                          ),
                        ),
                        const SizedBox(height: 32),
                        ElevatedButton.icon(
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.arrow_back),
                          label: const Text('Go Back'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.primaryColor,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// AI Trainer Chat Sheet
class _AITrainerChatSheet extends StatelessWidget {
  const _AITrainerChatSheet();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.75,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF1a1a2e),
            Color(0xFF16213e),
            Color(0xFF0f3460),
          ],
        ),
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
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
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primaryColor.withValues(alpha: 0.4),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Icon(Icons.smart_toy, color: Colors.white, size: 28),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'AI English Trainer',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'Your personal learning assistant',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.9),
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text(
                    'Online',
                    style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: Center(
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
                      Icons.chat_bubble_outline,
                      size: 48,
                      color: Colors.white.withValues(alpha: 0.6),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'AI Chat Coming Soon!',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 40),
                    child: Text(
                      'Get personalized tips and feedback from your AI trainer',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.7),
                      ),
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
}

// Sliver Tab Bar Delegate
class _SliverTabBarDelegate extends SliverPersistentHeaderDelegate {
  final TabBar _tabBar;

  _SliverTabBarDelegate(this._tabBar);

  @override
  double get minExtent => _tabBar.preferredSize.height + 20;

  @override
  double get maxExtent => _tabBar.preferredSize.height + 20;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return Container(
      color: const Color(0xFF16213e),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(25),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(25),
              border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
            ),
            child: _tabBar,
          ),
        ),
      ),
    );
  }

  @override
  bool shouldRebuild(_SliverTabBarDelegate oldDelegate) => false;
}
