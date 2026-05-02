import 'package:flutter/material.dart';
import '../widgets/exercise_card_widget.dart';
import '../../data/models/exercise_models.dart';
import 'grammar_exercise_page.dart';
import 'vocabulary_exercise_page.dart';
import 'speaking_exercise_page.dart';
import 'writing_exercise_page.dart';

class SkillPracticePage extends StatefulWidget {
  final ExerciseType exerciseType;
  final List<Exercise> exercises;

  const SkillPracticePage({
    super.key,
    required this.exerciseType,
    required this.exercises,
  });

  @override
  State<SkillPracticePage> createState() => _SkillPracticePageState();
}

class _SkillPracticePageState extends State<SkillPracticePage>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    ));

    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final skillData = _getSkillData(widget.exerciseType);
    
    return Scaffold(
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: CustomScrollView(
          slivers: [
            // Custom App Bar with Gradient
            SliverAppBar(
              expandedHeight: 200,
              pinned: true,
              backgroundColor: skillData['primaryColor'] as Color,
              flexibleSpace: FlexibleSpaceBar(
                title: Text(
                  '${skillData['name']} Practice',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                background: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: skillData['colors'] as List<Color>,
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: Stack(
                    children: [
                      Positioned(
                        top: 80,
                        right: 20,
                        child: Icon(
                          skillData['icon'] as IconData,
                          size: 100,
                          color: Colors.white.withValues(alpha: 0.3),
                        ),
                      ),
                      Positioned(
                        bottom: 60,
                        left: 20,
                        right: 20,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              skillData['description'] as String,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 6,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(
                                '${widget.exercises.length} exercises available',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // Content
            SliverPadding(
              padding: const EdgeInsets.all(16),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  // Skill Overview Card
                  _buildSkillOverviewCard(skillData),
                  
                  const SizedBox(height: 24),
                  
                  // Learning Tips
                  _buildLearningTipsCard(skillData),
                  
                  const SizedBox(height: 24),
                  
                  // Exercises Section
                  Text(
                    'Practice Exercises',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: skillData['primaryColor'] as Color,
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Exercise List
                  ...widget.exercises.map((exercise) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: ExerciseCardWidget(
                      exercise: exercise,
                      onTap: () => _startExercise(exercise),
                    ),
                  )),
                  
                  const SizedBox(height: 24),
                  
                  // Progress Tracking
                  _buildProgressCard(skillData),
                  
                  const SizedBox(height: 80),
                ]),
              ),
            ),
          ],
        ),
      ),
      
      // Floating Action Button
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _startRandomExercise(),
        backgroundColor: skillData['primaryColor'] as Color,
        icon: const Icon(Icons.play_arrow, color: Colors.white),
        label: const Text(
          'Start Random',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }

  Widget _buildSkillOverviewCard(Map<String, dynamic> skillData) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  color: (skillData['primaryColor'] as Color).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(25),
                ),
                child: Icon(
                  skillData['icon'] as IconData,
                  color: skillData['primaryColor'] as Color,
                  size: 28,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Master ${skillData['name']}',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      'Build your ${skillData['name'].toString().toLowerCase()} skills step by step',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 20),
          
          // Stats Row
          Row(
            children: [
              Expanded(
                child: _buildStatItem(
                  'Exercises',
                  widget.exercises.length.toString(),
                  Icons.assignment,
                  Colors.blue,
                ),
              ),
              Expanded(
                child: _buildStatItem(
                  'Avg Duration',
                  '${_calculateAverageDuration()} min',
                  Icons.timer,
                  Colors.green,
                ),
              ),
              Expanded(
                child: _buildStatItem(
                  'Total Points',
                  _calculateTotalPoints().toString(),
                  Icons.stars,
                  Colors.amber,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 16,
              color: color,
            ),
          ),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[600],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLearningTipsCard(Map<String, dynamic> skillData) {
    final tips = skillData['tips'] as List<String>;
    
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            (skillData['primaryColor'] as Color).withValues(alpha: 0.1),
            (skillData['primaryColor'] as Color).withValues(alpha: 0.05),
          ],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: (skillData['primaryColor'] as Color).withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.lightbulb_outline,
                color: skillData['primaryColor'] as Color,
                size: 24,
              ),
              const SizedBox(width: 8),
              Text(
                'Learning Tips',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: skillData['primaryColor'] as Color,
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 16),
          
          ...tips.asMap().entries.map((entry) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  margin: const EdgeInsets.only(top: 8, right: 12),
                  decoration: BoxDecoration(
                    color: skillData['primaryColor'] as Color,
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
                Expanded(
                  child: Text(
                    entry.value,
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildProgressCard(Map<String, dynamic> skillData) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Your Progress',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          
          const SizedBox(height: 16),
          
          // Progress Bar
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${skillData['name']} Mastery',
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  Text(
                    '${skillData['progress']}%',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: skillData['primaryColor'] as Color,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              LinearProgressIndicator(
                value: (skillData['progress'] as int) / 100,
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(
                  skillData['primaryColor'] as Color,
                ),
                minHeight: 8,
              ),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // Achievement Badge
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: (skillData['primaryColor'] as Color).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.emoji_events,
                  color: skillData['primaryColor'] as Color,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  skillData['achievement'] as String,
                  style: TextStyle(
                    color: skillData['primaryColor'] as Color,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _startExercise(Exercise exercise) {
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
        exercisePage = ExerciseDetailPage(exercise: exercise);
        break;
    }
    
    Navigator.of(context).push(
      MaterialPageRoute(builder: (context) => exercisePage),
    );
  }

  void _startRandomExercise() {
    if (widget.exercises.isNotEmpty) {
      final randomExercise = widget.exercises[
        DateTime.now().millisecondsSinceEpoch % widget.exercises.length
      ];
      _startExercise(randomExercise);
    } else {
      // Show a message when no exercises are available
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('No exercises available yet. Please check back later!'),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
          action: SnackBarAction(
            label: 'OK',
            textColor: Colors.white,
            onPressed: () {},
          ),
        ),
      );
    }
  }

  int _calculateAverageDuration() {
    if (widget.exercises.isEmpty) return 0;
    final total = widget.exercises.fold<int>(
      0, 
      (sum, exercise) => sum + exercise.estimatedDurationMinutes,
    );
    return (total / widget.exercises.length).round();
  }

  int _calculateTotalPoints() {
    return widget.exercises.fold<int>(
      0,
      (sum, exercise) => sum + exercise.points,
    );
  }

  Map<String, dynamic> _getSkillData(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return {
          'name': 'Vocabulary',
          'description': 'Expand your word knowledge and improve comprehension',
          'icon': Icons.menu_book,
          'colors': [const Color(0xFF9C27B0), const Color(0xFFE91E63)],
          'primaryColor': const Color(0xFF9C27B0),
          'progress': 75,
          'achievement': 'Word Master - 500+ words learned!',
          'tips': [
            'Learn 10 new words daily and review them regularly',
            'Use new words in sentences to remember them better',
            'Group related words together (synonyms, antonyms)',
            'Practice with flashcards and spaced repetition',
            'Read diverse texts to encounter words in context',
          ],
        };
      case ExerciseType.grammar:
        return {
          'name': 'Grammar',
          'description': 'Master English grammar rules and structures',
          'icon': Icons.rule,
          'colors': [const Color(0xFF2196F3), const Color(0xFF03DAC6)],
          'primaryColor': const Color(0xFF2196F3),
          'progress': 68,
          'achievement': 'Grammar Expert - Perfect tense mastery!',
          'tips': [
            'Practice one grammar rule at a time until mastered',
            'Use grammar in real sentences, not just exercises',
            'Read grammar explanations and examples carefully',
            'Identify patterns in correct vs incorrect usage',
            'Apply new grammar rules in your writing practice',
          ],
        };
      case ExerciseType.reading:
        return {
          'name': 'Reading',
          'description': 'Enhance comprehension and reading speed',
          'icon': Icons.auto_stories,
          'colors': [const Color(0xFF4CAF50), const Color(0xFF8BC34A)],
          'primaryColor': const Color(0xFF4CAF50),
          'progress': 82,
          'achievement': 'Speed Reader - 300 WPM achieved!',
          'tips': [
            'Read diverse topics to expand vocabulary naturally',
            'Don\'t translate every word - focus on main ideas',
            'Practice skimming and scanning techniques',
            'Take notes of key points and new vocabulary',
            'Gradually increase reading difficulty level',
          ],
        };
      case ExerciseType.listening:
        return {
          'name': 'Listening',
          'description': 'Improve audio comprehension and pronunciation',
          'icon': Icons.headphones,
          'colors': [const Color(0xFFFF9800), const Color(0xFFFFC107)],
          'primaryColor': const Color(0xFFFF9800),
          'progress': 71,
          'achievement': 'Active Listener - Native speed comprehension!',
          'tips': [
            'Listen to various accents and speaking speeds',
            'Use subtitles initially, then remove them gradually',
            'Focus on key words and context clues',
            'Practice with podcasts, news, and conversations',
            'Repeat and shadow what you hear for better retention',
          ],
        };
      case ExerciseType.speaking:
        return {
          'name': 'Speaking',
          'description': 'Build confidence and fluency in spoken English',
          'icon': Icons.record_voice_over,
          'colors': [const Color(0xFFF44336), const Color(0xFFFF5722)],
          'primaryColor': const Color(0xFFF44336),
          'progress': 65,
          'achievement': 'Confident Speaker - Fluent conversations!',
          'tips': [
            'Practice speaking daily, even if just to yourself',
            'Record yourself and listen for improvement areas',
            'Focus on clear pronunciation over perfect grammar',
            'Use gestures and expressions to aid communication',
            'Join conversation groups or find speaking partners',
          ],
        };
      case ExerciseType.writing:
        return {
          'name': 'Writing',
          'description': 'Express ideas clearly in written English',
          'icon': Icons.edit,
          'colors': [const Color(0xFF607D8B), const Color(0xFF9E9E9E)],
          'primaryColor': const Color(0xFF607D8B),
          'progress': 73,
          'achievement': 'Skilled Writer - Clear and engaging texts!',
          'tips': [
            'Plan your writing with outlines and key points',
            'Write regularly to develop your natural style',
            'Read your work aloud to check flow and clarity',
            'Use varied sentence structures and vocabulary',
            'Edit and revise for grammar, clarity, and impact',
          ],
        };
      case ExerciseType.conversation:
        return {
          'name': 'Conversation',
          'description': 'Master natural dialogue and social interaction',
          'icon': Icons.chat,
          'colors': [const Color(0xFF795548), const Color(0xFFBCAAA4)],
          'primaryColor': const Color(0xFF795548),
          'progress': 70,
          'achievement': 'Social Butterfly - Natural conversations!',
          'tips': [
            'Practice common conversation starters and responses',
            'Learn to ask follow-up questions to keep talks flowing',
            'Study cultural context and appropriate expressions',
            'Practice active listening and responding naturally',
            'Use body language and tone to enhance communication',
          ],
        };
    }
  }
}

// Placeholder for Exercise Detail Page
class ExerciseDetailPage extends StatelessWidget {
  final Exercise exercise;

  const ExerciseDetailPage({super.key, required this.exercise});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(exercise.title),
        backgroundColor: const Color(0xFF2196F3),
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.construction,
              size: 64,
              color: Colors.grey[400],
            ),
            const SizedBox(height: 16),
            Text(
              'Exercise Details',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Individual exercise pages coming soon!',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Back to Practice'),
            ),
          ],
        ),
      ),
    );
  }
}
