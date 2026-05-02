import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../data/models/exercise_models.dart';
import '../../data/repositories/practice_repository.dart';
import '../../../progress/data/repositories/progress_repository.dart';

class GrammarExercisePage extends StatefulWidget {
  final GrammarExercise exercise;

  const GrammarExercisePage({super.key, required this.exercise});

  @override
  State<GrammarExercisePage> createState() => _GrammarExercisePageState();
}

class _GrammarExercisePageState extends State<GrammarExercisePage> {
  late PracticeRepositoryImpl _repository;
  late final ProgressRepository _progressRepository;
  
  int currentQuestionIndex = 0;
  String? selectedOption;
  bool isAnswered = false;
  bool isLoading = false;
  int score = 0;
  int totalPointsEarned = 0;
  DateTime? _exerciseStartTime;
  List<AITrainerMessage> trainerMessages = [];
  
  // Rich AI feedback state
  GrammarAssessmentResult? _assessmentResult;
  bool? _answerWasCorrect;
  String? _revealedCorrectAnswer;
  String? _revealedExplanation;
  final TextEditingController _textAnswerController = TextEditingController();

  @override
  void initState() {
    super.initState();
    final apiClient = ApiClient(SecureStorage());
    _repository = PracticeRepositoryImpl(apiClient);
    _progressRepository = ProgressRepositoryImpl(apiClient);
    _exerciseStartTime = DateTime.now();
    
    _addTrainerMessage(
      'Let\'s practice grammar! Read each question carefully and answer (choose an option or type the missing word).',
      AITrainerMessageType.welcome,
    );
  }

  @override
  void dispose() {
    _textAnswerController.dispose();
    super.dispose();
  }

  void _addTrainerMessage(String message, AITrainerMessageType type) {
    setState(() {
      trainerMessages.add(AITrainerMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        message: message,
        type: type,
        timestamp: DateTime.now(),
      ));
      if (trainerMessages.length > 2) {
        trainerMessages.removeAt(0);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final question = widget.exercise.questions[currentQuestionIndex];
    final totalQuestions = widget.exercise.questions.length;
    final displayCorrectAnswer =
        (_revealedCorrectAnswer != null && _revealedCorrectAnswer!.trim().isNotEmpty)
            ? _revealedCorrectAnswer!.trim()
            : question.correctAnswer;
    final isFillBlank = question.options.isEmpty;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.exercise.title),
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Chip(
              backgroundColor: Colors.white.withValues(alpha: 0.15),
              label: Text(
                '${currentQuestionIndex + 1}/$totalQuestions',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
      body: Container(
        color: Colors.grey[50],
        child: Column(
          children: [
            LinearProgressIndicator(
              value: (currentQuestionIndex + 1) / totalQuestions,
              backgroundColor: Colors.grey[200],
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.blue),
              minHeight: 4,
            ),
            // AI Trainer Messages
            if (trainerMessages.isNotEmpty)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: _buildTrainerMessage(trainerMessages.last),
              ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _buildGrammarOverview(),
                    const SizedBox(height: 16),
                    _buildQuestionCard(question),
                    const SizedBox(height: 12),
                    if (isFillBlank) ...[
                      _buildTextAnswerInput(),
                    ] else ...[
                      ...question.options.map(
                        (option) => _buildOption(option, displayCorrectAnswer),
                      ),
                    ],
                    if (isAnswered) ...[
                      const SizedBox(height: 16),
                      _buildFeedback(question),
                    ],
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: isLoading ? null : (isAnswered ? _goNext : _submitAnswer),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isAnswered ? Colors.green : Colors.blue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
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
                      : Text(isAnswered ? _ctaLabel(totalQuestions) : 'Check Answer'),
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
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: _getMessageGradient(message.type),
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(
            _getMessageIcon(message.type),
            color: Colors.white,
            size: 18,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message.message,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
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
        return [const Color(0xFF2196F3), const Color(0xFF03A9F4)];
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

  Widget _buildGrammarOverview() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.blue.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.rule, color: Colors.blue),
              SizedBox(width: 8),
              Text(
                'Grammar Focus',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Colors.blue,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            widget.exercise.grammarRule.isNotEmpty
                ? widget.exercise.grammarRule
                : widget.exercise.title,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            widget.exercise.explanation.isNotEmpty
                ? widget.exercise.explanation
                : widget.exercise.description,
            style: TextStyle(
              color: Colors.grey[800],
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuestionCard(GrammarQuestion question) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.blue.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'Question ${currentQuestionIndex + 1}',
                  style: const TextStyle(
                    color: Colors.blue,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.amber.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.star, color: Colors.amber, size: 14),
                    const SizedBox(width: 4),
                    Text(
                      '+${widget.exercise.points ~/ widget.exercise.questions.length}',
                      style: const TextStyle(
                        color: Colors.amber,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            question.question,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOption(String option, String correctAnswer) {
    final isSelected = selectedOption == option;
    final isCorrect = option == correctAnswer;

    Color borderColor;
    Color fillColor = Colors.white;

    if (isAnswered) {
      if (isCorrect) {
        borderColor = Colors.green;
        fillColor = Colors.green.withValues(alpha: 0.08);
      } else if (isSelected) {
        borderColor = Colors.red;
        fillColor = Colors.red.withValues(alpha: 0.08);
      } else {
        borderColor = Colors.grey[300]!;
      }
    } else {
      borderColor = isSelected ? Colors.blue : Colors.grey[300]!;
      if (isSelected) {
        fillColor = Colors.blue.withValues(alpha: 0.08);
      }
    }

    return GestureDetector(
      onTap: isAnswered ? null : () => setState(() => selectedOption = option),
      child: Container(
        margin: const EdgeInsets.only(top: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: fillColor,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor, width: 2),
        ),
        child: Row(
          children: [
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                color: isSelected ? borderColor : Colors.grey[200],
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(
                isAnswered && isCorrect
                    ? Icons.check
                    : isAnswered && isSelected && !isCorrect
                        ? Icons.close
                        : isSelected
                            ? Icons.radio_button_checked
                            : Icons.circle_outlined,
                size: 16,
                color: isSelected || (isAnswered && isCorrect) ? Colors.white : Colors.grey[600],
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                option,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeedback(GrammarQuestion question) {
    final isCorrect = _answerWasCorrect ?? (selectedOption == question.correctAnswer);
    final assessment = _assessmentResult;
    final correctAnswer =
        (_revealedCorrectAnswer != null && _revealedCorrectAnswer!.trim().isNotEmpty)
            ? _revealedCorrectAnswer!.trim()
            : question.correctAnswer;
    final fallbackExplanation =
        (_revealedExplanation != null && _revealedExplanation!.trim().isNotEmpty)
            ? _revealedExplanation!.trim()
            : question.explanation;

    return Column(
      children: [
        // Main feedback card
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: isCorrect
                ? Colors.green.withValues(alpha: 0.1)
                : Colors.orange.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isCorrect ? Colors.green : Colors.orange,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    isCorrect ? Icons.check_circle : Icons.info,
                    color: isCorrect ? Colors.green : Colors.orange,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    isCorrect ? 'Excellent! 🎉' : 'Let\'s review',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: isCorrect ? Colors.green : Colors.orange,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.check,
                      color: Colors.green[700],
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        correctAnswer.trim().isNotEmpty
                            ? 'Correct answer: $correctAnswer'
                            : 'Answer checked',
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: Colors.green[700],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Text(
                assessment?.explanation ?? 
                    (fallbackExplanation.isNotEmpty 
                        ? fallbackExplanation
                        : 'Keep practicing to master this grammar pattern!'),
                style: TextStyle(color: Colors.grey[800], height: 1.5, fontSize: 15),
              ),
              // Why wrong - only show if incorrect
              if (!isCorrect && assessment?.whyWrong != null && assessment!.whyWrong!.isNotEmpty) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.warning_amber, color: Colors.red[700], size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          assessment.whyWrong!,
                          style: TextStyle(color: Colors.red[800], height: 1.4),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        
        // Grammar Rule Card
        if (assessment?.ruleExplanation != null && assessment!.ruleExplanation.isNotEmpty) ...[
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.blue.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.school, color: Colors.blue[700], size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Grammar Rule',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.blue[700],
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  assessment.ruleExplanation,
                  style: TextStyle(color: Colors.grey[800], height: 1.5),
                ),
              ],
            ),
          ),
        ],
        
        // Examples Card
        if (assessment?.examples != null && assessment!.examples.isNotEmpty) ...[
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.purple.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.purple.withValues(alpha: 0.2)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.format_quote, color: Colors.purple[700], size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Examples',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.purple[700],
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                ...assessment.examples.map((example) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('• ', style: TextStyle(color: Colors.purple[700], fontSize: 16)),
                      Expanded(
                        child: Text(
                          example,
                          style: TextStyle(
                            color: Colors.grey[800],
                            height: 1.4,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ),
                    ],
                  ),
                )),
              ],
            ),
          ),
        ],
        
        // Common Mistakes Card
        if (assessment?.commonMistakes != null && assessment!.commonMistakes.isNotEmpty) ...[
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.amber.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.amber.withValues(alpha: 0.3)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.lightbulb, color: Colors.amber[700], size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Common Mistakes to Avoid',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.amber[800],
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                ...assessment.commonMistakes.map((mistake) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.close, color: Colors.amber[700], size: 16),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          mistake,
                          style: TextStyle(color: Colors.grey[800], height: 1.4),
                        ),
                      ),
                    ],
                  ),
                )),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildTextAnswerInput() {
    final question = widget.exercise.questions[currentQuestionIndex];
    final userAnswer = selectedOption?.trim() ?? '';
    final displayCorrectAnswer =
        (_revealedCorrectAnswer != null && _revealedCorrectAnswer!.trim().isNotEmpty)
            ? _revealedCorrectAnswer!.trim()
            : question.correctAnswer;
    final isCorrect = _answerWasCorrect ?? false;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isAnswered
              ? (isCorrect ? Colors.green : Colors.red)
              : Colors.grey[300]!,
          width: 2,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isAnswered
                    ? (isCorrect ? Icons.check_circle : Icons.cancel)
                    : Icons.edit,
                size: 18,
                color: isAnswered
                    ? (isCorrect ? Colors.green : Colors.red)
                    : Colors.blue[700],
              ),
              const SizedBox(width: 8),
              Text(
                isAnswered
                    ? (isCorrect ? 'Correct!' : 'Not quite right')
                    : 'Type your answer',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: isAnswered
                      ? (isCorrect ? Colors.green : Colors.red)
                      : Colors.blue[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _textAnswerController,
            enabled: !isAnswered && !isLoading,
            onChanged: (value) => setState(() => selectedOption = value),
            decoration: InputDecoration(
              hintText: 'Enter the missing word/phrase',
              filled: true,
              fillColor: isAnswered
                  ? (isCorrect
                      ? Colors.green.withValues(alpha: 0.05)
                      : Colors.red.withValues(alpha: 0.05))
                  : Colors.grey[50],
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(
                  color: isAnswered
                      ? (isCorrect ? Colors.green : Colors.red)
                      : Colors.grey[300]!,
                ),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(
                  color: isAnswered
                      ? (isCorrect ? Colors.green : Colors.red)
                      : Colors.grey[300]!,
                ),
              ),
              disabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(
                  color: isCorrect ? Colors.green : Colors.red,
                  width: 2,
                ),
              ),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              suffixIcon: isAnswered
                  ? Icon(
                      isCorrect ? Icons.check_circle : Icons.cancel,
                      color: isCorrect ? Colors.green : Colors.red,
                    )
                  : null,
            ),
          ),
          // Show feedback for fill-in-the-blank after answering
          if (isAnswered) ...[
            const SizedBox(height: 12),
            _buildFillBlankFeedback(userAnswer, displayCorrectAnswer, isCorrect),
          ],
        ],
      ),
    );
  }

  /// Build feedback widget for fill-in-the-blank grammar exercises
  Widget _buildFillBlankFeedback(String userAnswer, String correctAnswer, bool isCorrect) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isCorrect
            ? Colors.green.withValues(alpha: 0.1)
            : Colors.orange.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isCorrect ? Colors.green : Colors.orange,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // User's answer
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                isCorrect ? Icons.check : Icons.close,
                color: isCorrect ? Colors.green : Colors.red,
                size: 18,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: RichText(
                  text: TextSpan(
                    style: TextStyle(fontSize: 14, color: Colors.grey[800]),
                    children: [
                      const TextSpan(
                        text: 'Your answer: ',
                        style: TextStyle(fontWeight: FontWeight.w500),
                      ),
                      TextSpan(
                        text: userAnswer.isNotEmpty ? '"$userAnswer"' : '(empty)',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: isCorrect ? Colors.green[700] : Colors.red[700],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          // Show correct answer if wrong
          if (!isCorrect && correctAnswer.isNotEmpty) ...[
            const SizedBox(height: 8),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.check, color: Colors.green[700], size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: RichText(
                    text: TextSpan(
                      style: TextStyle(fontSize: 14, color: Colors.grey[800]),
                      children: [
                        const TextSpan(
                          text: 'Correct answer: ',
                          style: TextStyle(fontWeight: FontWeight.w500),
                        ),
                        TextSpan(
                          text: '"$correctAnswer"',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.green[700],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  String _extractCorrectAnswer(Map<String, dynamic>? correctAnswer) {
    if (correctAnswer == null) return '';
    final direct = correctAnswer['correct_option'] ?? correctAnswer['text'];
    if (direct != null) return direct.toString();
    if (correctAnswer.isNotEmpty) {
      return correctAnswer.values.first.toString();
    }
    return '';
  }

  bool _isAnswerCorrectLocal(GrammarQuestion question, String answer) {
    final a = answer.trim().toLowerCase();
    if (a.isEmpty) return false;
    final correct = question.correctAnswer.trim().toLowerCase();
    if (correct.isEmpty) return false;

    // Support multiple acceptable answers: "a|b|c" or "a/b/c" or "a, b, c"
    final candidates = correct
        .split(RegExp(r'[|/,]'))
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toSet();

    if (candidates.isEmpty) return a == correct;
    return candidates.contains(a);
  }

  void _submitAnswer() async {
    // For fill-blank, keep selectedOption in sync with the text field.
    if (widget.exercise.questions[currentQuestionIndex].options.isEmpty) {
      selectedOption = _textAnswerController.text;
    }

    final answer = selectedOption?.trim() ?? '';
    if (answer.isEmpty) return;

    setState(() {
      isLoading = true;
      _assessmentResult = null;
      _answerWasCorrect = null;
      _revealedCorrectAnswer = null;
      _revealedExplanation = null;
    });

    final question = widget.exercise.questions[currentQuestionIndex];
    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;

    bool isCorrect;
    String correctAnswerForAi = question.correctAnswer;

    // If this is a DB-backed exercise, submit first to reveal correct answer + explanation.
    if (exerciseId > 0) {
      try {
        final timeTaken = _exerciseStartTime != null
            ? DateTime.now().difference(_exerciseStartTime!).inSeconds
            : null;

        final userAnswerPayload = question.options.isEmpty
            ? {
                'text': answer,
                'question_id': question.id,
                'question_index': currentQuestionIndex,
              }
            : {
                'selected': answer,
                'question_id': question.id,
                'question_index': currentQuestionIndex,
              };

        final result = await _repository.submitExercise(
          exerciseId: exerciseId,
          userAnswer: userAnswerPayload,
          timeTakenSeconds: timeTaken,
        );

        isCorrect = result.isCorrect;

        if (result.pointsEarned > 0) {
          totalPointsEarned += result.pointsEarned;
        }

        final serverCorrect = _extractCorrectAnswer(result.correctAnswer);
        if (serverCorrect.trim().isNotEmpty) {
          _revealedCorrectAnswer = serverCorrect.trim();
          correctAnswerForAi = serverCorrect.trim();
        }

        if (result.explanation != null && result.explanation!.trim().isNotEmpty) {
          _revealedExplanation = result.explanation!.trim();
        }
      } catch (e) {
        debugPrint('Failed to submit answer: $e');
        // Fallback to local correctness if server submission fails.
        isCorrect = _isAnswerCorrectLocal(question, answer);
      }
    } else {
      // Cached / generated exercises include correct answer.
      isCorrect = _isAnswerCorrectLocal(question, answer);
    }

    // Get AI assessment for rich feedback (now with the correct answer if we have it).
    try {
      final assessment = await _repository.assessGrammarAnswer(
        question: question.question,
        selectedAnswer: answer,
        correctAnswer: correctAnswerForAi,
        options: question.options,
        grammarRule: widget.exercise.grammarRule.isNotEmpty
            ? widget.exercise.grammarRule
            : widget.exercise.title,
        userLevel: widget.exercise.level.name.toUpperCase(),
      );
      _assessmentResult = assessment;
    } catch (e) {
      debugPrint('Failed to get AI assessment: $e');
      _assessmentResult = GrammarAssessmentResult.fallback(
        isCorrect: isCorrect,
        correctAnswer: correctAnswerForAi,
      );
    }

    if (!mounted) return;
    setState(() {
      isAnswered = true;
      isLoading = false;
      _answerWasCorrect = isCorrect;
      if (isCorrect) score++;
    });

    // Add trainer feedback
    if (isCorrect) {
      _addTrainerMessage(
        _assessmentResult?.tip ?? 'Perfect! You understand this grammar pattern well. Keep it up!',
        AITrainerMessageType.celebration,
      );
    } else {
      _addTrainerMessage(
        _assessmentResult?.tip ?? 'Don\'t worry! Review the explanation and you\'ll get it next time.',
        AITrainerMessageType.correction,
      );
    }

    HapticFeedback.lightImpact();
  }

  void _goNext() {
    final isLast = currentQuestionIndex >= widget.exercise.questions.length - 1;
    if (isLast) {
      _showCompletionDialog();
      return;
    }

    setState(() {
      currentQuestionIndex++;
      selectedOption = null;
      isAnswered = false;
      _assessmentResult = null;
      _answerWasCorrect = null;
      _revealedCorrectAnswer = null;
      _revealedExplanation = null;
    });
    _textAnswerController.clear();

    _addTrainerMessage(
      'Great progress! Let\'s try the next question.',
      AITrainerMessageType.encouragement,
    );
  }

  String _ctaLabel(int total) {
    final isLast = currentQuestionIndex >= total - 1;
    return isLast ? 'Complete Lesson' : 'Next Question';
  }

  void _showCompletionDialog() {
    final total = widget.exercise.questions.length;
    final percentage = ((score / total) * 100).round();
    
    final pointsEarned = totalPointsEarned > 0 
        ? totalPointsEarned 
        : (score * (widget.exercise.points ~/ total.clamp(1, 100)));

    String completionMessage;
    if (percentage >= 90) {
      completionMessage = '🌟 Outstanding! You\'ve mastered this grammar topic!';
    } else if (percentage >= 70) {
      completionMessage = '👏 Great work! You\'re getting the hang of it!';
    } else if (percentage >= 50) {
      completionMessage = '💪 Good effort! Review and try again to improve.';
    } else {
      completionMessage = '📚 Keep learning! Practice makes perfect.';
    }

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('🎉 Lesson Complete!', textAlign: TextAlign.center),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'You answered $score out of $total correctly!',
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
                  colors: [Colors.blue.withValues(alpha: 0.2), Colors.blue.withValues(alpha: 0.1)],
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
                          color: Colors.blue,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Points Earned',
                    style: TextStyle(color: Colors.blue),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                completionMessage,
                style: const TextStyle(
                  fontWeight: FontWeight.w500,
                  color: Colors.green,
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
                    // Persist progress for generated (non-DB) exercises even if user exits here.
                    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;
                    if (exerciseId <= 0) {
                      final seconds = _exerciseStartTime != null
                          ? DateTime.now().difference(_exerciseStartTime!).inSeconds
                          : 60;
                      final minutes = (seconds / 60).ceil().clamp(1, 999);
                      final accuracy = total > 0 ? (score / total).clamp(0.0, 1.0) : 0.0;
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
                      'accuracy_rate': total > 0 ? (score / total).clamp(0.0, 1.0) : 0.0,
                    });
                  },
                  child: const Text('Back to Practice'),
                ),
              ),
              Expanded(
                child: ElevatedButton(
                  onPressed: () async {
                    // Persist progress for generated (non-DB) exercises so points aren't lost.
                    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;
                    if (exerciseId <= 0) {
                      final seconds = _exerciseStartTime != null
                          ? DateTime.now().difference(_exerciseStartTime!).inSeconds
                          : 60;
                      final minutes = (seconds / 60).ceil().clamp(1, 999);
                      final accuracy = total > 0 ? (score / total).clamp(0.0, 1.0) : 0.0;
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
                      'accuracy_rate': total > 0 ? (score / total).clamp(0.0, 1.0) : 0.0,
                    });
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
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
}
