import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../progress/data/repositories/progress_repository.dart';
import '../../data/models/exercise_models.dart';
import '../../data/repositories/practice_repository.dart';

class VocabularyExercisePage extends StatefulWidget {
  final VocabularyExercise exercise;

  const VocabularyExercisePage({super.key, required this.exercise});

  @override
  State<VocabularyExercisePage> createState() => _VocabularyExercisePageState();
}

class _VocabularyExercisePageState extends State<VocabularyExercisePage>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late PracticeRepositoryImpl _repository;
  late final ProgressRepository _progressRepository;
  late FlutterTts _flutterTts;

  int currentWordIndex = 0;
  int score = 0;
  int totalPointsEarned = 0;
  bool isAnswered = false;
  String? selectedAnswer;
  List<String> userAnswers = [];
  List<AITrainerMessage> trainerMessages = [];
  final TextEditingController _inputController = TextEditingController();
  bool isLoading = false;
  DateTime? _exerciseStartTime;
  bool _isSpeaking = false;

  // When exercises come from `/exercises/`, the correct answer and explanation are only known after submit.
  final Map<int, String> _correctAnswersByIndex = {};
  final Map<int, String> _explanationsByIndex = {};

  @override
  void initState() {
    super.initState();
    final apiClient = ApiClient(SecureStorage());
    _repository = PracticeRepositoryImpl(apiClient);
    _progressRepository = ProgressRepositoryImpl(apiClient);
    _exerciseStartTime = DateTime.now();

    // Initialize TTS
    _flutterTts = FlutterTts();
    _initTts();

    _animationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _animationController.forward();
    _addTrainerMessage(
      'Welcome! Let\'s practice vocabulary together. I\'ll show you words and help you learn their meanings. Ready?',
      AITrainerMessageType.welcome,
    );
  }

  Future<void> _initTts() async {
    await _flutterTts.setLanguage("en-US");
    await _flutterTts.setSpeechRate(0.45); // Slightly slower for learning
    await _flutterTts.setVolume(1.0);
    await _flutterTts.setPitch(1.0);

    _flutterTts.setStartHandler(() {
      if (mounted) setState(() => _isSpeaking = true);
    });

    _flutterTts.setCompletionHandler(() {
      if (mounted) setState(() => _isSpeaking = false);
    });

    _flutterTts.setErrorHandler((msg) {
      if (mounted) setState(() => _isSpeaking = false);
    });
  }

  @override
  void dispose() {
    _animationController.dispose();
    _inputController.dispose();
    _flutterTts.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Handle empty words list
    if (widget.exercise.words.isEmpty) {
      return Scaffold(
        backgroundColor: Colors.grey[50],
        appBar: AppBar(
          title: Text(widget.exercise.title),
          backgroundColor: Colors.purple,
          foregroundColor: Colors.white,
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.warning_amber_rounded,
                size: 64,
                color: Colors.orange[400],
              ),
              const SizedBox(height: 16),
              const Text(
                'No vocabulary words available',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              Text(
                'Please try another exercise',
                style: TextStyle(color: Colors.grey[600]),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => Navigator.of(context).pop(),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.purple,
                  foregroundColor: Colors.white,
                ),
                child: const Text('Go Back'),
              ),
            ],
          ),
        ),
      );
    }

    final currentWord = widget.exercise.words[currentWordIndex];

    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: Text(widget.exercise.title),
        backgroundColor: Colors.purple,
        foregroundColor: Colors.white,
        elevation: 0,
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              '${currentWordIndex + 1}/${widget.exercise.words.length}',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: Column(
          children: [
            // Progress Bar
            LinearProgressIndicator(
              value: (currentWordIndex + 1) / widget.exercise.words.length,
              backgroundColor: Colors.grey[200],
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.purple),
              minHeight: 4,
            ),

            // AI Trainer Messages
            Container(
              height: 120,
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
                  children: [
                    // Word Card
                    _buildWordCard(currentWord),
                    const SizedBox(height: 24),

                    // Exercise Content based on type
                    if (widget.exercise.exerciseType ==
                        VocabularyExerciseType.matching)
                      _buildMatchingExercise(currentWord)
                    else if (widget.exercise.exerciseType ==
                        VocabularyExerciseType.multipleChoice)
                      _buildMultipleChoiceExercise(currentWord)
                    else if (widget.exercise.exerciseType ==
                        VocabularyExerciseType.fillInTheBlanks)
                      _buildFillInBlanksExercise(currentWord)
                    else
                      _buildWordBuildingExercise(currentWord),

                    if (isAnswered) ...[
                      const SizedBox(height: 16),
                      _buildWordDetails(currentWord),
                    ],

                    const SizedBox(height: 24),

                    // Action Button
                    if (!isAnswered)
                      _buildSubmitButton()
                    else
                      _buildNextButton(),

                    const SizedBox(height: 80),
                  ],
                ),
              ),
            ),
          ],
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

  Widget _buildWordCard(VocabularyWord word) {
    return Semantics(
      label:
          'Vocabulary word: ${word.word}. Pronunciation: ${word.pronunciation}',
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Colors.purple, Colors.deepPurple],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.purple.withValues(alpha: 0.3),
              blurRadius: 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Column(
          children: [
            Text(
              word.word.toUpperCase(),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 32,
                fontWeight: FontWeight.bold,
                letterSpacing: 2,
              ),
            ),
            if (word.pronunciation.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                word.pronunciation,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.9),
                  fontSize: 16,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
            const SizedBox(height: 16),
            Semantics(
              button: true,
              label: _isSpeaking ? 'Stop pronunciation' : 'Play pronunciation',
              child: GestureDetector(
                onTap: () => _speakWord(word.word),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: _isSpeaking
                        ? Colors.white.withValues(alpha: 0.4)
                        : Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(20),
                    border: _isSpeaking
                        ? Border.all(color: Colors.white, width: 2)
                        : null,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _isSpeaking ? Icons.stop_circle : Icons.volume_up,
                        color: Colors.white,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _isSpeaking ? 'Stop' : 'Tap to hear pronunciation',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
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
    );
  }

  Widget _buildWordDetails(VocabularyWord word) {
    final definitionText = _resolveCorrectAnswer(currentWordIndex, word);
    final explanationText = _resolveExplanation(currentWordIndex, word);

    final hasDetails =
        definitionText.isNotEmpty ||
        explanationText.isNotEmpty ||
        word.synonyms.isNotEmpty ||
        word.antonyms.isNotEmpty;

    if (!hasDetails) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.purple.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
        border: Border.all(color: Colors.purple.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.menu_book, color: Colors.purple, size: 20),
              const SizedBox(width: 8),
              const Text(
                'Meaning & examples',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.purple,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (definitionText.isNotEmpty)
            Text(
              definitionText,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
          if (definitionText.isNotEmpty && explanationText.isNotEmpty)
            const SizedBox(height: 10),
          if (explanationText.isNotEmpty)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.purple.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.record_voice_over,
                    color: Colors.purple,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      explanationText,
                      style: const TextStyle(
                        fontSize: 14,
                        fontStyle: FontStyle.italic,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          if (word.synonyms.isNotEmpty || word.antonyms.isNotEmpty) ...[
            const SizedBox(height: 12),
            if (word.synonyms.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Synonyms:',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: word.synonyms
                          .take(5)
                          .map(
                            (s) => Chip(
                              label: Text(s),
                              backgroundColor: Colors.purple.withValues(
                                alpha: 0.08,
                              ),
                              labelStyle: const TextStyle(
                                color: Colors.purple,
                                fontSize: 12,
                              ),
                              visualDensity: VisualDensity.compact,
                              materialTapTargetSize:
                                  MaterialTapTargetSize.shrinkWrap,
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ),
              ),
            if (word.antonyms.isNotEmpty)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Antonyms:',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                  ),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: word.antonyms
                        .take(5)
                        .map(
                          (a) => Chip(
                            label: Text(a),
                            backgroundColor: Colors.orange.withValues(
                              alpha: 0.08,
                            ),
                            labelStyle: const TextStyle(
                              color: Colors.orange,
                              fontSize: 12,
                            ),
                            visualDensity: VisualDensity.compact,
                            materialTapTargetSize:
                                MaterialTapTargetSize.shrinkWrap,
                          ),
                        )
                        .toList(),
                  ),
                ],
              ),
          ],
        ],
      ),
    );
  }

  Widget _buildMultipleChoiceExercise(VocabularyWord word) {
    final prompt = (word.question ?? '').trim();
    final options = word.options.isNotEmpty
        ? word.options
        : _generateOptions(word);
    final correctAnswer = _resolveCorrectAnswer(currentWordIndex, word);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          prompt.isNotEmpty ? prompt : 'What does "${word.word}" mean?',
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        ...options.asMap().entries.map((entry) {
          final index = entry.key;
          final option = entry.value;
          final isSelected = selectedAnswer == option;
          final isCorrect = isAnswered && correctAnswer.isNotEmpty
              ? _normalized(option) == _normalized(correctAnswer)
              : false;

          return Semantics(
            button: true,
            selected: isSelected,
            label:
                'Option ${String.fromCharCode(65 + index)}: $option${isAnswered && isCorrect ? ', correct answer' : ''}${isAnswered && isSelected && !isCorrect ? ', incorrect' : ''}',
            child: GestureDetector(
              onTap: isAnswered ? null : () => _selectAnswer(option),
              child: Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: isAnswered
                      ? isCorrect
                            ? Colors.green.withValues(alpha: 0.1)
                            : isSelected
                            ? Colors.red.withValues(alpha: 0.1)
                            : Colors.white
                      : isSelected
                      ? Colors.purple.withValues(alpha: 0.1)
                      : Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isAnswered
                        ? isCorrect
                              ? Colors.green
                              : isSelected
                              ? Colors.red
                              : Colors.grey[300]!
                        : isSelected
                        ? Colors.purple
                        : Colors.grey[300]!,
                    width: 2,
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 24,
                      height: 24,
                      decoration: BoxDecoration(
                        color: isAnswered
                            ? isCorrect
                                  ? Colors.green
                                  : isSelected
                                  ? Colors.red
                                  : Colors.grey[300]
                            : isSelected
                            ? Colors.purple
                            : Colors.grey[300],
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Center(
                        child: Text(
                          String.fromCharCode(65 + index), // A, B, C, D
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Text(option, style: const TextStyle(fontSize: 16)),
                    ),
                    if (isAnswered && isCorrect)
                      const Icon(Icons.check_circle, color: Colors.green),
                    if (isAnswered && isSelected && !isCorrect)
                      const Icon(Icons.cancel, color: Colors.red),
                  ],
                ),
              ),
            ),
          );
        }),
      ],
    );
  }

  Widget _buildFillInBlanksExercise(VocabularyWord word) {
    _resolveCorrectAnswer(currentWordIndex, word);
    final userAnswer = selectedAnswer?.trim() ?? '';
    final isCorrect =
        isAnswered && _normalized(userAnswer) == _normalized(word.word);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Complete the sentence:',
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isAnswered
                  ? (isCorrect ? Colors.green : Colors.red)
                  : Colors.grey[300]!,
              width: isAnswered ? 2 : 1,
            ),
          ),
          child: Column(
            children: [
              Text(
                _createSentenceWithBlank(word.exampleSentence, word.word),
                style: const TextStyle(fontSize: 18, height: 1.5),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _inputController,
                enabled: !isAnswered,
                textInputAction: TextInputAction.done,
                decoration: InputDecoration(
                  hintText: 'Type your answer here...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(
                      color: isAnswered
                          ? (isCorrect ? Colors.green : Colors.red)
                          : Colors.grey[300]!,
                    ),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(
                      color: isAnswered
                          ? (isCorrect ? Colors.green : Colors.red)
                          : Colors.grey[300]!,
                      width: isAnswered ? 2 : 1,
                    ),
                  ),
                  disabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(
                      color: isCorrect ? Colors.green : Colors.red,
                      width: 2,
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(
                      color: Colors.purple,
                      width: 2,
                    ),
                  ),
                  suffixIcon: isAnswered
                      ? Icon(
                          isCorrect ? Icons.check_circle : Icons.cancel,
                          color: isCorrect ? Colors.green : Colors.red,
                        )
                      : (selectedAnswer?.isNotEmpty == true
                            ? IconButton(
                                icon: const Icon(
                                  Icons.send,
                                  color: Colors.purple,
                                ),
                                onPressed: _submitAnswer,
                              )
                            : null),
                  fillColor: isAnswered
                      ? (isCorrect
                            ? Colors.green.withValues(alpha: 0.05)
                            : Colors.red.withValues(alpha: 0.05))
                      : null,
                  filled: isAnswered,
                ),
                onChanged: (value) {
                  setState(() {
                    selectedAnswer = value;
                  });
                },
                onSubmitted: (_) {
                  if (selectedAnswer?.isNotEmpty == true && !isAnswered) {
                    _submitAnswer();
                  }
                },
              ),
              // Feedback section for fill-in-the-blank
              if (isAnswered) ...[
                const SizedBox(height: 16),
                _buildFillBlankFeedback(word, userAnswer, isCorrect),
              ],
            ],
          ),
        ),
      ],
    );
  }

  /// Build feedback widget for fill-in-the-blank exercises
  Widget _buildFillBlankFeedback(
    VocabularyWord word,
    String userAnswer,
    bool isCorrect,
  ) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isCorrect
            ? Colors.green.withValues(alpha: 0.1)
            : Colors.red.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isCorrect ? Colors.green : Colors.red,
          width: 1.5,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Result header
          Row(
            children: [
              Icon(
                isCorrect ? Icons.check_circle : Icons.cancel,
                color: isCorrect ? Colors.green : Colors.red,
                size: 24,
              ),
              const SizedBox(width: 8),
              Text(
                isCorrect ? 'Correct! 🎉' : 'Not quite right',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: isCorrect ? Colors.green[700] : Colors.red[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // User's answer
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: isCorrect ? Colors.green[300]! : Colors.red[300]!,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Your answer:',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  userAnswer.isNotEmpty ? userAnswer : '(empty)',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: isCorrect ? Colors.green[700] : Colors.red[700],
                  ),
                ),
              ],
            ),
          ),

          // Correct answer (show if wrong)
          if (!isCorrect) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.green[300]!),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Correct answer:',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.green[700],
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    word.word,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Colors.green[700],
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Helpful tip
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.blue.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.lightbulb_outline,
                  color: Colors.blue[600],
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    isCorrect
                        ? 'Great job! You correctly identified the word "${word.word}".'
                        : 'Remember: "${word.word}" - ${word.definition}',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.blue[700],
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMatchingExercise(VocabularyWord word) {
    final options = word.options.isNotEmpty
        ? word.options
        : _generateMatchingOptions(word);
    final correctAnswer = _resolveCorrectAnswer(currentWordIndex, word);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Match the word with its meaning:',
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.purple.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Colors.purple.withValues(alpha: 0.3),
                  ),
                ),
                child: Column(
                  children: [
                    const Text(
                      'WORD',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.purple,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      word.word,
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                children: options.map((option) {
                  final isSelected = selectedAnswer == option;
                  final isCorrect = isAnswered && correctAnswer.isNotEmpty
                      ? _normalized(option) == _normalized(correctAnswer)
                      : false;

                  return GestureDetector(
                    onTap: isAnswered ? null : () => _selectAnswer(option),
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isAnswered
                            ? isCorrect
                                  ? Colors.green.withValues(alpha: 0.1)
                                  : isSelected
                                  ? Colors.red.withValues(alpha: 0.1)
                                  : Colors.white
                            : isSelected
                            ? Colors.purple.withValues(alpha: 0.1)
                            : Colors.white,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: isAnswered
                              ? isCorrect
                                    ? Colors.green
                                    : isSelected
                                    ? Colors.red
                                    : Colors.grey[300]!
                              : isSelected
                              ? Colors.purple
                              : Colors.grey[300]!,
                        ),
                      ),
                      child: Text(
                        option,
                        style: const TextStyle(fontSize: 14),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildWordBuildingExercise(VocabularyWord word) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Build a sentence using this word:',
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.grey[300]!),
          ),
          child: Column(
            children: [
              TextField(
                controller: _inputController,
                enabled: !isAnswered,
                maxLines: 3,
                textInputAction: TextInputAction.done,
                decoration: InputDecoration(
                  hintText: 'Write a sentence using "${word.word}"...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(
                      color: Colors.purple,
                      width: 2,
                    ),
                  ),
                ),
                onChanged: (value) {
                  setState(() {
                    selectedAnswer = value;
                  });
                },
                onSubmitted: (_) {
                  if (selectedAnswer?.isNotEmpty == true && !isAnswered) {
                    _submitAnswer();
                  }
                },
              ),
              const SizedBox(height: 12),
              Text(
                'Hint: ${word.definition}',
                style: TextStyle(
                  color: Colors.grey[600],
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSubmitButton() {
    final canSubmit = selectedAnswer != null && selectedAnswer!.isNotEmpty;

    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton(
        onPressed: canSubmit ? _submitAnswer : null,
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.purple,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(25),
          ),
          disabledBackgroundColor: Colors.grey[300],
        ),
        child: isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  color: Colors.white,
                  strokeWidth: 2,
                ),
              )
            : const Text(
                'Submit Answer',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
      ),
    );
  }

  Widget _buildNextButton() {
    final isLastWord = currentWordIndex >= widget.exercise.words.length - 1;

    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton(
        onPressed: isLastWord ? _completeExercise : _nextWord,
        style: ElevatedButton.styleFrom(
          backgroundColor: isLastWord ? Colors.green : Colors.purple,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(25),
          ),
        ),
        child: Text(
          isLastWord ? 'Complete Exercise' : 'Next Word',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }

  void _selectAnswer(String answer) {
    if (!isAnswered) {
      setState(() {
        selectedAnswer = answer;
      });
    }
  }

  void _submitAnswer() async {
    final raw = selectedAnswer;
    if (raw == null) return;

    final answer = raw.trim();
    if (answer.isEmpty) return;

    setState(() => isLoading = true);

    final currentWord = widget.exercise.words[currentWordIndex];
    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;
    final isRemoteExercise = exerciseId > 0;

    bool isCorrect = false;

    // If this exercise comes from `/exercises/`, use the backend response as the source of truth.
    if (isRemoteExercise) {
      try {
        final timeTaken = _exerciseStartTime != null
            ? DateTime.now().difference(_exerciseStartTime!).inSeconds
            : null;

        final Map<String, dynamic> userAnswerPayload;
        switch (widget.exercise.exerciseType) {
          case VocabularyExerciseType.multipleChoice:
          case VocabularyExerciseType.matching:
            userAnswerPayload = {'selected': answer};
            break;
          case VocabularyExerciseType.fillInTheBlanks:
          case VocabularyExerciseType.wordBuilding:
            userAnswerPayload = {'text': answer};
            break;
        }

        final result = await _repository.submitExercise(
          exerciseId: exerciseId,
          userAnswer: userAnswerPayload,
          timeTakenSeconds: timeTaken,
        );

        isCorrect = result.isCorrect;

        // Persist correct answer + explanation for UI reveal
        final correct =
            (result.correctAnswer?['correct_option'] ??
                    result.correctAnswer?['text'] ??
                    result.correctAnswer?['answer'])
                ?.toString()
                .trim();
        if (correct != null && correct.isNotEmpty) {
          _correctAnswersByIndex[currentWordIndex] = correct;
        }

        final expl = (result.explanation ?? '').trim();
        if (expl.isNotEmpty) {
          _explanationsByIndex[currentWordIndex] = expl;
        }

        if (result.pointsEarned > 0) {
          totalPointsEarned += result.pointsEarned;
        }

        // Use AI feedback if available
        if (result.aiFeedback != null && result.aiFeedback!.isNotEmpty) {
          _addTrainerMessage(
            result.aiFeedback!,
            isCorrect
                ? AITrainerMessageType.celebration
                : AITrainerMessageType.correction,
          );
        }
      } catch (e) {
        // Continue even if submission fails - we don't want to break the exercise
        debugPrint('Failed to submit answer: $e');
        isCorrect = _checkAnswer(currentWord, answer);
      }
    } else {
      isCorrect = _checkAnswer(currentWord, answer);
    }

    setState(() {
      isAnswered = true;
      isLoading = false;
      if (isCorrect) score++;
      userAnswers.add(answer);
    });

    final resolvedCorrect = _resolveCorrectAnswer(
      currentWordIndex,
      currentWord,
    );

    // Add trainer feedback if we didn't get AI feedback
    if (trainerMessages.isEmpty ||
        trainerMessages.last.message.contains('Welcome') ||
        trainerMessages.last.message.contains('progress')) {
      if (isCorrect) {
        _addTrainerMessage(
          resolvedCorrect.isNotEmpty
              ? 'Excellent! You got it right! "${currentWord.word}" means "$resolvedCorrect". Great job! 🎉'
              : 'Excellent! You got it right! Great job! 🎉',
          AITrainerMessageType.celebration,
        );
      } else {
        _addTrainerMessage(
          resolvedCorrect.isNotEmpty
              ? 'Not quite right. "${currentWord.word}" actually means "$resolvedCorrect". Let\'s learn from this!'
              : 'Not quite right. Let\'s learn from this!',
          AITrainerMessageType.correction,
        );
      }
    }

    // Vibrate for feedback
    HapticFeedback.lightImpact();
  }

  void _nextWord() {
    if (currentWordIndex < widget.exercise.words.length - 1) {
      setState(() {
        currentWordIndex++;
        isAnswered = false;
        selectedAnswer = null;
        _inputController.clear();
        _exerciseStartTime = DateTime.now();
      });

      _animationController.reset();
      _animationController.forward();

      // Add encouraging message
      final encouragements = [
        'Great! Let\'s continue with the next word. You\'re doing well!',
        'Nice progress! Ready for the next challenge?',
        'Keep it up! The next word is coming up.',
        'You\'re building your vocabulary nicely! Next word...',
      ];

      _addTrainerMessage(
        encouragements[currentWordIndex % encouragements.length],
        AITrainerMessageType.encouragement,
      );
    }
  }

  void _completeExercise() async {
    final percentage = (score / widget.exercise.words.length * 100).round();

    // Calculate final points - use backend total if available, otherwise calculate
    final pointsEarned = totalPointsEarned > 0
        ? totalPointsEarned
        : (score *
              (widget.exercise.points ~/
                  widget.exercise.words.length.clamp(1, 100)));

    // Generate completion message based on performance
    String completionMessage;
    if (percentage >= 90) {
      completionMessage = '🌟 Outstanding! You\'re mastering this vocabulary!';
    } else if (percentage >= 70) {
      completionMessage =
          '👏 Great work! Keep practicing to improve even more!';
    } else if (percentage >= 50) {
      completionMessage =
          '💪 Good effort! Review these words to strengthen your memory.';
    } else {
      completionMessage = '📚 Keep learning! Practice makes perfect.';
    }

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('🎉 Exercise Complete!', textAlign: TextAlign.center),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'You scored $score out of ${widget.exercise.words.length}!',
              style: const TextStyle(fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: percentage / 100,
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(
                  percentage >= 70 ? Colors.green : Colors.orange,
                ),
                minHeight: 12,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '$percentage%',
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: percentage >= 70 ? Colors.green : Colors.orange,
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.purple.withValues(alpha: 0.2),
                    Colors.purple.withValues(alpha: 0.1),
                  ],
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.star, color: Colors.amber, size: 28),
                      const SizedBox(width: 8),
                      Text(
                        '+$pointsEarned',
                        style: const TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.bold,
                          color: Colors.purple,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Points Earned',
                    style: TextStyle(color: Colors.purple),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                completionMessage,
                style: const TextStyle(
                  fontWeight: FontWeight.w500,
                  color: Colors.blue,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
        actions: [
          Row(
            children: [
              Expanded(
                child: TextButton(
                  onPressed: () async {
                    final total = widget.exercise.words.length;
                    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;

                    if (exerciseId <= 0) {
                      final seconds = _exerciseStartTime != null
                          ? DateTime.now()
                                .difference(_exerciseStartTime!)
                                .inSeconds
                          : 60;
                      final minutes = (seconds / 60).ceil().clamp(1, 999);
                      final accuracy = total > 0
                          ? (score / total).clamp(0.0, 1.0)
                          : 0.0;
                      await _progressRepository.updateDailyProgress(
                        studyTimeMinutes: minutes,
                        exercisesCompleted: 1,
                        pointsEarned: pointsEarned,
                        accuracyRate: accuracy,
                      );
                    }

                    if (!context.mounted) return;
                    Navigator.of(context).pop();
                    Navigator.of(context).pop({
                      'completed': true,
                      'score': score,
                      'total': total,
                      'points': pointsEarned,
                      'refresh': true,
                      'accuracy_rate': total > 0
                          ? (score / total).clamp(0.0, 1.0)
                          : 0.0,
                    });
                  },
                  child: const Text('Back to Practice'),
                ),
              ),
              Expanded(
                child: ElevatedButton(
                  onPressed: () async {
                    final total = widget.exercise.words.length;
                    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;

                    if (exerciseId <= 0) {
                      final seconds = _exerciseStartTime != null
                          ? DateTime.now()
                                .difference(_exerciseStartTime!)
                                .inSeconds
                          : 60;
                      final minutes = (seconds / 60).ceil().clamp(1, 999);
                      final accuracy = total > 0
                          ? (score / total).clamp(0.0, 1.0)
                          : 0.0;
                      await _progressRepository.updateDailyProgress(
                        studyTimeMinutes: minutes,
                        exercisesCompleted: 1,
                        pointsEarned: pointsEarned,
                        accuracyRate: accuracy,
                      );
                    }

                    if (!context.mounted) return;
                    Navigator.of(context).pop();
                    Navigator.of(context).pop({
                      'completed': true,
                      'score': score,
                      'total': total,
                      'points': pointsEarned,
                      'accuracy_rate': total > 0
                          ? (score / total).clamp(0.0, 1.0)
                          : 0.0,
                    });
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.purple,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text('Continue'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _speakWord(String word) async {
    HapticFeedback.selectionClick();

    if (_isSpeaking) {
      await _flutterTts.stop();
      return;
    }

    try {
      await _flutterTts.speak(word);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not play pronunciation: $e'),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    }
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

  bool _checkAnswer(VocabularyWord word, String answer) {
    switch (widget.exercise.exerciseType) {
      case VocabularyExerciseType.multipleChoice:
      case VocabularyExerciseType.matching:
        final expected = (word.correctAnswer ?? word.definition).trim();
        if (expected.isEmpty) return false;
        return _normalized(answer) == _normalized(expected);
      case VocabularyExerciseType.fillInTheBlanks:
        return _normalized(answer) == _normalized(word.word);
      case VocabularyExerciseType.wordBuilding:
        return _normalized(answer).contains(_normalized(word.word));
    }
  }

  String _normalized(String value) => value.trim().toLowerCase();

  String _resolveCorrectAnswer(int index, VocabularyWord word) {
    final override = _correctAnswersByIndex[index]?.trim();
    if (override != null && override.isNotEmpty) return override;
    return (word.correctAnswer ?? word.definition).trim();
  }

  String _resolveExplanation(int index, VocabularyWord word) {
    final override = _explanationsByIndex[index]?.trim();
    if (override != null && override.isNotEmpty) return override;
    return word.exampleSentence.trim();
  }

  List<String> _generateOptions(VocabularyWord correctWord) {
    final correct = (correctWord.correctAnswer ?? correctWord.definition)
        .trim();
    final options = <String>[];
    if (correct.isNotEmpty) options.add(correct);

    // First, try to use definitions from other words in the exercise
    final otherWords = widget.exercise.words
        .where((w) => w.word != correctWord.word && w.definition.isNotEmpty)
        .toList();

    if (otherWords.isNotEmpty) {
      otherWords.shuffle();
      for (final word in otherWords.take(3)) {
        final def = word.definition.trim();
        if (def.isNotEmpty && !options.contains(def)) {
          options.add(def);
        }
      }
    }

    // If still need more options, add contextual distractors
    if (options.length < 4) {
      final fallbackOptions = _generateContextualDistractors(correctWord);
      for (final opt in fallbackOptions) {
        if (options.length >= 4) break;
        if (!options.contains(opt)) {
          options.add(opt);
        }
      }
    }

    options.shuffle();
    return options.take(4).toList();
  }

  List<String> _generateMatchingOptions(VocabularyWord correctWord) {
    final correct = (correctWord.correctAnswer ?? correctWord.definition)
        .trim();
    final options = <String>[];
    if (correct.isNotEmpty) options.add(correct);

    // Use other words from exercise first
    final otherWords = widget.exercise.words
        .where((w) => w.word != correctWord.word && w.definition.isNotEmpty)
        .toList();

    if (otherWords.isNotEmpty) {
      otherWords.shuffle();
      for (final word in otherWords.take(3)) {
        final def = word.definition.trim();
        if (def.isNotEmpty && !options.contains(def)) {
          options.add(def);
        }
      }
    }

    // Fallback if needed
    if (options.length < 4) {
      final fallbackOptions = _generateContextualDistractors(correctWord);
      for (final opt in fallbackOptions) {
        if (options.length >= 4) break;
        if (!options.contains(opt)) {
          options.add(opt);
        }
      }
    }

    options.shuffle();
    return options.take(4).toList();
  }

  /// Generate contextual distractors based on word type/content
  List<String> _generateContextualDistractors(VocabularyWord word) {
    // Common plausible wrong definitions grouped by type
    final distractors = <String>[
      'A common object used in daily life',
      'An action performed regularly',
      'A quality or characteristic',
      'A feeling or emotional state',
      'A type of relationship between people',
      'A measurement or quantity',
      'A place where activities occur',
      'A process that takes time',
      'Something that affects others',
      'A tool for communication',
    ];

    distractors.shuffle();
    return distractors;
  }

  String _createSentenceWithBlank(String sentence, String word) {
    // Case-insensitive replacement
    final pattern = RegExp(RegExp.escape(word), caseSensitive: false);
    return sentence.replaceFirst(pattern, '________');
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
        return [const Color(0xFF9C27B0), const Color(0xFFE91E63)];
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
