import 'package:flutter/material.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../progress/data/repositories/progress_repository.dart';
import '../../data/models/exercise_models.dart';
import '../../data/repositories/practice_repository.dart';

class WritingExercisePage extends StatefulWidget {
  final WritingExercise exercise;

  const WritingExercisePage({super.key, required this.exercise});

  @override
  State<WritingExercisePage> createState() => _WritingExercisePageState();
}

class _WritingExercisePageState extends State<WritingExercisePage>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late final PracticeRepositoryImpl _practiceRepository;
  late final ProgressRepository _progressRepository;
  DateTime _exerciseStartTime = DateTime.now();
  bool _isCompleting = false;

  final TextEditingController _writingController = TextEditingController();
  final FocusNode _writingFocusNode = FocusNode();

  List<AITrainerMessage> trainerMessages = [];
  String? aiAnalysis;
  Map<String, int> scores = {};
  List<String> suggestions = [];
  List<String> strengths = [];
  List<String> weaknesses = [];
  List<WritingError> errors = [];
  List<VocabularySuggestion> vocabularySuggestions = [];
  List<String> nextSteps = [];
  String? correctedVersion;
  bool isAnalyzing = false;
  bool hasSubmitted = false;
  int wordCount = 0;
  bool showRealTimeFeedback = false;

  @override
  void initState() {
    super.initState();

    final apiClient = ApiClient(SecureStorage());
    _practiceRepository = PracticeRepositoryImpl(apiClient);
    _progressRepository = ProgressRepositoryImpl(apiClient);
    _exerciseStartTime = DateTime.now();

    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _animationController.forward();

    _writingController.addListener(_onTextChanged);

    _addTrainerMessage(
      'Ready to practice writing? I\'ll help you create great ${widget.exercise.writingType.name}. Take your time and express your ideas clearly!',
      AITrainerMessageType.welcome,
    );
  }

  @override
  void dispose() {
    _animationController.dispose();
    _writingController.dispose();
    _writingFocusNode.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    final text = _writingController.text;
    final words = text.trim().isEmpty
        ? 0
        : text.trim().split(RegExp(r'\s+')).length;

    setState(() {
      wordCount = words;
    });

    // Provide real-time feedback
    if (showRealTimeFeedback && words > 20 && words % 25 == 0) {
      _addTrainerMessage(
        'Great progress! You\'ve written $words words. Keep going!',
        AITrainerMessageType.encouragement,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: Text(widget.exercise.title),
        backgroundColor: Colors.teal,
        foregroundColor: Colors.white,
        elevation: 0,
        actions: [
          IconButton(
            onPressed: () {
              setState(() {
                showRealTimeFeedback = !showRealTimeFeedback;
              });
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(
                    showRealTimeFeedback
                        ? 'Real-time feedback enabled'
                        : 'Real-time feedback disabled',
                  ),
                  duration: const Duration(seconds: 2),
                ),
              );
            },
            icon: Icon(
              showRealTimeFeedback ? Icons.feedback : Icons.feedback_outlined,
            ),
          ),
        ],
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: Column(
          children: [
            // AI Trainer Messages
            Container(
              height: 100,
              padding: const EdgeInsets.all(16),
              child: ListView.builder(
                itemCount: trainerMessages.length,
                itemBuilder: (context, index) {
                  final message = trainerMessages[index];
                  return _buildTrainerMessage(message);
                },
              ),
            ),

            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Writing Prompt Card
                    _buildPromptCard(),

                    const SizedBox(height: 20),

                    // Guidelines
                    _buildGuidelinesCard(),

                    const SizedBox(height: 20),

                    // Key Words
                    _buildKeyWordsSection(),

                    const SizedBox(height: 20),

                    // Writing Area
                    _buildWritingArea(),

                    const SizedBox(height: 20),

                    // AI Analysis Results
                    if (aiAnalysis != null) _buildAnalysisResults(),

                    const SizedBox(height: 80),
                  ],
                ),
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
          child: hasSubmitted
              ? _buildCompletionButtons()
              : _buildSubmitButton(),
        ),
      ),
    );
  }

  Widget _buildTrainerMessage(AITrainerMessage message) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: LinearGradient(colors: _getMessageGradient(message.type)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(_getMessageIcon(message.type), color: Colors.white, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message.message,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPromptCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Colors.teal, Colors.cyan],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.teal.withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                _getWritingTypeIcon(widget.exercise.writingType),
                color: Colors.white,
                size: 28,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  widget.exercise.writingType.name.toUpperCase(),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            'Writing Task:',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.9),
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            widget.exercise.prompt,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 16),
          Row(
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
                  '${widget.exercise.minWords}-${widget.exercise.maxWords} words',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const SizedBox(width: 8),
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
                  '${widget.exercise.points} points',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildGuidelinesCard() {
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
              Icon(Icons.checklist, color: Colors.teal, size: 20),
              const SizedBox(width: 8),
              Text(
                'Writing Guidelines:',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.teal,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...widget.exercise.guidelines.map(
            (guideline) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    margin: const EdgeInsets.only(top: 8, right: 12),
                    decoration: BoxDecoration(
                      color: Colors.teal,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      guideline,
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

  Widget _buildKeyWordsSection() {
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
              Icon(Icons.key, color: Colors.teal, size: 20),
              const SizedBox(width: 8),
              Text(
                'Suggested Key Words:',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.teal,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: widget.exercise.keyWords.map((word) {
              return GestureDetector(
                onTap: () => _insertKeyWord(word),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.teal.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: Colors.teal.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        word,
                        style: const TextStyle(
                          color: Colors.teal,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Icon(
                        Icons.add_circle_outline,
                        size: 14,
                        color: Colors.teal,
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildWritingArea() {
    final isWithinRange =
        wordCount >= widget.exercise.minWords &&
        wordCount <= widget.exercise.maxWords;

    return Container(
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
          // Header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.teal.withValues(alpha: 0.1),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(16),
              ),
            ),
            child: Row(
              children: [
                Icon(Icons.edit, color: Colors.teal, size: 20),
                const SizedBox(width: 8),
                Text(
                  'Your Writing',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.teal,
                  ),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: isWithinRange ? Colors.green : Colors.orange,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '$wordCount words',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Writing Text Field
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _writingController,
              focusNode: _writingFocusNode,
              maxLines: 15,
              enabled: !hasSubmitted,
              style: const TextStyle(fontSize: 16, height: 1.5),
              decoration: InputDecoration(
                hintText:
                    'Start writing your ${widget.exercise.writingType.name} here...',
                border: InputBorder.none,
                hintStyle: TextStyle(color: Colors.grey[400], fontSize: 16),
              ),
            ),
          ),

          // Word Count Progress
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Column(
              children: [
                LinearProgressIndicator(
                  value: (wordCount / widget.exercise.maxWords).clamp(0.0, 1.0),
                  backgroundColor: Colors.grey[200],
                  valueColor: AlwaysStoppedAnimation<Color>(
                    wordCount < widget.exercise.minWords
                        ? Colors.orange
                        : wordCount > widget.exercise.maxWords
                        ? Colors.red
                        : Colors.green,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Min: ${widget.exercise.minWords}',
                      style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                    ),
                    Text(
                      wordCount < widget.exercise.minWords
                          ? '${widget.exercise.minWords - wordCount} more needed'
                          : wordCount > widget.exercise.maxWords
                          ? '${wordCount - widget.exercise.maxWords} over limit'
                          : 'Perfect length!',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: wordCount < widget.exercise.minWords
                            ? Colors.orange
                            : wordCount > widget.exercise.maxWords
                            ? Colors.red
                            : Colors.green,
                      ),
                    ),
                    Text(
                      'Max: ${widget.exercise.maxWords}',
                      style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildAnalysisResults() {
    return Column(
      children: [
        // Main Scores Card
        Container(
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
                  Icon(Icons.analytics, color: Colors.teal, size: 24),
                  const SizedBox(width: 8),
                  Text(
                    'AI Analysis Results',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Colors.teal,
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 20),

              // Scores Grid
              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 2.5,
                children: scores.entries.map((entry) {
                  return Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _getScoreColor(entry.value).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: _getScoreColor(
                          entry.value,
                        ).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          '${entry.value}%',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: _getScoreColor(entry.value),
                          ),
                        ),
                        Text(
                          entry.key,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),

              const SizedBox(height: 20),

              // AI Analysis Text
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.blue.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.smart_toy, color: Colors.blue, size: 20),
                        const SizedBox(width: 8),
                        Text(
                          'AI Trainer Feedback:',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.blue,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      aiAnalysis!,
                      style: const TextStyle(fontSize: 14, height: 1.4),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // Errors and Corrections Card (Most Important for Learning!)
        if (errors.isNotEmpty) ...[
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
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
                    Icon(Icons.error_outline, color: Colors.red, size: 24),
                    const SizedBox(width: 8),
                    Text(
                      'Errors & Corrections',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.red,
                      ),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${errors.length} found',
                        style: TextStyle(
                          color: Colors.red,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                ...errors.map(
                  (error) => Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: _getErrorColor(
                        error.severity,
                      ).withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: _getErrorColor(
                          error.severity,
                        ).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Error type badge
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: _getErrorColor(error.severity),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                error.type.toUpperCase(),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              error.severity.toUpperCase(),
                              style: TextStyle(
                                color: _getErrorColor(error.severity),
                                fontSize: 10,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),

                        // Wrong text (crossed out)
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.close, color: Colors.red, size: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                error.original,
                                style: TextStyle(
                                  color: Colors.red[700],
                                  fontSize: 14,
                                  decoration: TextDecoration.lineThrough,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),

                        // Corrected text
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(Icons.check, color: Colors.green, size: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                error.corrected,
                                style: TextStyle(
                                  color: Colors.green[700],
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),

                        // Explanation
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.blue.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.lightbulb_outline,
                                color: Colors.blue,
                                size: 18,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  error.explanation,
                                  style: TextStyle(
                                    color: Colors.blue[800],
                                    fontSize: 13,
                                    height: 1.4,
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
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],

        // Strengths Card
        if (strengths.isNotEmpty) ...[
          Container(
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
                    Icon(Icons.thumb_up, color: Colors.green, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'What You Did Well',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.green,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...strengths.map(
                  (strength) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.check_circle, color: Colors.green, size: 16),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            strength,
                            style: const TextStyle(fontSize: 14, height: 1.4),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],

        // Vocabulary Suggestions Card
        if (vocabularySuggestions.isNotEmpty) ...[
          Container(
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
                    Icon(Icons.auto_awesome, color: Colors.purple, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Vocabulary Improvements',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.purple,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...vocabularySuggestions.map(
                  (vocab) => Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.purple.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              '"${vocab.originalWord}"',
                              style: TextStyle(
                                fontWeight: FontWeight.w500,
                                color: Colors.grey[700],
                              ),
                            ),
                            const SizedBox(width: 8),
                            Icon(
                              Icons.arrow_forward,
                              size: 16,
                              color: Colors.purple,
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Wrap(
                                spacing: 6,
                                children: vocab.betterAlternatives
                                    .map(
                                      (alt) => Container(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 8,
                                          vertical: 4,
                                        ),
                                        decoration: BoxDecoration(
                                          color: Colors.purple.withValues(
                                            alpha: 0.2,
                                          ),
                                          borderRadius: BorderRadius.circular(
                                            12,
                                          ),
                                        ),
                                        child: Text(
                                          alt,
                                          style: TextStyle(
                                            color: Colors.purple[700],
                                            fontSize: 12,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ),
                                    )
                                    .toList(),
                              ),
                            ),
                          ],
                        ),
                        if (vocab.context.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            vocab.context,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],

        // Suggestions Card
        if (suggestions.isNotEmpty) ...[
          Container(
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
                      Icons.tips_and_updates,
                      color: Colors.orange,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'How to Improve',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.orange,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...suggestions.map(
                  (suggestion) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          margin: const EdgeInsets.only(top: 8, right: 12),
                          decoration: BoxDecoration(
                            color: Colors.orange,
                            borderRadius: BorderRadius.circular(3),
                          ),
                        ),
                        Expanded(
                          child: Text(
                            suggestion,
                            style: const TextStyle(fontSize: 14, height: 1.4),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],

        // Next Steps Card
        if (nextSteps.isNotEmpty) ...[
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.teal.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.teal.withValues(alpha: 0.3)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.arrow_forward, color: Colors.teal, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Next Steps',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.teal,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...nextSteps.asMap().entries.map(
                  (entry) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 24,
                          height: 24,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: Colors.teal,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '${entry.key + 1}',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            entry.value,
                            style: const TextStyle(fontSize: 14, height: 1.4),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Color _getErrorColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'major':
        return Colors.red;
      case 'moderate':
        return Colors.orange;
      case 'minor':
      default:
        return Colors.amber;
    }
  }

  Widget _buildSubmitButton() {
    final canSubmit =
        wordCount >= widget.exercise.minWords &&
        wordCount <= widget.exercise.maxWords;

    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton(
        onPressed: canSubmit && !isAnalyzing ? _submitWriting : null,
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.teal,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(25),
          ),
          disabledBackgroundColor: Colors.grey[300],
        ),
        child: isAnalyzing
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  color: Colors.white,
                  strokeWidth: 2,
                ),
              )
            : Text(
                isAnalyzing ? 'Analyzing...' : 'Get AI Feedback',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
      ),
    );
  }

  Widget _buildCompletionButtons() {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            onPressed: _reviseWriting,
            child: const Text('Revise'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: ElevatedButton(
            onPressed: _completeExercise,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
              foregroundColor: Colors.white,
            ),
            child: const Text('Complete'),
          ),
        ),
      ],
    );
  }

  void _insertKeyWord(String word) {
    final currentText = _writingController.text;
    final selection = _writingController.selection;

    String newText;
    int newCursorPosition;

    if (selection.start == -1) {
      // No selection, add at end
      newText = currentText.isEmpty ? word : '$currentText $word';
      newCursorPosition = newText.length;
    } else {
      // Insert at cursor position
      newText = currentText.replaceRange(selection.start, selection.end, word);
      newCursorPosition = selection.start + word.length;
    }

    _writingController.text = newText;
    _writingController.selection = TextSelection.collapsed(
      offset: newCursorPosition,
    );

    _writingFocusNode.requestFocus();

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Added "$word" to your writing'),
        duration: const Duration(seconds: 1),
      ),
    );
  }

  void _submitWriting() async {
    setState(() {
      isAnalyzing = true;
    });

    // Call the real AI assessment API
    final result = await _practiceRepository.assessWriting(
      text: _writingController.text,
      writingType: widget.exercise.writingType.name,
    );

    setState(() {
      isAnalyzing = false;
      hasSubmitted = true;

      // Set scores from API response
      scores = {
        'Grammar': result.scores.grammar,
        'Vocabulary': result.scores.vocabulary,
        'Coherence': result.scores.coherence,
        'Task': result.scores.taskAchievement,
      };

      // Set detailed feedback
      aiAnalysis = result.feedback;
      suggestions = result.suggestions;
      strengths = result.strengths;
      weaknesses = result.weaknesses;
      errors = result.errors;
      vocabularySuggestions = result.vocabularySuggestions;
      nextSteps = result.nextSteps;
      correctedVersion = result.correctedVersion;
    });

    // Calculate overall score
    final overallScore = result.scores.overall;

    // Add trainer feedback
    if (overallScore >= 85) {
      _addTrainerMessage(
        'Outstanding writing! Your overall score is $overallScore%. You\'ve demonstrated excellent ${widget.exercise.writingType.name} skills!',
        AITrainerMessageType.celebration,
      );
    } else if (overallScore >= 70) {
      _addTrainerMessage(
        'Great job! You scored $overallScore% overall. Your writing is developing well. Keep practicing!',
        AITrainerMessageType.encouragement,
      );
    } else {
      _addTrainerMessage(
        'Good effort! You scored $overallScore%. There\'s room for improvement, but you\'re making progress. Let\'s work on it together!',
        AITrainerMessageType.correction,
      );
    }
  }

  void _reviseWriting() {
    setState(() {
      hasSubmitted = false;
      aiAnalysis = null;
      scores.clear();
      suggestions.clear();
      strengths.clear();
      weaknesses.clear();
      errors.clear();
      vocabularySuggestions.clear();
      nextSteps.clear();
      correctedVersion = null;
    });

    _writingFocusNode.requestFocus();

    _addTrainerMessage(
      'Great! Let\'s revise your writing based on the feedback. Take your time to make improvements!',
      AITrainerMessageType.encouragement,
    );
  }

  Future<void> _completeExercise() async {
    if (_isCompleting) return;
    setState(() => _isCompleting = true);

    final overallScore = scores.isEmpty
        ? 0
        : (scores.values.reduce((a, b) => a + b) ~/ scores.length);
    final accuracy = (overallScore / 100).clamp(0.0, 1.0);

    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;
    var pointsEarned = widget.exercise.points;

    try {
      if (exerciseId > 0) {
        final timeTakenSeconds = DateTime.now()
            .difference(_exerciseStartTime)
            .inSeconds;
        final result = await _practiceRepository.submitExercise(
          exerciseId: exerciseId,
          userAnswer: {
            'text': _writingController.text,
            'word_count': wordCount,
            if (scores.isNotEmpty) 'scores': scores,
          },
          timeTakenSeconds: timeTakenSeconds > 0 ? timeTakenSeconds : null,
        );
        if (result.pointsEarned > 0) {
          pointsEarned = result.pointsEarned;
        }
      } else {
        final minutes =
            (DateTime.now().difference(_exerciseStartTime).inSeconds / 60)
                .ceil()
                .clamp(1, 999);
        await _progressRepository.updateDailyProgress(
          studyTimeMinutes: minutes,
          exercisesCompleted: 1,
          pointsEarned: pointsEarned,
          accuracyRate: accuracy,
        );
      }
    } catch (e) {
      debugPrint('Failed to persist writing result: $e');
    }

    if (!mounted) return;
    setState(() => _isCompleting = false);

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('🎉 Exercise Complete!'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Your overall writing score: $overallScore%'),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.teal.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                children: [
                  Text(
                    '+$pointsEarned',
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: Colors.teal,
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
                'completed': true,
                'score': overallScore,
                'total': 100,
                'points': pointsEarned,
                'accuracy_rate': accuracy,
              });
            },
            child: const Text('Continue'),
          ),
        ],
      ),
    );
  }

  void _addTrainerMessage(String message, AITrainerMessageType type) {
    setState(() {
      trainerMessages.add(
        AITrainerMessage(
          id: DateTime.now().millisecondsSinceEpoch.toString(),
          message: message,
          type: type,
          timestamp: DateTime.now(),
        ),
      );

      // Keep only last 3 messages
      if (trainerMessages.length > 3) {
        trainerMessages.removeAt(0);
      }
    });
  }

  IconData _getWritingTypeIcon(WritingType type) {
    switch (type) {
      case WritingType.essay:
        return Icons.article;
      case WritingType.email:
        return Icons.email;
      case WritingType.letter:
        return Icons.mail;
      case WritingType.story:
        return Icons.auto_stories;
      case WritingType.description:
        return Icons.description;
      case WritingType.opinion:
        return Icons.rate_review;
    }
  }

  Color _getScoreColor(int score) {
    if (score >= 85) return Colors.green;
    if (score >= 70) return Colors.orange;
    return Colors.red;
  }

  List<Color> _getMessageGradient(AITrainerMessageType type) {
    switch (type) {
      case AITrainerMessageType.welcome:
        return [const Color(0xFF2196F3), const Color(0xFF21CBF3)];
      case AITrainerMessageType.encouragement:
        return [const Color(0xFF4CAF50), const Color(0xFF8BC34A)];
      case AITrainerMessageType.correction:
        return [const Color(0xFFFF9800), const Color(0xFFFFC107)];
      case AITrainerMessageType.celebration:
        return [const Color(0xFFE91E63), const Color(0xFFFF5722)];
      default:
        return [const Color(0xFF607D8B), const Color(0xFF9E9E9E)];
    }
  }

  IconData _getMessageIcon(AITrainerMessageType type) {
    switch (type) {
      case AITrainerMessageType.welcome:
        return Icons.waving_hand;
      case AITrainerMessageType.encouragement:
        return Icons.thumb_up;
      case AITrainerMessageType.correction:
        return Icons.lightbulb_outline;
      case AITrainerMessageType.celebration:
        return Icons.celebration;
      default:
        return Icons.smart_toy;
    }
  }
}
