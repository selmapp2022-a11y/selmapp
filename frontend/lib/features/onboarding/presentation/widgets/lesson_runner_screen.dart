import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:universal_io/io.dart' as io;

import '../../../../core/api/speaking_api.dart';
import '../../../../core/config/app_environment.dart';
import '../../../../core/models/speaking_models.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../../speaking/recording_controller.dart';
import '../../data/models/onboarding_models.dart';
import '../../data/repositories/onboarding_repository.dart';

class LessonRunnerScreen extends StatefulWidget {
  final LessonSession session;

  const LessonRunnerScreen({super.key, required this.session});

  @override
  State<LessonRunnerScreen> createState() => _LessonRunnerScreenState();
}

class _LessonRunnerScreenState extends State<LessonRunnerScreen> {
  int _currentIndex = 0;
  // Track accumulated progress across the entire session
  int _sessionCorrect = 0;
  int _sessionTotal = 0;

  // Track per-step completion status
  final Map<int, bool> _stepCompleted = {};

  // Track current step state
  final Map<int, int> _currentStepAnswers =
      {}; // {questionIndex: selectedOptionIndex}
  bool _showTranscript = false;

  final Stopwatch _stopwatch = Stopwatch();
  final AudioPlayer _player = AudioPlayer();
  // Speaking state
  bool _speakingAnalyzing = false;
  double? _speakingOverall;
  String? _speakingFeedback;
  SpeechEvaluateResponseModel? _speakingResult;

  // Check if there's a dedicated vocabulary step to avoid showing duplicate vocabulary in reading
  bool get _hasDedicatedVocabStep =>
      widget.session.steps.any((s) => s.stepType == 'vocabulary');

  // Check if vocabulary step comes BEFORE current index (already shown)
  bool get _vocabStepAlreadyShown {
    final vocabIndex = widget.session.steps.indexWhere(
      (s) => s.stepType == 'vocabulary',
    );
    return vocabIndex >= 0 && vocabIndex < _currentIndex;
  }

  // Track unique vocabulary words shown in the session to prevent duplicates
  final Set<String> _shownVocabularyWords = {};

  @override
  void initState() {
    super.initState();
    // Explicitly set playback speed to 1.0x to prevent fast-forward on some Android devices
    _player.setSpeed(1.0);
    // Clear vocabulary tracking at start of each session
    _shownVocabularyWords.clear();
  }

  @override
  void dispose() {
    _stopwatch.stop();
    _player.dispose();
    super.dispose();
  }

  void _resetStepState() {
    _currentStepAnswers.clear();
    _showTranscript = false;
    _speakingOverall = null;
    _speakingFeedback = null;
    _speakingAnalyzing = false;
    _speakingResult = null;
  }

  @override
  Widget build(BuildContext context) {
    if (!_stopwatch.isRunning) _stopwatch.start();
    final step = widget.session.steps[_currentIndex];

    // Get step color based on type
    final stepColor = _getStepColor(step.stepType);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.close, color: Colors.black87),
          onPressed: () => _showExitConfirmation(context),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Day ${widget.session.dayNumber}',
              style: const TextStyle(
                fontSize: 14,
                color: Colors.black54,
                fontWeight: FontWeight.normal,
              ),
            ),
            Text(
              step.title,
              style: const TextStyle(
                fontSize: 16,
                color: Colors.black87,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        actions: [
          // Progress indicator
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: Text(
                '${_currentIndex + 1}/${widget.session.steps.length}',
                style: TextStyle(
                  color: Colors.grey[600],
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Progress bar
          Container(
            height: 4,
            color: Colors.grey[200],
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: (_currentIndex + 1) / widget.session.steps.length,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [stepColor, stepColor.withValues(alpha: 0.7)],
                  ),
                ),
              ),
            ),
          ),

          // Step type indicator
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            color: Colors.white,
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: stepColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _getStepIcon(step.stepType),
                        size: 16,
                        color: stepColor,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        _getStepLabel(step.stepType),
                        style: TextStyle(
                          color: stepColor,
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
                const Spacer(),
                Icon(Icons.timer_outlined, size: 16, color: Colors.grey[500]),
                const SizedBox(width: 4),
                Text(
                  '${step.estimatedMinutes} min',
                  style: TextStyle(color: Colors.grey[600], fontSize: 13),
                ),
              ],
            ),
          ),

          // Content
          Expanded(child: _buildStepContent(step)),

          // Navigation
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 10,
                  offset: const Offset(0, -4),
                ),
              ],
            ),
            child: SafeArea(
              child: Row(
                children: [
                  if (_currentIndex > 0)
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () async {
                          await _stopAudioPlayback();
                          if (!mounted) return;
                          setState(() => _currentIndex -= 1);
                        },
                        icon: const Icon(Icons.arrow_back_rounded),
                        label: const Text('Back'),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      ),
                    ),
                  if (_currentIndex > 0) const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [stepColor, stepColor.withValues(alpha: 0.8)],
                        ),
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [
                          BoxShadow(
                            color: stepColor.withValues(alpha: 0.3),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: ElevatedButton.icon(
                        onPressed: () async => _onNext(),
                        icon: Icon(
                          _currentIndex == widget.session.steps.length - 1
                              ? Icons.check_circle_rounded
                              : Icons.arrow_forward_rounded,
                        ),
                        label: Text(
                          _currentIndex == widget.session.steps.length - 1
                              ? 'Complete'
                              : 'Continue',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.transparent,
                          foregroundColor: Colors.white,
                          shadowColor: Colors.transparent,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
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

  Color _getStepColor(String stepType) {
    switch (stepType) {
      case 'listening':
        return const Color(0xFF3B82F6);
      case 'reading':
        return const Color(0xFF10B981);
      case 'speaking':
        return const Color(0xFFF59E0B);
      case 'vocabulary':
        return const Color(0xFFEC4899);
      case 'grammar':
      case 'exercise':
      case 'quiz':
        return const Color(0xFF6366F1);
      default:
        return const Color(0xFF6366F1);
    }
  }

  IconData _getStepIcon(String stepType) {
    switch (stepType) {
      case 'listening':
        return Icons.headphones_rounded;
      case 'reading':
        return Icons.menu_book_rounded;
      case 'speaking':
        return Icons.mic_rounded;
      case 'vocabulary':
        return Icons.abc_rounded;
      case 'grammar':
        return Icons.rule_rounded;
      case 'exercise':
      case 'quiz':
        return Icons.quiz_rounded;
      default:
        return Icons.dashboard_rounded;
    }
  }

  String _getStepLabel(String stepType) {
    switch (stepType) {
      case 'listening':
        return 'Listening';
      case 'reading':
        return 'Reading';
      case 'speaking':
        return 'Speaking';
      case 'vocabulary':
        return 'Vocabulary';
      case 'grammar':
        return 'Grammar';
      case 'exercise':
        return 'Exercise';
      case 'quiz':
        return 'Quiz';
      default:
        return 'Practice';
    }
  }

  void _showExitConfirmation(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Leave Lesson?'),
        content: const Text(
          'Your progress will be saved, but you\'ll need to complete this lesson to unlock the next day.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Continue Lesson'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              _saveProgressAndExit();
            },
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Leave'),
          ),
        ],
      ),
    );
  }

  Future<void> _saveProgressAndExit() async {
    // Save partial progress
    try {
      final minutes = (_stopwatch.elapsed.inSeconds / 60).clamp(1, 180).round();
      final repo = context.read<OnboardingRepository>();
      await repo.saveStepProgress(
        sessionId: widget.session.sessionId,
        moduleId: widget.session.moduleId,
        dayNumber: widget.session.dayNumber,
        stepIndex: _currentIndex,
        correct: _sessionCorrect,
        total: _sessionTotal,
        timeSpentMinutes: minutes,
      );
    } catch (_) {}

    if (!mounted) return;
    Navigator.of(context).pop({'partial': true});
  }

  Widget _buildStepContent(LessonStep step) {
    switch (step.stepType) {
      case 'reading':
        return _buildReadingStep(step);
      case 'listening':
        return _buildListeningStep(step);
      case 'vocabulary':
        return _buildVocabularyStep(step);
      case 'grammar':
        return _buildGrammarStep(step);
      case 'exercise':
      case 'quiz':
        return _buildQuizStep(step);
      case 'speaking':
        final prompt =
            step.contentJson?['prompt_text']?.toString() ??
            step.contentJson?['prompt']?.toString() ??
            step.contentJson?['conversation_prompt']?.toString() ??
            step.contentJson?['content']?.toString() ??
            step.contentJson?['text']?.toString() ??
            step.contentJson?['context']?.toString() ??
            step.content ??
            step.title;
        final normalizedPrompt = prompt.trim().isEmpty
            ? 'Share a quick response about ${step.title}.'
            : prompt;
        return _buildSpeakingStep(prompt: normalizedPrompt);
      default:
        return _buildGenericStep(step);
    }
  }

  Widget _buildReadingStep(LessonStep step) {
    List<Map<String, dynamic>> fallbackQuestions() {
      final List<dynamic> raw =
          (step.contentJson?['comprehension_questions'] as List?) ??
          (step.contentJson?['questions'] as List?) ??
          const [];
      return raw
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
    }

    String cleanText(String text) {
      // Clean up common formatting issues
      String cleaned = text
          // Remove markdown code blocks if present
          .replaceAll(RegExp(r'```\w*\n?'), '')
          .replaceAll('```', '')
          // Clean up escaped newlines
          .replaceAll(r'\n', '\n')
          .replaceAll(r'\\n', '\n')
          // Clean up escaped quotes
          .replaceAll(r'\"', '"')
          .replaceAll(r"\'", "'")
          // Remove excessive whitespace
          .replaceAll(RegExp(r'\n{3,}'), '\n\n')
          // Clean up any remaining JSON artifacts
          .replaceAll(RegExp(r'^\s*[\[{]'), '')
          .replaceAll(RegExp(r'[\]}]\s*$'), '')
          .trim();

      // If it still looks like JSON, don't show it
      if (cleaned.startsWith('{') || cleaned.startsWith('[')) {
        return '';
      }

      return cleaned;
    }

    String pickText(dynamic source) {
      if (source == null) return '';
      if (source is String && source.trim().isNotEmpty) {
        return cleanText(source);
      }
      if (source is List) {
        final parts = source
            .map((e) => pickText(e))
            .where((e) => e.trim().isNotEmpty)
            .toList();
        return parts.isNotEmpty ? parts.join('\n\n') : '';
      }
      if (source is Map) {
        // Try specific keys in order of preference
        for (final key in [
          'text',
          'text_content',
          'passage',
          'reading_text',
          'reading_passage',
          'article',
          'story',
          'body',
          'content',
          'paragraphs',
          'paragraph',
          'value',
          'data',
          'description',
        ]) {
          final picked = pickText(source[key]);
          if (picked.trim().isNotEmpty) return picked;
        }
        // Try 'lesson' nested object
        if (source['lesson'] is Map) {
          final lessonPicked = pickText(source['lesson']);
          if (lessonPicked.trim().isNotEmpty) return lessonPicked;
        }
      }
      return '';
    }

    bool looksLikeJson(String value) {
      final trimmed = value.trim();
      return (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
          (trimmed.startsWith('[') && trimmed.endsWith(']'));
    }

    LessonStep withQuestions(List<Map<String, dynamic>> q) {
      if (q.isEmpty || (step.questions?.isNotEmpty ?? false)) return step;
      return LessonStep(
        stepType: step.stepType,
        title: step.title,
        content: step.content,
        mediaUrl: step.mediaUrl,
        questions: q,
        estimatedMinutes: step.estimatedMinutes,
        contentJson: step.contentJson,
      );
    }

    final fbQuestionsResult = fallbackQuestions();
    final effectiveStep = withQuestions(fbQuestionsResult);
    final effectiveQuestions = effectiveStep.questions ?? const [];

    // Extract reading text from multiple possible sources
    String readingText = '';

    // Try content first
    if (step.content != null && step.content!.isNotEmpty) {
      readingText = step.content!;
      if (looksLikeJson(readingText)) {
        try {
          final parsed = jsonDecode(readingText);
          readingText = pickText(parsed);
        } catch (_) {}
      } else {
        readingText = cleanText(readingText);
      }
    }

    // Try contentJson
    if (readingText.isEmpty && step.contentJson != null) {
      final cj = step.contentJson!;

      // Try direct text keys
      readingText = pickText(cj);

      // Try content nested object
      if (readingText.trim().isEmpty && cj['content'] != null) {
        readingText = pickText(cj['content']);
      }

      // Try lesson nested object
      if (readingText.trim().isEmpty && cj['lesson'] is Map) {
        readingText = pickText(cj['lesson']);
      }

      // Try reading_content nested
      if (readingText.trim().isEmpty && cj['reading_content'] is Map) {
        readingText = pickText(cj['reading_content']);
      }

      // Try content_json nested (sometimes backend wraps content)
      if (readingText.trim().isEmpty && cj['content_json'] is Map) {
        readingText = pickText(cj['content_json']);
      }
    }

    // Extract vocabulary words - filter out already shown words
    final rawVocab =
        (step.contentJson?['vocabulary_words'] as List?)?.cast<dynamic>() ??
        (step.contentJson?['vocabulary'] as List?)?.cast<dynamic>() ??
        (step.contentJson?['words'] as List?)?.cast<dynamic>() ??
        const [];

    final vocab = <dynamic>[];
    for (final e in rawVocab) {
      final word =
          (e is Map ? e['word']?.toString() : e.toString())?.toLowerCase() ??
          '';
      if (word.isNotEmpty && !_shownVocabularyWords.contains(word)) {
        vocab.add(e);
      }
    }

    // Check if we have questions
    final hasQuestions = effectiveQuestions.isNotEmpty;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Reading content card
          if (readingText.isNotEmpty)
            Container(
              width: double.infinity,
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
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF10B981).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.menu_book_rounded,
                          color: Color(0xFF10B981),
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'Reading Passage',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const Divider(),
                  const SizedBox(height: 16),
                  Text(
                    readingText,
                    style: const TextStyle(
                      fontSize: 16,
                      height: 1.8,
                      color: Colors.black87,
                    ),
                  ),
                ],
              ),
            )
          else
            Container(
              width: double.infinity,
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
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF10B981).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.menu_book_rounded,
                          color: Color(0xFF10B981),
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'Reading Practice',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const Divider(),
                  const SizedBox(height: 16),
                  // Show a default reading passage when API content is unavailable
                  Text(
                    _getDefaultReadingPassage(step.title),
                    style: const TextStyle(
                      fontSize: 16,
                      height: 1.8,
                      color: Colors.black87,
                    ),
                  ),
                ],
              ),
            ),

          // Vocabulary section (skip if there is a dedicated vocab step OR vocab was already shown)
          if (vocab.isNotEmpty &&
              !_hasDedicatedVocabStep &&
              !_vocabStepAlreadyShown) ...[
            const SizedBox(height: 24),
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
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEC4899).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.abc_rounded,
                          color: Color(0xFFEC4899),
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'Key Vocabulary',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: vocab.map((e) {
                      final m = e is Map
                          ? Map<String, dynamic>.from(e)
                          : <String, dynamic>{'word': e.toString()};
                      final word = m['word']?.toString() ?? '';
                      final definition = m['definition']?.toString();

                      return Tooltip(
                        message: definition ?? '',
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(
                              0xFFEC4899,
                            ).withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            word,
                            style: const TextStyle(
                              color: Color(0xFFEC4899),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
          ],

          // Comprehension questions
          if (hasQuestions) ...[
            const SizedBox(height: 24),
            const Text(
              'Comprehension Questions',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            _buildQuestions(effectiveStep, embedded: true),
          ],
        ],
      ),
    );
  }

  Widget _buildListeningStep(LessonStep step) {
    // Get transcript text
    final transcript =
        step.content ??
        step.contentJson?['transcript']?.toString() ??
        step.contentJson?['audio_script']?.toString() ??
        '';

    List<Map<String, dynamic>> listeningFallbackQuestions() {
      final List<dynamic> raw =
          (step.contentJson?['comprehension_questions'] as List?) ??
          (step.contentJson?['questions'] as List?) ??
          const [];
      return raw
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
    }

    final fbQuestions = listeningFallbackQuestions();
    final effectiveStep = (step.questions?.isNotEmpty ?? false)
        ? step
        : LessonStep(
            stepType: step.stepType,
            title: step.title,
            content: step.content,
            mediaUrl: step.mediaUrl,
            questions: fbQuestions,
            estimatedMinutes: step.estimatedMinutes,
            contentJson: step.contentJson,
          );

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Audio player card
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF3B82F6), Color(0xFF2563EB)],
              ),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF3B82F6).withValues(alpha: 0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              children: [
                const Icon(
                  Icons.headphones_rounded,
                  color: Colors.white,
                  size: 48,
                ),
                const SizedBox(height: 16),
                const Text(
                  'Listen to the Audio',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Tap play to start listening',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.8),
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (step.mediaUrl != null) ...[
                      ElevatedButton.icon(
                        onPressed: () async {
                          try {
                            final media = step.mediaUrl!;
                            final absUrl = await _absoluteMediaUrl(media);
                            await _player.stop();

                            if (kIsWeb) {
                              await _player.setUrl(absUrl);
                            } else {
                              final localPath = await _downloadAudioToDevice(
                                absUrl,
                              );
                              await _player.setFilePath(localPath);
                            }

                            await _player.play();
                          } catch (e) {
                            debugPrint('Audio playback error: $e');
                          }
                        },
                        icon: const Icon(Icons.play_arrow_rounded),
                        label: const Text('Play'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: const Color(0xFF3B82F6),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 12,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      OutlinedButton.icon(
                        onPressed: () async {
                          try {
                            await _player.pause();
                          } catch (_) {}
                        },
                        icon: const Icon(Icons.pause_rounded),
                        label: const Text('Pause'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white,
                          side: const BorderSide(color: Colors.white),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 12,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      ),
                    ] else ...[
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.info_outline, color: Colors.white),
                            const SizedBox(width: 8),
                            Text(
                              'Audio unavailable',
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.9),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Transcript section
          if (transcript.isNotEmpty)
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
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Transcript',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      TextButton.icon(
                        onPressed: () =>
                            setState(() => _showTranscript = !_showTranscript),
                        icon: Icon(
                          _showTranscript
                              ? Icons.visibility_off
                              : Icons.visibility,
                        ),
                        label: Text(_showTranscript ? 'Hide' : 'Show'),
                      ),
                    ],
                  ),
                  if (_showTranscript) ...[
                    const Divider(),
                    const SizedBox(height: 12),
                    Text(
                      transcript,
                      style: const TextStyle(
                        fontSize: 15,
                        height: 1.6,
                        color: Colors.black87,
                      ),
                    ),
                  ],
                ],
              ),
            ),

          // Comprehension questions
          if ((effectiveStep.questions ?? const []).isNotEmpty) ...[
            const SizedBox(height: 24),
            const Text(
              'Comprehension',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            _buildQuestions(effectiveStep, embedded: true),
          ],
        ],
      ),
    );
  }

  Widget _buildVocabularyStep(LessonStep step) {
    // Extract vocabulary from multiple possible sources (including new AI format)
    final contentJson = step.contentJson ?? {};
    // These keys may be either a nested Map OR a simple String in some payloads.
    final lessonSection = contentJson['lesson'] is Map
        ? Map<String, dynamic>.from(contentJson['lesson'] as Map)
        : null;
    final contentSection = contentJson['content'] is Map
        ? Map<String, dynamic>.from(contentJson['content'] as Map)
        : null;
    final exerciseSection = contentJson['exercise'] is Map
        ? Map<String, dynamic>.from(contentJson['exercise'] as Map)
        : null;

    // Try multiple possible paths for vocabulary data
    List<dynamic> vocab = const [];

    // Direct vocabulary_words key (most common)
    vocab =
        (contentJson['vocabulary_words'] as List?)?.cast<dynamic>() ?? const [];

    // Fallback: words key
    if (vocab.isEmpty) {
      vocab = (contentJson['words'] as List?)?.cast<dynamic>() ?? const [];
    }

    // Fallback: vocabulary key
    if (vocab.isEmpty) {
      vocab = (contentJson['vocabulary'] as List?)?.cast<dynamic>() ?? const [];
    }

    // Fallback: lesson.vocabulary_words
    if (vocab.isEmpty && lessonSection != null) {
      vocab =
          (lessonSection['vocabulary_words'] as List?)?.cast<dynamic>() ??
          (lessonSection['vocabulary'] as List?)?.cast<dynamic>() ??
          (lessonSection['words'] as List?)?.cast<dynamic>() ??
          const [];
    }

    // Fallback: content.vocabulary_words
    if (vocab.isEmpty && contentSection != null) {
      vocab =
          (contentSection['vocabulary_words'] as List?)?.cast<dynamic>() ??
          (contentSection['vocabulary'] as List?)?.cast<dynamic>() ??
          const [];
    }

    // Fallback: exercise.words (for vocabulary exercises)
    if (vocab.isEmpty && exerciseSection != null) {
      vocab =
          (exerciseSection['words'] as List?)?.cast<dynamic>() ??
          (exerciseSection['vocabulary'] as List?)?.cast<dynamic>() ??
          const [];
    }

    // Fallback: nested content_json.vocabulary_words
    if (vocab.isEmpty && contentJson['content_json'] is Map) {
      final nested = contentJson['content_json'] as Map<String, dynamic>;
      vocab =
          (nested['vocabulary_words'] as List?)?.cast<dynamic>() ??
          (nested['words'] as List?)?.cast<dynamic>() ??
          const [];
    }

    // IMPORTANT:
    // Do NOT mutate `_shownVocabularyWords` during build.
    // Answering a question triggers setState() -> rebuild, and mutating the set here
    // causes the vocab list to become empty and show "Content Not Available".
    final filteredVocab = <dynamic>[];
    final localSeen = <String>{};
    for (final e in vocab) {
      final word =
          (e is Map ? e['word']?.toString() : e.toString())?.toLowerCase() ??
          '';
      if (word.isEmpty) continue;
      if (localSeen.contains(word)) continue;
      localSeen.add(word);
      filteredVocab.add(e);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Learning Header - Instructions
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFFEC4899).withValues(alpha: 0.1),
                  const Color(0xFFEC4899).withValues(alpha: 0.05),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: const Color(0xFFEC4899).withValues(alpha: 0.2),
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEC4899).withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.lightbulb_outline_rounded,
                    color: Color(0xFFEC4899),
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Learn New Words',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                          color: Color(0xFFEC4899),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Study each word, its meaning, and example before practicing',
                        style: TextStyle(fontSize: 13, color: Colors.grey[700]),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Empty state if no vocabulary - show error and ask user to try later
          if (filteredVocab.isEmpty)
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
              ),
              child: Column(
                children: [
                  Icon(
                    Icons.error_outline_rounded,
                    size: 48,
                    color: Colors.red.withValues(alpha: 0.7),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Content Not Available',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.red[700],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Vocabulary content could not be loaded. Please try again later or check your internet connection.',
                    style: TextStyle(fontSize: 14, color: Colors.grey[600]),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.arrow_back_rounded, size: 18),
                    label: const Text('Go Back'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red[400],
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Vocabulary Cards - Learning Section
          if (filteredVocab.isNotEmpty) ...[
            Row(
              children: [
                Icon(Icons.school_rounded, color: Colors.grey[700], size: 20),
                const SizedBox(width: 8),
                Text(
                  'Words to Learn (${filteredVocab.length})',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey[800],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: filteredVocab.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final m = filteredVocab[index] is Map
                    ? Map<String, dynamic>.from(filteredVocab[index])
                    : <String, dynamic>{
                        'word': filteredVocab[index].toString(),
                      };
                final word = m['word']?.toString() ?? '';
                final definition =
                    m['definition']?.toString() ??
                    m['simple_explanation']?.toString() ??
                    '';
                final example =
                    m['example']?.toString() ??
                    m['example_sentence']?.toString();
                final partOfSpeech =
                    m['part_of_speech']?.toString() ?? m['pos']?.toString();
                final pronunciation =
                    m['pronunciation']?.toString() ?? m['phonetic']?.toString();
                final synonyms = (m['synonyms'] as List?)
                    ?.map((e) => e.toString())
                    .toList();
                final useCases = (m['use_cases'] as List?)
                    ?.map((e) => e.toString())
                    .toList();
                // usageTip not currently displayed but available in data
                // final usageTip = m['usage_tip']?.toString();

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
                      // Word header with part of speech
                      Row(
                        children: [
                          Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              gradient: const LinearGradient(
                                colors: [Color(0xFFEC4899), Color(0xFFF472B6)],
                              ),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Center(
                              child: Text(
                                word.isNotEmpty ? word[0].toUpperCase() : '?',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 20,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  word,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 20,
                                  ),
                                ),
                                if (partOfSpeech != null ||
                                    pronunciation != null)
                                  Row(
                                    children: [
                                      if (partOfSpeech != null)
                                        Container(
                                          margin: const EdgeInsets.only(
                                            top: 4,
                                            right: 8,
                                          ),
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 8,
                                            vertical: 2,
                                          ),
                                          decoration: BoxDecoration(
                                            color: const Color(
                                              0xFFEC4899,
                                            ).withValues(alpha: 0.1),
                                            borderRadius: BorderRadius.circular(
                                              4,
                                            ),
                                          ),
                                          child: Text(
                                            partOfSpeech,
                                            style: const TextStyle(
                                              fontSize: 11,
                                              color: Color(0xFFEC4899),
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                        ),
                                      if (pronunciation != null)
                                        Padding(
                                          padding: const EdgeInsets.only(
                                            top: 4,
                                          ),
                                          child: Text(
                                            '/$pronunciation/',
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: Colors.grey[500],
                                              fontStyle: FontStyle.italic,
                                            ),
                                          ),
                                        ),
                                    ],
                                  ),
                              ],
                            ),
                          ),
                          // Word index badge
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.grey[100],
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              '${index + 1}/${filteredVocab.length}',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[600],
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),

                      // Definition
                      if (definition.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: Colors.blue.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: Colors.blue.withValues(alpha: 0.1),
                            ),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.menu_book_rounded,
                                size: 18,
                                color: Colors.blue[400],
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Definition',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.blue[700],
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      definition,
                                      style: TextStyle(
                                        fontSize: 15,
                                        color: Colors.grey[800],
                                        height: 1.5,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],

                      // Example sentence
                      if (example != null && example.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: Colors.green.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: Colors.green.withValues(alpha: 0.1),
                            ),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.format_quote_rounded,
                                size: 18,
                                color: Colors.green[400],
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Example',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.green[700],
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      example,
                                      style: TextStyle(
                                        fontSize: 14,
                                        color: Colors.grey[700],
                                        fontStyle: FontStyle.italic,
                                        height: 1.5,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],

                      // Use cases (if available)
                      if (useCases != null && useCases.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: Colors.orange.withValues(alpha: 0.05),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: Colors.orange.withValues(alpha: 0.1),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(
                                    Icons.tips_and_updates_rounded,
                                    size: 16,
                                    color: Colors.orange[400],
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'When to Use',
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold,
                                      color: Colors.orange[700],
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              ...useCases
                                  .take(3)
                                  .map(
                                    (useCase) => Padding(
                                      padding: const EdgeInsets.only(bottom: 4),
                                      child: Row(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            '• ',
                                            style: TextStyle(
                                              color: Colors.orange[400],
                                            ),
                                          ),
                                          Expanded(
                                            child: Text(
                                              useCase,
                                              style: TextStyle(
                                                fontSize: 13,
                                                color: Colors.grey[700],
                                                height: 1.4,
                                              ),
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

                      // Synonyms (if available)
                      if (synonyms != null && synonyms.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.swap_horiz_rounded,
                                    size: 14,
                                    color: Colors.grey[500],
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    'Similar:',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey[600],
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            ...synonyms
                                .take(4)
                                .map(
                                  (syn) => Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 4,
                                    ),
                                    decoration: BoxDecoration(
                                      color: Colors.grey[100],
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      syn,
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.grey[700],
                                      ),
                                    ),
                                  ),
                                ),
                          ],
                        ),
                      ],
                    ],
                  ),
                );
              },
            ),
          ] else
            Center(
              child: Container(
                padding: const EdgeInsets.all(32),
                child: Column(
                  children: [
                    Icon(Icons.abc_rounded, size: 64, color: Colors.grey[300]),
                    const SizedBox(height: 16),
                    Text(
                      'No vocabulary list available',
                      style: TextStyle(color: Colors.grey[500]),
                    ),
                  ],
                ),
              ),
            ),

          // Practice exercises - comes AFTER learning the words
          if ((step.questions ?? const []).isNotEmpty) ...[
            const SizedBox(height: 32),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF6366F1).withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0xFF6366F1).withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.quiz_rounded,
                      color: Color(0xFF6366F1),
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Practice Time!',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: Color(0xFF6366F1),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Test your understanding of the new vocabulary',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey[700],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _buildQuestions(step, embedded: true),
          ],
        ],
      ),
    );
  }

  Widget _buildGrammarStep(LessonStep step) {
    final grammarJson = step.contentJson ?? {};

    // Debug: print grammar contentJson keys
    debugPrint(
      '📝 Grammar step contentJson keys: ${grammarJson.keys.toList()}',
    );

    final fallbackQuestions =
        (grammarJson['exercises'] as List?)
            ?.whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList() ??
        const [];
    final effectiveQuestions = (step.questions?.isNotEmpty ?? false)
        ? step.questions!
        : fallbackQuestions;
    final displayStep = effectiveQuestions == step.questions
        ? step
        : LessonStep(
            stepType: step.stepType,
            title: step.title,
            content: step.content,
            mediaUrl: step.mediaUrl,
            questions: effectiveQuestions,
            estimatedMinutes: step.estimatedMinutes,
            contentJson: step.contentJson,
          );

    // Extract grammar_summary from AI response (new format from improved prompt)
    final grammarSummary =
        grammarJson['grammar_summary'] as Map<String, dynamic>?;
    final lessonGrammar =
        (grammarJson['lesson'] as Map<String, dynamic>?)?['grammar_point']
            as Map<String, dynamic>?;

    debugPrint('📝 Grammar summary: ${grammarSummary != null}');
    debugPrint('📝 Lesson grammar point: ${lessonGrammar != null}');

    final grammarPoint =
        grammarSummary?['title']?.toString() ??
        lessonGrammar?['title']?.toString() ??
        grammarJson['grammar_point']?.toString() ??
        grammarJson['rule']?.toString() ??
        grammarJson['topic']?.toString();
    final explanation =
        grammarSummary?['explanation']?.toString() ??
        lessonGrammar?['explanation']?.toString() ??
        grammarJson['explanation']?.toString() ??
        grammarJson['description']?.toString();
    String grammarText = step.content?.trim() ?? '';
    if (grammarText.isEmpty) {
      grammarText =
          grammarJson['content']?.toString() ??
          grammarJson['text']?.toString() ??
          grammarPoint ??
          '';
    }
    // Extract examples from multiple possible sources
    final examples =
        (grammarSummary?['examples'] as List?)
            ?.map((e) => e.toString())
            .where((e) => e.trim().isNotEmpty)
            .toList() ??
        (lessonGrammar?['examples'] as List?)
            ?.map((e) => e.toString())
            .where((e) => e.trim().isNotEmpty)
            .toList() ??
        (grammarJson['examples'] as List?)
            ?.map((e) => e.toString())
            .where((e) => e.trim().isNotEmpty)
            .toList() ??
        const <String>[];
    final structure =
        grammarJson['structure']?.toString() ??
        grammarJson['formula']?.toString();
    final usageTips =
        (grammarJson['usage_tips'] as List?)
            ?.map((e) => e.toString())
            .toList() ??
        (grammarJson['tips'] as List?)?.map((e) => e.toString()).toList();
    final commonMistakes =
        (grammarSummary?['common_mistakes'] as List?)
            ?.map((e) => e.toString())
            .toList() ??
        (lessonGrammar?['common_mistakes'] as List?)
            ?.map((e) => e.toString())
            .toList() ??
        (grammarJson['common_mistakes'] as List?)
            ?.map((e) => e.toString())
            .toList();
    final hasRuleContent =
        grammarText.isNotEmpty ||
        (grammarPoint?.isNotEmpty ?? false) ||
        (explanation?.isNotEmpty ?? false);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Learning Header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFFFF9800).withValues(alpha: 0.1),
                  const Color(0xFFFF9800).withValues(alpha: 0.05),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: const Color(0xFFFF9800).withValues(alpha: 0.2),
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFF9800).withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.lightbulb_outline_rounded,
                    color: Color(0xFFFF9800),
                    size: 24,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Grammar Lesson',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                          color: Color(0xFFFF9800),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Learn the rule, study examples, then practice',
                        style: TextStyle(fontSize: 13, color: Colors.grey[700]),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Grammar Rule Card
          if (hasRuleContent)
            Container(
              width: double.infinity,
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
                  // Rule title
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFFFF9800), Color(0xFFFFB74D)],
                          ),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(
                          Icons.rule_rounded,
                          color: Colors.white,
                          size: 22,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Text(
                          grammarPoint ?? 'Grammar Rule',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),

                  // Explanation
                  if ((explanation ?? '').isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.blue.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.blue.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            Icons.info_outline_rounded,
                            size: 18,
                            color: Colors.blue[400],
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'What is it?',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.blue[700],
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  explanation!,
                                  style: TextStyle(
                                    fontSize: 15,
                                    color: Colors.grey[800],
                                    height: 1.6,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Structure/Formula
                  if (structure != null && structure.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFF9800).withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: const Color(0xFFFF9800).withValues(alpha: 0.2),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.architecture_rounded,
                                size: 16,
                                color: Colors.orange[700],
                              ),
                              const SizedBox(width: 8),
                              Text(
                                'Structure',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.orange[700],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            structure,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Additional content text
                  if (grammarText.isNotEmpty &&
                      grammarText != grammarPoint &&
                      grammarText != explanation) ...[
                    const SizedBox(height: 12),
                    Text(
                      grammarText,
                      style: const TextStyle(fontSize: 15, height: 1.6),
                    ),
                  ],

                  // Examples section
                  if (examples.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.green.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.green.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.format_list_bulleted_rounded,
                                size: 16,
                                color: Colors.green[700],
                              ),
                              const SizedBox(width: 8),
                              Text(
                                'Examples',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.green[700],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          ...examples.asMap().entries.map(
                            (entry) => Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Container(
                                    width: 22,
                                    height: 22,
                                    margin: const EdgeInsets.only(right: 10),
                                    decoration: BoxDecoration(
                                      color: Colors.green.withValues(
                                        alpha: 0.15,
                                      ),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Center(
                                      child: Text(
                                        '${entry.key + 1}',
                                        style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: FontWeight.bold,
                                          color: Colors.green[700],
                                        ),
                                      ),
                                    ),
                                  ),
                                  Expanded(
                                    child: Text(
                                      entry.value,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        height: 1.5,
                                      ),
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

                  // Usage Tips
                  if (usageTips != null && usageTips.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.purple.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.purple.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.tips_and_updates_rounded,
                                size: 16,
                                color: Colors.purple[400],
                              ),
                              const SizedBox(width: 8),
                              Text(
                                'Usage Tips',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.purple[700],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          ...usageTips
                              .take(3)
                              .map(
                                (tip) => Padding(
                                  padding: const EdgeInsets.only(bottom: 4),
                                  child: Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '💡 ',
                                        style: TextStyle(fontSize: 12),
                                      ),
                                      Expanded(
                                        child: Text(
                                          tip,
                                          style: TextStyle(
                                            fontSize: 13,
                                            color: Colors.grey[700],
                                            height: 1.4,
                                          ),
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

                  // Common Mistakes
                  if (commonMistakes != null && commonMistakes.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.red.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.warning_amber_rounded,
                                size: 16,
                                color: Colors.red[400],
                              ),
                              const SizedBox(width: 8),
                              Text(
                                'Common Mistakes to Avoid',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.red[700],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          ...commonMistakes
                              .take(3)
                              .map(
                                (mistake) => Padding(
                                  padding: const EdgeInsets.only(bottom: 4),
                                  child: Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '❌ ',
                                        style: TextStyle(fontSize: 12),
                                      ),
                                      Expanded(
                                        child: Text(
                                          mistake,
                                          style: TextStyle(
                                            fontSize: 13,
                                            color: Colors.grey[700],
                                            height: 1.4,
                                          ),
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
              ),
            )
          else
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
              ),
              child: Column(
                children: [
                  Icon(
                    Icons.error_outline_rounded,
                    size: 48,
                    color: Colors.red.withValues(alpha: 0.7),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Content Not Available',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.red[700],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Grammar content could not be loaded. Please try again later or check your internet connection.',
                    style: TextStyle(fontSize: 14, color: Colors.grey[600]),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.arrow_back_rounded, size: 18),
                    label: const Text('Go Back'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red[400],
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Practice exercises - comes AFTER learning the rule
          if (effectiveQuestions.isNotEmpty) ...[
            const SizedBox(height: 32),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF6366F1).withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: const Color(0xFF6366F1).withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.quiz_rounded,
                      color: Color(0xFF6366F1),
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Practice Exercises',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: Color(0xFF6366F1),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Apply what you learned with these exercises',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey[700],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _buildQuestions(displayStep, embedded: true),
          ],
        ],
      ),
    );
  }

  Widget _buildQuizStep(LessonStep step) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: _buildQuestions(step),
    );
  }

  Widget _buildGenericStep(LessonStep step) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (step.content != null && step.content!.isNotEmpty)
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
              child: Text(
                step.content!,
                style: const TextStyle(fontSize: 16, height: 1.6),
              ),
            ),
          if ((step.questions ?? const []).isNotEmpty) ...[
            const SizedBox(height: 24),
            _buildQuestions(step, embedded: true),
          ],
        ],
      ),
    );
  }

  Widget _buildSpeakingStep({required String prompt}) {
    return _SpeakingInlineWidget(
      prompt: prompt,
      analyzing: _speakingAnalyzing,
      overallScore: _speakingOverall,
      feedback: _speakingFeedback,
      evaluationResult: _speakingResult,
      onAnalyze: (filePath) async {
        setState(() => _speakingAnalyzing = true);
        try {
          final api = SpeakingApi(SecureStorage());
          final SpeechEvaluateResponseModel res;

          if (kIsWeb) {
            // On web, filePath is a blob URL
            res = await api.evaluate(
              referenceText: prompt,
              language: 'en-US',
              audioFile: null,
              audioBlobUrl: filePath,
            );
          } else {
            // On native platforms, filePath is a file path
            res = await api.evaluate(
              referenceText: prompt,
              language: 'en-US',
              audioFile: io.File(filePath),
            );
          }

          setState(() {
            _speakingAnalyzing = false;
            _speakingOverall = res.overallScore;
            _speakingResult = res;
            _speakingFeedback = res.tips.isNotEmpty
                ? res.tips.join("\n")
                : 'Good job! Keep practicing.';

            // Mark step as completed when speaking is done
            _stepCompleted[_currentIndex] = true;

            // Save speaking progress immediately
            _saveStepProgress('speaking', res.overallScore >= 60 ? 1 : 0, 1);
          });
        } catch (e) {
          setState(() {
            _speakingAnalyzing = false;
            _speakingFeedback = 'Analysis failed: $e';
          });
        }
      },
    );
  }

  Widget _buildQuestions(LessonStep step, {bool embedded = false}) {
    final questions = step.questions ?? [];
    if (questions.isEmpty) {
      return Center(
        child: Container(
          padding: const EdgeInsets.all(32),
          child: Column(
            children: [
              Icon(Icons.quiz_rounded, size: 64, color: Colors.grey[300]),
              const SizedBox(height: 16),
              Text(
                'No questions available',
                style: TextStyle(color: Colors.grey[500]),
              ),
            ],
          ),
        ),
      );
    }

    return ListView.separated(
      shrinkWrap: embedded,
      physics: embedded ? const NeverScrollableScrollPhysics() : null,
      itemCount: questions.length,
      separatorBuilder: (context, index) => const SizedBox(height: 16),
      itemBuilder: (context, index) {
        final q = _normalizeQuestion(questions[index]);
        final int? userSelection = _currentStepAnswers[index];
        final bool isAnswered = userSelection != null;
        final int? correctIdx = q['answerIndex'];

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
              // Question number and text
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(
                      child: Text(
                        '${index + 1}',
                        style: const TextStyle(
                          color: Color(0xFF6366F1),
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      q['question']?.toString() ?? 'Question',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 16),

              // Options
              if (q['options'] is List)
                ...List<Widget>.from(
                  (q['options'] as List).asMap().entries.map((entry) {
                    final optIdx = entry.key;
                    final opt = entry.value;

                    Color? tileColor;
                    Color? borderColor;
                    Color? textColor;
                    IconData icon = Icons.radio_button_unchecked_rounded;
                    Color iconColor = Colors.grey[400]!;

                    if (isAnswered) {
                      if (optIdx == correctIdx) {
                        tileColor = const Color(
                          0xFF10B981,
                        ).withValues(alpha: 0.1);
                        borderColor = const Color(0xFF10B981);
                        textColor = const Color(0xFF047857);
                        icon = Icons.check_circle_rounded;
                        iconColor = const Color(0xFF10B981);
                      } else if (optIdx == userSelection) {
                        tileColor = Colors.red.withValues(alpha: 0.1);
                        borderColor = Colors.red;
                        textColor = Colors.red[700];
                        icon = Icons.cancel_rounded;
                        iconColor = Colors.red;
                      }
                    }

                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Material(
                        color: Colors.transparent,
                        child: InkWell(
                          onTap: isAnswered
                              ? null
                              : () {
                                  setState(() {
                                    _currentStepAnswers[index] = optIdx;
                                    _sessionTotal += 1;
                                    if (optIdx == correctIdx) {
                                      _sessionCorrect += 1;
                                    }
                                  });

                                  // Save progress after answering each question
                                  _saveStepProgress(
                                    widget
                                        .session
                                        .steps[_currentIndex]
                                        .stepType,
                                    optIdx == correctIdx ? 1 : 0,
                                    1,
                                  );
                                },
                          borderRadius: BorderRadius.circular(12),
                          child: Container(
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: tileColor ?? Colors.grey[50],
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: borderColor ?? Colors.grey[200]!,
                                width:
                                    isAnswered &&
                                        (optIdx == correctIdx ||
                                            optIdx == userSelection)
                                    ? 2
                                    : 1,
                              ),
                            ),
                            child: Row(
                              children: [
                                Icon(icon, color: iconColor, size: 22),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    opt.toString(),
                                    style: TextStyle(
                                      color: textColor ?? Colors.black87,
                                      fontWeight:
                                          isAnswered && optIdx == correctIdx
                                          ? FontWeight.bold
                                          : FontWeight.normal,
                                      fontSize: 15,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    );
                  }),
                ),

              // Explanation
              if (isAnswered && q['explanation'] != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF3B82F6).withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: const Color(0xFF3B82F6).withValues(alpha: 0.2),
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.lightbulb_outline_rounded,
                        size: 18,
                        color: const Color(0xFF3B82F6).withValues(alpha: 0.8),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          q['explanation'],
                          style: TextStyle(
                            color: Colors.grey[700],
                            fontSize: 14,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Future<void> _saveStepProgress(
    String skillType,
    int correct,
    int total,
  ) async {
    try {
      final repo = context.read<OnboardingRepository>();
      await repo.saveStepProgress(
        sessionId: widget.session.sessionId,
        moduleId: widget.session.moduleId,
        dayNumber: widget.session.dayNumber,
        stepIndex: _currentIndex,
        correct: correct,
        total: total,
        timeSpentMinutes: (_stopwatch.elapsed.inSeconds / 60)
            .clamp(1, 180)
            .round(),
        skillType: skillType,
      );
    } catch (e) {
      debugPrint('Failed to save step progress: $e');
    }
  }

  Future<void> _onNext() async {
    await _stopAudioPlayback();

    // Mark current step as completed
    _stepCompleted[_currentIndex] = true;

    if (_currentIndex < widget.session.steps.length - 1) {
      if (!mounted) return;
      setState(() {
        _currentIndex += 1;
        _resetStepState();
      });
    } else {
      _stopwatch.stop();
      await _completeSession();
    }
  }

  Future<void> _completeSession() async {
    try {
      final minutes = (_stopwatch.elapsed.inSeconds / 60).clamp(1, 180).round();
      final repo = context.read<OnboardingRepository>();
      final res = await repo.completeLearningSession(
        sessionId: widget.session.sessionId,
        moduleId: widget.session.moduleId,
        dayNumber: widget.session.dayNumber,
        correct: _sessionCorrect,
        total: _sessionTotal == 0 ? 1 : _sessionTotal,
        timeSpentMinutes: minutes,
      );
      if (!mounted) return;
      await _stopAudioPlayback();

      // Show completion dialog
      _showCompletionDialog(res);
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop({'error': e.toString()});
    }
  }

  void _showCompletionDialog(Map<String, dynamic> result) {
    final unlocked = result['unlocked_next_module'] == true;
    // Progress tracking available in result but not currently displayed
    // final progress = result['updated_progress_percentage'] ?? 0.0;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: const Color(0xFF10B981).withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.celebration_rounded,
                color: Color(0xFF10B981),
                size: 48,
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Great Job!',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'You completed Day ${widget.session.dayNumber}',
              style: TextStyle(color: Colors.grey[600], fontSize: 16),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _buildCompletionStat(
                  icon: Icons.check_circle_rounded,
                  value: '$_sessionCorrect/$_sessionTotal',
                  label: 'Correct',
                ),
                const SizedBox(width: 24),
                _buildCompletionStat(
                  icon: Icons.timer_rounded,
                  value: '${(_stopwatch.elapsed.inMinutes)}m',
                  label: 'Time',
                ),
              ],
            ),
            if (unlocked) ...[
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.lock_open_rounded,
                      color: Color(0xFF6366F1),
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Day ${widget.session.dayNumber + 1} unlocked!',
                      style: const TextStyle(
                        color: Color(0xFF6366F1),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
        actions: [
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () {
                Navigator.of(context).pop();
                Navigator.of(context).pop(result);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6366F1),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                'Continue',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCompletionStat({
    required IconData icon,
    required String value,
    required String label,
  }) {
    return Column(
      children: [
        Icon(icon, color: const Color(0xFF6366F1), size: 24),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        Text(label, style: TextStyle(color: Colors.grey[500], fontSize: 12)),
      ],
    );
  }

  Future<void> _stopAudioPlayback() async {
    try {
      await _player.stop();
    } catch (_) {}
  }

  Future<String> _absoluteMediaUrl(String url) async {
    final current = Uri.base;
    bool isLocal(String host) =>
        host == 'localhost' || host == '127.0.0.1' || host.endsWith('.local');

    final apiBaseUri = Uri.tryParse(AppEnvironment.apiBaseUrl);
    final sameOriginApi =
        apiBaseUri != null && apiBaseUri.origin == current.origin;
    final shouldIngressRewrite =
        kIsWeb && sameOriginApi && !isLocal(current.host);

    String addApiPrefixIfNeeded(String path) {
      final normalized = path.startsWith('/') ? path : '/$path';
      if (!shouldIngressRewrite) return normalized;
      if (normalized.startsWith('/api/')) return normalized;
      if (normalized.startsWith('/media/') || normalized.startsWith('/audio/')) {
        return '/api$normalized';
      }
      return normalized;
    }

    if (url.startsWith('http://') || url.startsWith('https://')) {
      final uri = Uri.tryParse(url);
      if (uri != null &&
          shouldIngressRewrite &&
          uri.origin == current.origin &&
          (uri.path.startsWith('/media/') || uri.path.startsWith('/audio/'))) {
        return uri.replace(path: addApiPrefixIfNeeded(uri.path)).toString();
      }
      return url;
    }
    try {
      final parsed = Uri.parse(AppEnvironment.apiBaseUrl);
      final origin = Uri(
        scheme: parsed.scheme,
        host: parsed.host,
        port: parsed.hasPort ? parsed.port : null,
      ).toString().replaceAll(RegExp(r"\/\$"), '');
      final path = addApiPrefixIfNeeded(url);
      return '$origin$path';
    } catch (_) {
      final path = addApiPrefixIfNeeded(url);
      return '${AppEnvironment.apiBaseUrl}$path';
    }
  }

  Future<String> _downloadAudioToDevice(String absoluteUrl) async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = io.Directory('${docs.path}/tts');
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
    final segments = Uri.parse(absoluteUrl).pathSegments;
    final filename = segments.isNotEmpty
        ? segments.last
        : 'audio_${DateTime.now().millisecondsSinceEpoch}.wav';
    final localPath = '${dir.path}/$filename';
    final localFile = io.File(localPath);
    if (await localFile.exists()) {
      return localPath;
    }
    final tempFile = await DefaultCacheManager().getSingleFile(absoluteUrl);
    await tempFile.copy(localPath);
    return localPath;
  }

  String _getDefaultReadingPassage(String title) {
    // Extract topic from title
    final topic = title
        .replaceAll('Reading •', '')
        .replaceAll('Reading', '')
        .trim();

    return '''Today we will explore an interesting topic: $topic.

Learning a new language opens many doors. It helps you communicate with people from different cultures and understand their perspectives. English, in particular, is used around the world for business, travel, and everyday communication.

When reading in English, try to understand the main ideas first. Don't worry if you don't know every word. Use context clues to guess the meaning of unfamiliar words.

Practice reading a little bit every day. Start with easier texts and gradually move to more challenging material. Reading regularly will help you build your vocabulary and improve your comprehension skills.

Remember, every expert was once a beginner. Keep practicing and you will see improvement!''';
  }

  Map<String, dynamic> _normalizeQuestion(dynamic raw) {
    final Map<String, dynamic> q = raw is Map
        ? Map<String, dynamic>.from(raw)
        : {'question': raw.toString()};
    final String questionText = q['question']?.toString() ?? 'Question';
    final String type = (q['type'] ?? '').toString().toLowerCase();
    List<String> options = [];
    int? answerIndex;

    if (q['options'] is List) {
      options = (q['options'] as List).map((e) => e.toString()).toList();
    }

    final dynamic rawCorrect = q.containsKey('answer')
        ? q['answer']
        : q['correct_answer'];

    if (options.isNotEmpty) {
      if (rawCorrect is int && rawCorrect >= 0 && rawCorrect < options.length) {
        answerIndex = rawCorrect;
      } else if (rawCorrect != null) {
        final idx = options.indexWhere(
          (o) =>
              o.toString().trim().toLowerCase() ==
              rawCorrect.toString().trim().toLowerCase(),
        );
        answerIndex = idx >= 0 ? idx : 0;
      } else {
        answerIndex = 0;
      }
    } else if (type == 'true_false' ||
        type == 'true-false' ||
        type == 'boolean') {
      options = const ['True', 'False'];
      final val = rawCorrect?.toString().toLowerCase();
      answerIndex = (val == 'true' || val == 't' || val == '1') ? 0 : 1;
    } else {
      final correct = (rawCorrect?.toString().isNotEmpty ?? false)
          ? rawCorrect.toString()
          : 'Not stated';
      options = [
        correct,
        'A different detail from the text',
        'An unrelated inference',
        'Not enough information',
      ];
      answerIndex = 0;
    }

    return {
      'question': questionText,
      'options': options,
      'answerIndex': answerIndex,
      'explanation': q['explanation']?.toString(),
    };
  }
}

class _SpeakingInlineWidget extends StatefulWidget {
  final String prompt;
  final bool analyzing;
  final double? overallScore;
  final String? feedback;
  final SpeechEvaluateResponseModel? evaluationResult;
  final Future<void> Function(String filePath) onAnalyze;

  const _SpeakingInlineWidget({
    required this.prompt,
    required this.analyzing,
    required this.overallScore,
    required this.feedback,
    this.evaluationResult,
    required this.onAnalyze,
  });

  @override
  State<_SpeakingInlineWidget> createState() => _SpeakingInlineWidgetState();
}

class _SpeakingInlineWidgetState extends State<_SpeakingInlineWidget>
    with SingleTickerProviderStateMixin {
  final RecordingController _recorder = RecordingController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  late AnimationController _pulseController;
  bool _recording = false;
  bool _playing = false;
  String? _path;
  int _recordingSeconds = 0;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _recorder.dispose();
    _audioPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Prompt card
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFFF59E0B), Color(0xFFD97706)],
              ),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFFF59E0B).withValues(alpha: 0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              children: [
                const Icon(Icons.mic_rounded, color: Colors.white, size: 48),
                const SizedBox(height: 16),
                const Text(
                  'Practice Speaking',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Read the following text aloud',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.9),
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Text to read
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
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF59E0B).withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.format_quote_rounded,
                        color: Color(0xFFF59E0B),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Text(
                      'Text to Read',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                const Divider(),
                const SizedBox(height: 16),
                Text(
                  widget.prompt,
                  style: const TextStyle(
                    fontSize: 18,
                    height: 1.8,
                    color: Colors.black87,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Recording controls
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
              children: [
                // Recording status indicator
                if (_recording) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 20,
                      vertical: 12,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(30),
                      border: Border.all(
                        color: Colors.red.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Pulsing red dot
                        AnimatedBuilder(
                          animation: _pulseController,
                          builder: (context, child) {
                            return Container(
                              width: 12,
                              height: 12,
                              decoration: BoxDecoration(
                                color: Colors.red.withValues(
                                  alpha: 0.5 + _pulseController.value * 0.5,
                                ),
                                shape: BoxShape.circle,
                              ),
                            );
                          },
                        ),
                        const SizedBox(width: 10),
                        Text(
                          'REC ${_recordingSeconds}s',
                          style: const TextStyle(
                            color: Colors.red,
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                ],

                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Play button (only show if recording exists)
                    if (_path != null && !_recording)
                      GestureDetector(
                        onTap: _togglePlayback,
                        child: Container(
                          width: 56,
                          height: 56,
                          decoration: BoxDecoration(
                            color: _playing ? Colors.blue : Colors.grey[300],
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            _playing
                                ? Icons.stop_rounded
                                : Icons.play_arrow_rounded,
                            color: _playing ? Colors.white : Colors.grey[700],
                            size: 28,
                          ),
                        ),
                      ),
                    if (_path != null && !_recording) const SizedBox(width: 16),
                    // Record button with animation
                    GestureDetector(
                      onTap: _toggle,
                      child: AnimatedBuilder(
                        animation: _pulseController,
                        builder: (context, child) {
                          final scale = _recording
                              ? 1.0 + (_pulseController.value * 0.1)
                              : 1.0;
                          return Transform.scale(
                            scale: scale,
                            child: Container(
                              width: 80,
                              height: 80,
                              decoration: BoxDecoration(
                                color: _recording
                                    ? Colors.red
                                    : _path != null
                                    ? const Color(0xFF10B981)
                                    : const Color(0xFFF59E0B),
                                shape: BoxShape.circle,
                                boxShadow: [
                                  BoxShadow(
                                    color:
                                        (_recording
                                                ? Colors.red
                                                : _path != null
                                                ? const Color(0xFF10B981)
                                                : const Color(0xFFF59E0B))
                                            .withValues(alpha: 0.4),
                                    blurRadius: _recording ? 20 : 12,
                                    offset: const Offset(0, 4),
                                  ),
                                ],
                              ),
                              child: Icon(
                                _recording
                                    ? Icons.stop_rounded
                                    : _path != null
                                    ? Icons.refresh_rounded
                                    : Icons.mic_rounded,
                                color: Colors.white,
                                size: 36,
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    const SizedBox(width: 20),
                    // Analyze button
                    ElevatedButton.icon(
                      onPressed:
                          (!_recording && _path != null && !widget.analyzing)
                          ? () => widget.onAnalyze(_path!)
                          : null,
                      icon: widget.analyzing
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation(
                                  Colors.white,
                                ),
                              ),
                            )
                          : const Icon(Icons.psychology_rounded),
                      label: Text(
                        widget.analyzing ? 'Analyzing...' : 'Get Feedback',
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF6366F1),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 16,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  _recording
                      ? 'Speak now! Tap the red button to stop'
                      : _path != null
                      ? '✅ Recording complete (${_recordingSeconds}s)! Tap "Get Feedback" to analyze'
                      : 'Tap the microphone to start recording',
                  style: TextStyle(
                    color: _path != null
                        ? const Color(0xFF10B981)
                        : Colors.grey[600],
                    fontSize: 14,
                    fontWeight: _path != null
                        ? FontWeight.w600
                        : FontWeight.normal,
                  ),
                ),
              ],
            ),
          ),

          // Results
          if (widget.overallScore != null) ...[
            const SizedBox(height: 24),
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
                  // Overall score
                  Row(
                    children: [
                      Container(
                        width: 70,
                        height: 70,
                        decoration: BoxDecoration(
                          color: _getScoreColor(
                            widget.overallScore!,
                          ).withValues(alpha: 0.1),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: _getScoreColor(
                              widget.overallScore!,
                            ).withValues(alpha: 0.3),
                            width: 3,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            '${widget.overallScore!.toInt()}',
                            style: TextStyle(
                              color: _getScoreColor(widget.overallScore!),
                              fontSize: 28,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Pronunciation Score',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _getScoreMessage(widget.overallScore!),
                              style: TextStyle(
                                color: Colors.grey[600],
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),

                  // Detailed metrics from SpeechAce
                  if (widget.evaluationResult != null) ...[
                    const SizedBox(height: 20),
                    const Divider(),
                    const SizedBox(height: 16),

                    // Pronunciation score (main metric from Speechace pronunciation-only plan)
                    if (widget.evaluationResult!.pronunciationScore != null &&
                        widget.evaluationResult!.pronunciationScore! > 0)
                      _buildMetricCard(
                        'Pronunciation',
                        '${widget.evaluationResult!.pronunciationScore!.toInt()}%',
                        Icons.record_voice_over_rounded,
                        const Color(0xFF10B981),
                      ),

                    // Transcript comparison
                    if (widget
                        .evaluationResult!
                        .transcript
                        .text
                        .isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.grey[50],
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.grey[200]!),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  Icons.record_voice_over_rounded,
                                  size: 16,
                                  color: Colors.grey[600],
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  'What we heard:',
                                  style: TextStyle(
                                    color: Colors.grey[600],
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(
                              widget.evaluationResult!.transcript.text,
                              style: const TextStyle(fontSize: 14, height: 1.5),
                            ),
                          ],
                        ),
                      ),
                    ],

                    // Pronunciation issues
                    if (widget
                        .evaluationResult!
                        .pronunciation
                        .issues
                        .isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Text(
                        'Areas to improve:',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: Colors.grey[700],
                        ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: widget.evaluationResult!.pronunciation.issues
                            .take(5)
                            .map((issue) {
                              return Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 6,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.orange.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(20),
                                  border: Border.all(
                                    color: Colors.orange.withValues(alpha: 0.3),
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(
                                      issue.word,
                                      style: const TextStyle(
                                        color: Colors.orange,
                                        fontWeight: FontWeight.w600,
                                        fontSize: 13,
                                      ),
                                    ),
                                    if (issue.suggestion != null) ...[
                                      const SizedBox(width: 6),
                                      Icon(
                                        Icons.arrow_forward_rounded,
                                        size: 12,
                                        color: Colors.orange[700],
                                      ),
                                      const SizedBox(width: 4),
                                      Text(
                                        issue.suggestion!,
                                        style: TextStyle(
                                          color: Colors.orange[800],
                                          fontSize: 12,
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              );
                            })
                            .toList(),
                      ),
                    ],
                  ],

                  // Tips
                  if (widget.feedback != null) ...[
                    const SizedBox(height: 16),
                    const Divider(),
                    const SizedBox(height: 16),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(6),
                          decoration: BoxDecoration(
                            color: Colors.amber.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(
                            Icons.lightbulb_rounded,
                            color: Colors.amber[700],
                            size: 18,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Tips for improvement',
                                style: TextStyle(
                                  color: Colors.grey[800],
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                widget.feedback!,
                                style: TextStyle(
                                  color: Colors.grey[600],
                                  fontSize: 13,
                                  height: 1.5,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildMetricCard(
    String label,
    String value,
    IconData icon,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.1)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(color: Colors.grey[600], fontSize: 12)),
        ],
      ),
    );
  }

  Color _getScoreColor(double score) {
    if (score >= 80) return const Color(0xFF10B981);
    if (score >= 60) return const Color(0xFFF59E0B);
    return Colors.red;
  }

  String _getScoreMessage(double score) {
    if (score >= 90) return 'Excellent! Native-like pronunciation';
    if (score >= 80) return 'Great job! Very clear pronunciation';
    if (score >= 70) return 'Good! Keep practicing';
    if (score >= 60) return 'Fair. Focus on problem areas';
    return 'Needs improvement. Keep trying!';
  }

  Future<void> _toggle() async {
    if (_recording) {
      debugPrint('🎤 Stopping recording...');
      _pulseController.stop();
      final p = await _recorder.stop();
      debugPrint('🎤 Recording stopped. Path: $p');
      setState(() {
        _recording = false;
        _path = p;
      });
    } else {
      // Stop any playback before recording
      if (_playing) {
        await _audioPlayer.stop();
        setState(() => _playing = false);
      }
      debugPrint('🎤 Starting recording...');
      try {
        await _recorder.start();
        debugPrint('🎤 Recording started successfully');
        _pulseController.repeat(reverse: true);
        setState(() {
          _recording = true;
          _recordingSeconds = 0;
          _path = null;
        });
        // Start recording timer
        _startRecordingTimer();
      } catch (e) {
        debugPrint('🎤 ERROR starting recording: $e');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Could not start recording: $e'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    }
  }

  void _startRecordingTimer() async {
    while (_recording && mounted) {
      await Future.delayed(const Duration(seconds: 1));
      if (_recording && mounted) {
        setState(() => _recordingSeconds++);
      }
    }
  }

  Future<void> _togglePlayback() async {
    if (_path == null) return;

    try {
      if (_playing) {
        await _audioPlayer.stop();
        setState(() => _playing = false);
        return;
      }

      setState(() => _playing = true);

      // Handle both blob URLs (web) and file paths (native)
      if (kIsWeb) {
        // On web, _path is a blob URL
        await _audioPlayer.setUrl(_path!);
      } else {
        // On native platforms, _path is a file path
        await _audioPlayer.setFilePath(_path!);
      }

      _audioPlayer.playerStateStream.listen((state) {
        if (state.processingState == ProcessingState.completed) {
          if (mounted) setState(() => _playing = false);
        }
      });
      await _audioPlayer.play();
    } catch (e) {
      if (mounted) {
        setState(() => _playing = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error playing recording: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }
}
