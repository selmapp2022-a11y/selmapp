import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../../core/theme/app_theme.dart';
import '../../data/models/exercise_models.dart';
import '../../data/repositories/practice_repository.dart';
import '../widgets/exercise_card_widget.dart';
import 'grammar_exercise_page.dart';
import 'vocabulary_exercise_page.dart';
import 'reading_exercise_page.dart';
import 'listening_exercise_page.dart';
import 'speaking_exercise_page.dart';
import 'writing_exercise_page.dart';

/// Direct skill practice page - loads exercises for a specific skill
/// and goes directly back to home (no Training Zone intermediate)
class DirectSkillPracticePage extends StatefulWidget {
  final String skillType;

  const DirectSkillPracticePage({
    super.key,
    required this.skillType,
  });

  @override
  State<DirectSkillPracticePage> createState() => _DirectSkillPracticePageState();
}

class _DirectSkillPracticePageState extends State<DirectSkillPracticePage>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late PracticeRepository _repository;
  
  List<Exercise> _exercises = [];
  bool _isLoading = true;
  String? _errorMessage;

  ExerciseType get _exerciseType {
    switch (widget.skillType.toLowerCase()) {
      case 'vocabulary':
        return ExerciseType.vocabulary;
      case 'grammar':
        return ExerciseType.grammar;
      case 'reading':
        return ExerciseType.reading;
      case 'listening':
        return ExerciseType.listening;
      case 'speaking':
        return ExerciseType.speaking;
      case 'writing':
        return ExerciseType.writing;
      default:
        return ExerciseType.vocabulary;
    }
  }

  @override
  void initState() {
    super.initState();
    _repository = PracticeRepositoryImpl(ApiClient(SecureStorage()));
    
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 600),
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
    _loadExercises();
  }

  Future<void> _loadExercises() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // Try to get ready content first
      final readyContent = await _repository.getReadyContent();
      
      if (!mounted) return;
      
      List<Exercise> exercises = [];
      
      if (readyContent.hasContent) {
        exercises = readyContent.getAllExercises()
            .where((e) => e.type == _exerciseType)
            .toList();
      }

      // For content-heavy skills (reading/listening/speaking), prefer micro-lessons when
      // ready content isn't available. This avoids low-quality placeholder text coming
      // from generic `/exercises/` records and keeps the experience fresh.
      final preferMicroLessonFirst = ['reading', 'listening', 'speaking']
          .contains(widget.skillType.toLowerCase());
      if (exercises.isEmpty && preferMicroLessonFirst) {
        final microLesson = await _repository.getMicroLesson(skillType: widget.skillType);

        if (!mounted) return;

        if (microLesson.hasExercises) {
          exercises = microLesson.toExercises(widget.skillType);
        }
      }
      
      // If no ready content, fetch from API
      if (exercises.isEmpty) {
        final exerciseData = await _repository.getExercises(
          exerciseType: widget.skillType,
          limit: 20,
        );
        
        if (!mounted) return;
        
        exercises = exerciseData
            .map((e) => e.toExercise())
            .where((e) => e.type == _exerciseType)
            .toList();
      }
      
      // If still no exercises, try micro-lesson
      if (exercises.isEmpty && !preferMicroLessonFirst) {
        final microLesson = await _repository.getMicroLesson(skillType: widget.skillType);
        
        if (!mounted) return;
        
        if (microLesson.hasExercises) {
          exercises = microLesson.toExercises(widget.skillType);
        }
      }

      // Listening: do NOT replace transcript-based exercises with a newly generated one
      // just to get audio. That causes the user to see one transcript while waiting,
      // then a different transcript once audio is available (even if questions look similar).
      //
      // If an exercise has no audio_url, the ListeningExercisePage will attempt to generate
      // TTS audio for the existing transcript so the text/questions remain stable.
      if (widget.skillType.toLowerCase() == 'listening' && exercises.isEmpty) {
        final generated = await _repository.generateListeningExercise(
          topic: 'Daily Conversation',
          contentType: 'conversation',
        );

        if (!mounted) return;

        if (generated != null) {
          exercises = [generated];
        }
      }

      // Deduplicate exercises based on title and description to avoid showing the same content
      final uniqueExercises = _deduplicateExercises(exercises);

      setState(() {
        _exercises = uniqueExercises;
        _isLoading = false;
      });
    } catch (e) {
      if (kDebugMode) {
        print('Error loading exercises: $e');
      }
      if (mounted) {
        setState(() {
          _errorMessage = 'Failed to load exercises. Please try again.';
          _isLoading = false;
        });
      }
    }
  }

  /// Deduplicates exercises based on their content
  List<Exercise> _deduplicateExercises(List<Exercise> exercises) {
    final seen = <String>{};
    final unique = <Exercise>[];
    final mergedGrammar = <String, GrammarExercise>{};
    
    for (final exercise in exercises) {
      // Merge grammar exercises with the same topic/title into ONE multi-question exercise.
      // This prevents the UI from showing the same grammar practice title multiple times.
      if (exercise is GrammarExercise) {
        final keySource = exercise.grammarRule.isNotEmpty ? exercise.grammarRule : exercise.title;
        final mergeKey = keySource.toLowerCase().trim();

        final existing = mergedGrammar[mergeKey];
        if (existing == null) {
          mergedGrammar[mergeKey] = exercise;
        } else {
          mergedGrammar[mergeKey] = _mergeGrammarExercises(existing, exercise);
        }
        continue;
      }

      // Create a unique key based on title and content
      final key = _getExerciseContentKey(exercise);
      
      if (!seen.contains(key)) {
        seen.add(key);
        unique.add(exercise);
      }
    }

    // Append merged grammar exercises (in insertion order).
    unique.addAll(mergedGrammar.values);
    return unique;
  }

  GrammarExercise _mergeGrammarExercises(GrammarExercise a, GrammarExercise b) {
    final combinedQuestions = <GrammarQuestion>[];
    final seenQ = <String>{};

    void addQuestions(List<GrammarQuestion> qs) {
      for (final q in qs) {
        final k = q.question.toLowerCase().trim();
        if (k.isEmpty) continue;
        if (seenQ.add(k)) combinedQuestions.add(q);
      }
    }

    addQuestions(a.questions);
    addQuestions(b.questions);

    final mergedTags = <String>{...a.tags, ...b.tags}.toList();
    final mergedRule = a.grammarRule.isNotEmpty ? a.grammarRule : b.grammarRule;
    final mergedExplanation =
        a.explanation.length >= b.explanation.length ? a.explanation : b.explanation;

    return GrammarExercise(
      id: a.id,
      title: a.title,
      description: a.description.isNotEmpty ? a.description : b.description,
      level: a.level,
      estimatedDurationMinutes: a.estimatedDurationMinutes >= b.estimatedDurationMinutes
          ? a.estimatedDurationMinutes
          : b.estimatedDurationMinutes,
      points: a.points + b.points,
      tags: mergedTags,
      grammarRule: mergedRule,
      explanation: mergedExplanation,
      questions: combinedQuestions,
    );
  }

  /// Generates a unique key for an exercise based on its content
  String _getExerciseContentKey(Exercise exercise) {
    // Use title + first part of description as key
    final titleKey = exercise.title.toLowerCase().trim();
    final descKey = exercise.description.toLowerCase().trim();
    
    // For more specific content, check type-specific fields
    String contentKey = '';
    if (exercise is GrammarExercise && exercise.questions.isNotEmpty) {
      contentKey = exercise.questions.first.question.toLowerCase();
    } else if (exercise is VocabularyExercise && exercise.words.isNotEmpty) {
      contentKey = exercise.words.first.word.toLowerCase();
    } else if (exercise is ReadingExercise) {
      contentKey = exercise.text.substring(0, exercise.text.length.clamp(0, 50)).toLowerCase();
    } else if (exercise is ListeningExercise) {
      contentKey = exercise.transcript.substring(0, exercise.transcript.length.clamp(0, 50)).toLowerCase();
    }
    
    return '$titleKey|$descKey|$contentKey';
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final skillData = _getSkillData(_exerciseType);

    return Scaffold(
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: CustomScrollView(
          slivers: [
            // Custom App Bar with Gradient and Back Button
            SliverAppBar(
              expandedHeight: 180,
              pinned: true,
              backgroundColor: skillData['primaryColor'] as Color,
              leading: IconButton(
                icon: const Icon(Icons.arrow_back, color: Colors.white),
                onPressed: () => context.go('/home'),
              ),
              flexibleSpace: FlexibleSpaceBar(
                title: Text(
                  '${skillData['name']} Practice',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
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
                        top: 60,
                        right: 20,
                        child: Icon(
                          skillData['icon'] as IconData,
                          size: 80,
                          color: Colors.white.withValues(alpha: 0.25),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // Content
            if (_isLoading)
              SliverFillRemaining(
                child: _buildLoadingState(skillData),
              )
            else if (_errorMessage != null)
              SliverFillRemaining(
                child: _buildErrorState(skillData),
              )
            else if (_exercises.isEmpty)
              SliverFillRemaining(
                child: _buildEmptyState(skillData),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.all(16),
                sliver: SliverList(
                  delegate: SliverChildListDelegate([
                    // Stats Card
                    _buildStatsCard(skillData),
                    const SizedBox(height: 20),
                    
                    // Tips Card
                    _buildTipsCard(skillData),
                    const SizedBox(height: 20),
                    
                    // Exercises Header
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Available Exercises',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                          decoration: BoxDecoration(
                            color: (skillData['primaryColor'] as Color).withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '${_exercises.length} exercises',
                            style: TextStyle(
                              color: skillData['primaryColor'] as Color,
                              fontWeight: FontWeight.w600,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    
                    // Exercise List
                    ..._exercises.map((exercise) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: ExerciseCardWidget(
                        exercise: exercise,
                        onTap: () => _startExercise(exercise),
                      ),
                    )),
                    
                    const SizedBox(height: 80),
                  ]),
                ),
              ),
          ],
        ),
      ),

      // Floating Action Button
      floatingActionButton: !_isLoading && _exercises.isNotEmpty
          ? FloatingActionButton.extended(
              onPressed: _startRandomExercise,
              backgroundColor: skillData['primaryColor'] as Color,
              icon: const Icon(Icons.play_arrow, color: Colors.white),
              label: const Text(
                'Start Random',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
              ),
            )
          : null,
    );
  }

  Widget _buildLoadingState(Map<String, dynamic> skillData) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: (skillData['primaryColor'] as Color).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: CircularProgressIndicator(
              color: skillData['primaryColor'] as Color,
              strokeWidth: 3,
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'Loading ${skillData['name']} exercises...',
            style: TextStyle(
              color: Colors.grey[600],
              fontSize: 16,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState(Map<String, dynamic> skillData) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(
                Icons.error_outline,
                size: 48,
                color: Colors.red,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              _errorMessage ?? 'Something went wrong',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.grey[700],
                fontSize: 16,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadExercises,
              icon: const Icon(Icons.refresh),
              label: const Text('Try Again'),
              style: ElevatedButton.styleFrom(
                backgroundColor: skillData['primaryColor'] as Color,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(Map<String, dynamic> skillData) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: (skillData['primaryColor'] as Color).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(
                skillData['icon'] as IconData,
                size: 48,
                color: (skillData['primaryColor'] as Color).withValues(alpha: 0.5),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'No ${skillData['name']} exercises available',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Check back later for new content!',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.grey[600],
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OutlinedButton.icon(
                  onPressed: _loadExercises,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh'),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: () => context.go('/home'),
                  icon: const Icon(Icons.home),
                  label: const Text('Go Home'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: skillData['primaryColor'] as Color,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatsCard(Map<String, dynamic> skillData) {
    final totalPoints = _exercises.fold<int>(0, (sum, e) => sum + e.points);
    final avgDuration = _exercises.isEmpty
        ? 0
        : (_exercises.fold<int>(0, (sum, e) => sum + e.estimatedDurationMinutes) / _exercises.length).round();

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
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _buildStatItem(
            Icons.quiz,
            '${_exercises.length}',
            'Exercises',
            skillData['primaryColor'] as Color,
          ),
          _buildStatItem(
            Icons.star,
            '$totalPoints',
            'Points',
            Colors.amber,
          ),
          _buildStatItem(
            Icons.timer,
            '~${avgDuration}m',
            'Each',
            Colors.blue,
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(IconData icon, String value, String label, Color color) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: color, size: 24),
        ),
        const SizedBox(height: 8),
        Text(
          value,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            fontSize: 18,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            color: Colors.grey[600],
            fontSize: 12,
          ),
        ),
      ],
    );
  }

  Widget _buildTipsCard(Map<String, dynamic> skillData) {
    final tips = skillData['tips'] as List<String>;
    final tip = tips[DateTime.now().second % tips.length];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            (skillData['primaryColor'] as Color).withValues(alpha: 0.1),
            (skillData['primaryColor'] as Color).withValues(alpha: 0.05),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: (skillData['primaryColor'] as Color).withValues(alpha: 0.2),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Text('💡', style: TextStyle(fontSize: 20)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Pro Tip',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: skillData['primaryColor'] as Color,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  tip,
                  style: TextStyle(
                    color: Colors.grey[700],
                    fontSize: 13,
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

  void _startRandomExercise() {
    if (_exercises.isNotEmpty) {
      final randomExercise = _exercises[
        DateTime.now().millisecondsSinceEpoch % _exercises.length
      ];
      _startExercise(randomExercise);
    }
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
      case ExerciseType.reading:
        exercisePage = ReadingExercisePage(exercise: exercise as ReadingExercise);
        break;
      case ExerciseType.listening:
        exercisePage = ListeningExercisePage(exercise: exercise as ListeningExercise);
        break;
      case ExerciseType.speaking:
        exercisePage = SpeakingExercisePage(exercise: exercise as SpeakingExercise);
        break;
      case ExerciseType.writing:
        exercisePage = WritingExercisePage(exercise: exercise as WritingExercise);
        break;
      default:
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${exercise.type.name} exercises coming soon!'),
            backgroundColor: Colors.orange,
          ),
        );
        return;
    }

    Navigator.of(context).push(
      MaterialPageRoute(builder: (context) => exercisePage),
    ).then((_) {
      // Refresh exercises after completing one
      if (mounted) {
        _loadExercises();
      }
    });
  }

  Map<String, dynamic> _getSkillData(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return {
          'name': 'Vocabulary',
          'description': 'Expand your word knowledge',
          'icon': Icons.menu_book,
          'colors': [const Color(0xFF9C27B0), const Color(0xFFE91E63)],
          'primaryColor': const Color(0xFF9C27B0),
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
          'description': 'Master English grammar rules',
          'icon': Icons.spellcheck,
          'colors': [const Color(0xFF2196F3), const Color(0xFF03DAC6)],
          'primaryColor': const Color(0xFF2196F3),
          'tips': [
            'Focus on one grammar rule at a time',
            'Practice with real-world examples',
            'Read your sentences aloud to check if they sound right',
            'Keep a grammar journal for common mistakes',
            'Apply grammar rules in your daily writing',
          ],
        };
      case ExerciseType.reading:
        return {
          'name': 'Reading',
          'description': 'Improve comprehension skills',
          'icon': Icons.article,
          'colors': [const Color(0xFF4CAF50), const Color(0xFF8BC34A)],
          'primaryColor': const Color(0xFF4CAF50),
          'tips': [
            'Read a variety of texts at your level',
            'Don\'t stop to look up every word',
            'Take notes while reading',
            'Summarize what you read in your own words',
            'Read regularly, even if just for 10 minutes',
          ],
        };
      case ExerciseType.listening:
        return {
          'name': 'Listening',
          'description': 'Train your ears for English',
          'icon': Icons.headphones,
          'colors': [const Color(0xFFFF9800), const Color(0xFFFFB74D)],
          'primaryColor': const Color(0xFFFF9800),
          'tips': [
            'Listen to English podcasts during commute',
            'Watch movies with English subtitles first',
            'Focus on understanding the main idea first',
            'Listen to the same content multiple times',
            'Practice with different accents',
          ],
        };
      case ExerciseType.speaking:
        return {
          'name': 'Speaking',
          'description': 'Build confidence in speaking',
          'icon': Icons.mic,
          'colors': [const Color(0xFFF44336), const Color(0xFFE57373)],
          'primaryColor': const Color(0xFFF44336),
          'tips': [
            'Practice speaking every day, even to yourself',
            'Record yourself and listen back',
            'Focus on communication, not perfection',
            'Learn common phrases and expressions',
            'Speak slowly and clearly at first',
          ],
        };
      case ExerciseType.writing:
        return {
          'name': 'Writing',
          'description': 'Express yourself in writing',
          'icon': Icons.edit,
          'colors': [const Color(0xFF009688), const Color(0xFF4DB6AC)],
          'primaryColor': const Color(0xFF009688),
          'tips': [
            'Write a little every day',
            'Start with simple sentences and build up',
            'Read your writing aloud to catch errors',
            'Keep a vocabulary journal for writing',
            'Get feedback on your writing when possible',
          ],
        };
      default:
        return {
          'name': 'Practice',
          'description': 'Improve your skills',
          'icon': Icons.school,
          'colors': [AppTheme.primaryColor, AppTheme.secondaryColor],
          'primaryColor': AppTheme.primaryColor,
          'tips': ['Practice regularly for best results'],
        };
    }
  }
}






