import 'dart:async';

import 'package:flutter/material.dart';


import '../../data/models/exercise_models.dart';
import 'grammar_exercise_page.dart';
import 'speaking_exercise_page.dart';
import 'vocabulary_exercise_page.dart';
import 'writing_exercise_page.dart';

class LearningSessionDetailPage extends StatefulWidget {
  final LearningSession session;

  const LearningSessionDetailPage({super.key, required this.session});

  @override
  State<LearningSessionDetailPage> createState() =>
      _LearningSessionDetailPageState();
}

class _LearningSessionDetailPageState extends State<LearningSessionDetailPage>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;

  int currentExerciseIndex = 0;
  bool sessionStarted = false;
  final Set<int> _completedExerciseIndices = <int>{};
  final Map<int, int> _earnedPointsByIndex = <int, int>{};
  final Map<int, double> _accuracyByIndex = <int, double>{};

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: CustomScrollView(
          slivers: [
            // Custom App Bar
            SliverAppBar(
              expandedHeight: 250,
              pinned: true,
              backgroundColor: const Color(0xFF2196F3),
              flexibleSpace: FlexibleSpaceBar(
                title: Text(
                  widget.session.title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                background: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: _getLevelGradient(widget.session.level),
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: Stack(
                    children: [
                      // Background Pattern
                      Positioned(
                        top: 60,
                        right: -20,
                        child: Icon(
                          Icons.school,
                          size: 120,
                          color: Colors.white.withValues(alpha: 0.1),
                        ),
                      ),

                      // Session Info
                      Positioned(
                        bottom: 60,
                        left: 20,
                        right: 20,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
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
                                'Level ${widget.session.level.name.toUpperCase()}',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                            Row(
                              children: [
                                _buildSessionStat(
                                  Icons.timer,
                                  '${widget.session.totalDurationMinutes} min',
                                ),
                                const SizedBox(width: 16),
                                _buildSessionStat(
                                  Icons.stars,
                                  '${widget.session.totalPoints} pts',
                                ),
                                const SizedBox(width: 16),
                                _buildSessionStat(
                                  Icons.assignment,
                                  '${widget.session.exercises.length} exercises',
                                ),
                              ],
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
                  // AI Trainer Introduction
                  if (widget.session.trainerIntroduction != null)
                    _buildTrainerIntroCard(),

                  const SizedBox(height: 20),

                  // Session Progress
                  _buildProgressCard(),

                  const SizedBox(height: 20),

                  // Focus Areas
                  _buildFocusAreasCard(),

                  const SizedBox(height: 20),

                  // Exercises Section
                  Text(
                    'Session Exercises',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: const Color(0xFF2196F3),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Exercise List
                  ...widget.session.exercises.asMap().entries.map((entry) {
                    final index = entry.key;
                    final exercise = entry.value;
                    final isActive = sessionStarted && index == currentExerciseIndex;
                    final isCompleted = _completedExerciseIndices.contains(index);

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: GestureDetector(
                        onTap: sessionStarted ? () => _openExercise(index) : null,
                        child: _buildSessionExerciseCard(
                          exercise,
                          index + 1,
                          isActive,
                          isCompleted,
                        ),
                      ),
                    );
                  }),

                  const SizedBox(height: 20),

                  // Learning Tips
                  _buildLearningTipsCard(),

                  const SizedBox(height: 80),
                ]),
              ),
            ),
          ],
        ),
      ),

      // Bottom Action Bar
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: SafeArea(
          child: sessionStarted ? _buildSessionControls() : _buildStartButton(),
        ),
      ),
    );
  }

  Widget _buildSessionStat(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: Colors.white, size: 16),
        const SizedBox(width: 4),
        Text(
          text,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildTrainerIntroCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF2196F3), Color(0xFF21CBF3)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF2196F3).withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 50,
            height: 50,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(25),
            ),
            child: const Icon(Icons.smart_toy, color: Colors.white, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'AI Trainer Message',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  widget.session.trainerIntroduction!.message,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
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

  Widget _buildProgressCard() {
    final total = widget.session.exercises.length;
    final completed = _completedExerciseIndices.length;
    final progress = (sessionStarted && total > 0) ? completed / total : 0.0;

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
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Session Progress',
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              Text(
                sessionStarted
                    ? '$completed/$total'
                    : '0/$total',
                style: const TextStyle(
                  color: Color(0xFF2196F3),
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          LinearProgressIndicator(
            value: progress,
            backgroundColor: Colors.grey[200],
            valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF2196F3)),
            minHeight: 8,
          ),

          const SizedBox(height: 12),

          Text(
            sessionStarted
                ? completed == total
                      ? 'Session completed! Great work! 🎉'
                      : 'Keep going! You\'re doing great!'
                : 'Ready to start your learning journey?',
            style: TextStyle(color: Colors.grey[600], fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildFocusAreasCard() {
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
              Icon(
                Icons.center_focus_strong,
                color: const Color(0xFF2196F3),
                size: 24,
              ),
              const SizedBox(width: 8),
              Text(
                'Focus Areas',
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
            ],
          ),

          const SizedBox(height: 16),

          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: widget.session.focusAreas.map((area) {
              return Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFF2196F3).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: const Color(0xFF2196F3).withValues(alpha: 0.3),
                  ),
                ),
                child: Text(
                  area.toUpperCase(),
                  style: const TextStyle(
                    color: Color(0xFF2196F3),
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildSessionExerciseCard(
    Exercise exercise,
    int number,
    bool isActive,
    bool isCompleted,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: isActive
            ? const Color(0xFF2196F3).withValues(alpha: 0.1)
            : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isActive
              ? const Color(0xFF2196F3)
              : isCompleted
              ? Colors.green
              : Colors.grey[200]!,
          width: isActive || isCompleted ? 2 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            // Exercise Number/Status
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: isCompleted
                    ? Colors.green
                    : isActive
                    ? const Color(0xFF2196F3)
                    : Colors.grey[300],
                borderRadius: BorderRadius.circular(20),
              ),
              child: Center(
                child: isCompleted
                    ? const Icon(Icons.check, color: Colors.white, size: 20)
                    : Text(
                        number.toString(),
                        style: TextStyle(
                          color: isActive || isCompleted
                              ? Colors.white
                              : Colors.grey[600],
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ),

            const SizedBox(width: 16),

            // Exercise Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    exercise.title,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: isActive
                          ? const Color(0xFF2196F3)
                          : Colors.black87,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    exercise.description,
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Icon(
                        _getExerciseIcon(exercise.type),
                        size: 16,
                        color: _getExerciseColor(exercise.type),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        exercise.type.name.toUpperCase(),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: _getExerciseColor(exercise.type),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Icon(Icons.schedule, size: 16, color: Colors.grey[500]),
                      const SizedBox(width: 4),
                      Text(
                        '${exercise.estimatedDurationMinutes} min',
                        style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            // Status Indicator
            if (isActive)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF2196F3),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Text(
                  'CURRENT',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildLearningTipsCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.amber.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.amber.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.lightbulb_outline, color: Colors.amber[700], size: 24),
              const SizedBox(width: 8),
              Text(
                'Session Tips',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.amber[700],
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          ...[
            'Take breaks between exercises to stay focused',
            'Don\'t worry about making mistakes - they help you learn!',
            'Try to complete all exercises in one session for best results',
            'Review your answers and learn from any corrections',
          ].map(
            (tip) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    margin: const EdgeInsets.only(top: 8, right: 12),
                    decoration: BoxDecoration(
                      color: Colors.amber[700],
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      tip,
                      style: const TextStyle(fontSize: 14, height: 1.4),
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

  Widget _buildStartButton() {
    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton(
        onPressed: _startSession,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF2196F3),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(25),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.play_arrow, size: 24),
            const SizedBox(width: 8),
            Text(
              'Start Session',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSessionControls() {
    final isSessionComplete =
        _completedExerciseIndices.length >= widget.session.exercises.length;

    return Row(
      children: [
        if (currentExerciseIndex > 0)
          Expanded(
            child: OutlinedButton(
              onPressed: _previousExercise,
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFF2196F3),
                side: const BorderSide(color: Color(0xFF2196F3)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(25),
                ),
              ),
              child: const Text('Previous'),
            ),
          ),

        if (currentExerciseIndex > 0) const SizedBox(width: 16),

        Expanded(
          flex: 2,
          child: ElevatedButton(
            onPressed: isSessionComplete ? _completeSession : _nextExercise,
            style: ElevatedButton.styleFrom(
              backgroundColor: isSessionComplete
                  ? Colors.green
                  : const Color(0xFF2196F3),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(25),
              ),
            ),
            child: Text(
              isSessionComplete ? 'Complete Session' : 'Start Exercise',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ),
      ],
    );
  }

  void _startSession() {
    setState(() {
      sessionStarted = true;
      currentExerciseIndex = 0;
      _completedExerciseIndices.clear();
      _earnedPointsByIndex.clear();
      _accuracyByIndex.clear();
    });

    // Open first exercise immediately for a real practice flow.
    unawaited(_openExercise(0));
  }

  Future<void> _nextExercise() async {
    await _openExercise(currentExerciseIndex);
  }

  void _previousExercise() {
    if (currentExerciseIndex > 0) {
      setState(() {
        currentExerciseIndex--;
      });
    }
  }

  Future<void> _completeSession() async {
    final total = widget.session.exercises.length;
    final completed = _completedExerciseIndices.length;
    final pointsEarned = _earnedPointsByIndex.values.fold<int>(0, (sum, p) => sum + p);
    // Note: per-exercise completion already persists progress (either via /exercises/submit
    // for DB exercises or /progress/daily/update for generated micro/cached exercises).

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('🎉 Session Complete!'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Congratulations! You\'ve completed the session.'),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                children: [
                  Text(
                    '+${pointsEarned > 0 ? pointsEarned : widget.session.totalPoints}',
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: Colors.green,
                    ),
                  ),
                  const Text('Points Earned'),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.of(context).pop({
                'completed': completed == total,
                'points': pointsEarned,
              });
            },
            child: const Text('Continue'),
          ),
        ],
      ),
    );
  }

  Future<void> _openExercise(int index) async {
    if (!sessionStarted) return;
    if (index < 0 || index >= widget.session.exercises.length) return;

    // Highlight selected exercise in the list.
    if (mounted) {
      setState(() => currentExerciseIndex = index);
    }

    final exercise = widget.session.exercises[index];

    final result = await Navigator.of(context).push(
      MaterialPageRoute(builder: (context) => _buildExercisePage(exercise)),
    );

    if (!mounted) return;

    if (result is! Map) return;
    final resultMap = Map<String, dynamic>.from(result);

    final completed = resultMap['completed'] == true;
    if (!completed) {
      // User backed out without finishing.
      return;
    }

    final int points = _coerceInt(resultMap['points']) ??
        _coerceInt(resultMap['pointsEarned']) ??
        exercise.points;
    final int score = _coerceInt(resultMap['score']) ?? 0;
    final int totalQuestions = _coerceInt(resultMap['total']) ?? 0;
    final double accuracy = _coerceDouble(resultMap['accuracy_rate']) ??
        _deriveAccuracy(score, totalQuestions);

    setState(() {
      _completedExerciseIndices.add(index);
      _earnedPointsByIndex[index] = points;
      _accuracyByIndex[index] = accuracy;
      // Move to next incomplete exercise if possible.
      final next = _findNextIncompleteIndex(from: index + 1);
      if (next != null) {
        currentExerciseIndex = next;
      }
    });
  }

  int? _findNextIncompleteIndex({required int from}) {
    for (var i = from; i < widget.session.exercises.length; i++) {
      if (!_completedExerciseIndices.contains(i)) return i;
    }
    return null;
  }

  double _deriveAccuracy(int score, int total) {
    if (total <= 0) return 0.0;
    return (score / total).clamp(0.0, 1.0).toDouble();
  }

  int? _coerceInt(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }

  double? _coerceDouble(dynamic value) {
    if (value is double) return value;
    if (value is int) return value.toDouble();
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  Widget _buildExercisePage(Exercise exercise) {
    switch (exercise.type) {
      case ExerciseType.vocabulary:
        return VocabularyExercisePage(exercise: exercise as VocabularyExercise);
      case ExerciseType.grammar:
        return GrammarExercisePage(exercise: exercise as GrammarExercise);
      case ExerciseType.speaking:
        return SpeakingExercisePage(exercise: exercise as SpeakingExercise);
      case ExerciseType.writing:
        return WritingExercisePage(exercise: exercise as WritingExercise);
      case ExerciseType.reading:
      case ExerciseType.listening:
      case ExerciseType.conversation:
        return _UnsupportedExercisePage(exercise: exercise);
    }
  }

  List<Color> _getLevelGradient(DifficultyLevel level) {
    switch (level) {
      case DifficultyLevel.a1:
        return [Colors.green, Colors.lightGreen];
      case DifficultyLevel.a2:
        return [Colors.lightGreen, Colors.lime];
      case DifficultyLevel.b1:
        return [Colors.blue, Colors.lightBlue];
      case DifficultyLevel.b2:
        return [Colors.indigo, Colors.blue];
      case DifficultyLevel.c1:
        return [Colors.purple, Colors.deepPurple];
      case DifficultyLevel.c2:
        return [Colors.red, Colors.pink];
    }
  }

  IconData _getExerciseIcon(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return Icons.menu_book;
      case ExerciseType.grammar:
        return Icons.rule;
      case ExerciseType.reading:
        return Icons.auto_stories;
      case ExerciseType.listening:
        return Icons.headphones;
      case ExerciseType.speaking:
        return Icons.record_voice_over;
      case ExerciseType.writing:
        return Icons.edit;
      case ExerciseType.conversation:
        return Icons.chat;
    }
  }

  Color _getExerciseColor(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return Colors.purple;
      case ExerciseType.grammar:
        return Colors.blue;
      case ExerciseType.reading:
        return Colors.green;
      case ExerciseType.listening:
        return Colors.orange;
      case ExerciseType.speaking:
        return Colors.red;
      case ExerciseType.writing:
        return Colors.teal;
      case ExerciseType.conversation:
        return Colors.pink;
    }
  }
}

class _UnsupportedExercisePage extends StatelessWidget {
  final Exercise exercise;

  const _UnsupportedExercisePage({required this.exercise});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(exercise.title),
        backgroundColor: const Color(0xFF2196F3),
        foregroundColor: Colors.white,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.construction, size: 56, color: Colors.grey[400]),
              const SizedBox(height: 16),
              Text(
                'This exercise type is not available yet.',
                style: Theme.of(context).textTheme.titleMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                'Type: ${exercise.type.name.toUpperCase()}',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.grey[600],
                    ),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Back'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
