import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb, kDebugMode;
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_cache_manager/flutter_cache_manager.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:just_audio/just_audio.dart';

import '../../../../core/api/tts_api.dart';
import '../../../../core/config/app_environment.dart';
import '../../../../core/di/injection_container.dart' as di;
import '../../data/models/onboarding_models.dart';
import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';

class AssessmentScreen extends StatefulWidget {
  final AssessmentInProgressState state;

  const AssessmentScreen({super.key, required this.state});

  @override
  State<AssessmentScreen> createState() => _AssessmentScreenState();
}

class _AssessmentScreenState extends State<AssessmentScreen>
    with TickerProviderStateMixin {
  late AnimationController _questionAnimationController;
  late AnimationController _progressAnimationController;
  late Animation<double> _questionFadeAnimation;
  late Animation<Offset> _questionSlideAnimation;
  late Animation<double> _progressAnimation;
  final TextEditingController _textAnswerController = TextEditingController();
  List<TextEditingController> _blankControllers = [];
  final AudioPlayer _player = AudioPlayer();
  final FlutterTts _tts = FlutterTts();
  final TTSApi _ttsApi = di.sl<TTSApi>();
  bool _isAudioLoading = false;
  bool _isAudioPlaying = false;
  String? _ttsErrorMessage;
  // Cache for generated audio URLs by question ID
  final Map<String, String> _generatedAudioUrls = {};

  int? _selectedAnswerIndex;
  DateTime _questionStartTime = DateTime.now();
  bool _showFeedback = false;

  @override
  void initState() {
    super.initState();

    _questionStartTime = DateTime.now();

    _questionAnimationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _progressAnimationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _questionFadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _questionAnimationController,
        curve: Curves.easeOut,
      ),
    );

    _questionSlideAnimation =
        Tween<Offset>(begin: const Offset(0.3, 0), end: Offset.zero).animate(
          CurvedAnimation(
            parent: _questionAnimationController,
            curve: Curves.elasticOut,
          ),
        );

    _progressAnimation = Tween<double>(begin: 0.0, end: widget.state.progress)
        .animate(
          CurvedAnimation(
            parent: _progressAnimationController,
            curve: Curves.easeInOut,
          ),
        );

    _questionAnimationController.forward();
    _progressAnimationController.forward();

    // Initialize TTS
    _initTTS();

    // Explicitly set playback speed to 1.0x to prevent fast-forward on some Android devices
    _player.setSpeed(1.0);

    // just_audio state listeners
    _player.playerStateStream.listen((state) {
      if (!mounted) return;
      final playing = state.playing;
      final completed = state.processingState == ProcessingState.completed;
      setState(() {
        _isAudioPlaying = playing && !completed;
      });
      if (completed) {
        _player.seek(Duration.zero);
      }
    });
  }

  @override
  void didUpdateWidget(AssessmentScreen oldWidget) {
    super.didUpdateWidget(oldWidget);

    // Reset for new question
    if (oldWidget.state.currentQuestionIndex !=
        widget.state.currentQuestionIndex) {
      unawaited(_stopAllAudio());
      _selectedAnswerIndex = null;
      _showFeedback = false;
      _questionStartTime = DateTime.now();
      _textAnswerController.clear();
      _ttsErrorMessage = null; // Clear TTS error for new question
      for (final c in _blankControllers) {
        c.dispose();
      }
      _blankControllers = [];

      // Animate new question
      _questionAnimationController.reset();
      _questionAnimationController.forward();

      // Update progress
      _progressAnimation =
          Tween<double>(
            begin: _progressAnimation.value,
            end: widget.state.progress,
          ).animate(
            CurvedAnimation(
              parent: _progressAnimationController,
              curve: Curves.easeInOut,
            ),
          );
      _progressAnimationController.reset();
      _progressAnimationController.forward();
    }
  }

  @override
  void dispose() {
    _questionAnimationController.dispose();
    _progressAnimationController.dispose();
    _textAnswerController.dispose();
    for (final c in _blankControllers) {
      c.dispose();
    }
    _stopAllAudio();
    _player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final currentQuestion = widget.state.currentQuestion;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) {
          _showExitDialog();
        }
      },
      child: Scaffold(
        backgroundColor: Theme.of(context).colorScheme.surface,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: Icon(
              Icons.close,
              color: Theme.of(context).colorScheme.onSurface,
            ),
            onPressed: _showExitDialog,
          ),
          title: Text(
            'Assessment',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          centerTitle: true,
        ),
        body: BlocListener<OnboardingBloc, OnboardingState>(
          listener: (context, state) {
            if (state is AssessmentInProgressState &&
                state.isLoadingNextQuestion) {
              // Show loading for next question
            }
          },
          child: SafeArea(
            child: Column(
              children: [
                // Progress Header
                _buildProgressHeader(),

                // Question Content
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(24),
                    child: FadeTransition(
                      opacity: _questionFadeAnimation,
                      child: SlideTransition(
                        position: _questionSlideAnimation,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Question Number & Type
                            _buildQuestionHeader(currentQuestion),

                            const SizedBox(height: 24),

                            // Passage (for reading) and Question Text
                            if ((currentQuestion.passage ?? '').isNotEmpty) ...[
                              _buildPassageBlock(currentQuestion.passage!),
                              const SizedBox(height: 16),
                            ],
                            _buildQuestionText(currentQuestion),
                            const SizedBox(height: 16),
                            _buildAudioWidget(currentQuestion),

                            const SizedBox(height: 32),

                            // Answer Options
                            _buildAnswerOptions(currentQuestion),

                            if (_showFeedback) ...[
                              const SizedBox(height: 24),
                              _buildFeedback(currentQuestion),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ),
                ),

                // Action Button
                _buildActionButton(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProgressHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: Column(
        children: [
          // Progress Bar
          AnimatedBuilder(
            animation: _progressAnimation,
            builder: (context, child) {
              return LinearProgressIndicator(
                value: _progressAnimation.value,
                backgroundColor: Theme.of(
                  context,
                ).colorScheme.outline.withValues(alpha: 0.2),
                valueColor: AlwaysStoppedAnimation<Color>(
                  Theme.of(context).colorScheme.primary,
                ),
              );
            },
          ),

          const SizedBox(height: 12),

          // Progress Text
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Question ${widget.state.currentQuestionIndex + 1} of ${widget.state.questions.length}',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
              ),
              Text(
                '${(widget.state.progress * 100).round()}% Complete',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildQuestionHeader(AssessmentQuestion question) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: _getSkillColor(question.skillType).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                _getSkillIcon(question.skillType),
                size: 16,
                color: _getSkillColor(question.skillType),
              ),
              const SizedBox(width: 6),
              Text(
                question.skillType.toUpperCase(),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: _getSkillColor(question.skillType),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),

        const SizedBox(width: 12),

        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: Theme.of(
              context,
            ).colorScheme.secondaryContainer.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Text(
            question.targetLevel.code,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.secondary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildQuestionText(AssessmentQuestion question) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Text(
        question.question,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w500,
          height: 1.4,
          color: Theme.of(context).colorScheme.onSurface,
        ),
      ),
    );
  }

  Widget _buildPassageBlock(String passage) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.menu_book,
                size: 18,
                color: Theme.of(context).colorScheme.secondary,
              ),
              const SizedBox(width: 8),
              Text(
                'Reading Passage',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: Theme.of(context).colorScheme.secondary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            passage,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5),
          ),
        ],
      ),
    );
  }

  Widget _buildAudioWidget(AssessmentQuestion question) {
    final hasUrl = (question.audioUrl != null && question.audioUrl!.isNotEmpty);
    final hasGeneratedUrl = _generatedAudioUrls.containsKey(question.id);
    final hasText =
        (question.audioText != null && question.audioText!.isNotEmpty);
    if (!hasUrl && !hasText) return const SizedBox.shrink();

    // Determine audio source label
    String audioSourceLabel;
    IconData audioIcon;
    if (hasUrl || hasGeneratedUrl) {
      audioSourceLabel = 'Listening question (AI audio)';
      audioIcon = Icons.graphic_eq;
    } else {
      audioSourceLabel = 'Listening question (tap to generate audio)';
      audioIcon = Icons.hearing;
    }

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _ttsErrorMessage != null
            ? Colors.red.withValues(alpha: 0.1)
            : _isAudioPlaying
            ? Theme.of(
                context,
              ).colorScheme.primaryContainer.withValues(alpha: 0.3)
            : Theme.of(
                context,
              ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _ttsErrorMessage != null
              ? Colors.red
              : _isAudioPlaying
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          width: _isAudioPlaying ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _isAudioPlaying
                      ? Theme.of(
                          context,
                        ).colorScheme.primary.withValues(alpha: 0.2)
                      : Colors.transparent,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  _ttsErrorMessage != null ? Icons.error : audioIcon,
                  color: _ttsErrorMessage != null
                      ? Colors.red
                      : Theme.of(context).colorScheme.primary,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      audioSourceLabel,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    if (_isAudioLoading)
                      Text(
                        'Generating audio...',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                  ],
                ),
              ),
              if (_isAudioLoading)
                const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else if (_ttsErrorMessage != null)
                IconButton(
                  icon: Icon(
                    Icons.refresh,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  onPressed: () {
                    setState(() {
                      _ttsErrorMessage = null;
                    });
                    _togglePlayAudio(question);
                  },
                  tooltip: 'Retry',
                )
              else
                IconButton(
                  icon: Icon(
                    _isAudioPlaying ? Icons.stop_circle : Icons.play_circle,
                    color: Theme.of(context).colorScheme.primary,
                    size: 32,
                  ),
                  onPressed: () => _togglePlayAudio(question),
                  tooltip: _isAudioPlaying ? 'Stop' : 'Play',
                ),
            ],
          ),
          if (_ttsErrorMessage != null) ...[
            const SizedBox(height: 8),
            Text(
              _ttsErrorMessage!,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.red,
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _togglePlayAudio(AssessmentQuestion q) async {
    if (_isAudioPlaying) {
      await _pauseAllAudio();
      setState(() {
        _isAudioPlaying = false;
      });
      return;
    }

    setState(() {
      _isAudioLoading = true;
      _ttsErrorMessage = null;
    });

    try {
      // Priority 1: Use existing audio URL from backend
      String? audioUrl = q.audioUrl;

      // Priority 2: Check if we've already generated audio for this question
      if ((audioUrl == null || audioUrl.isEmpty) &&
          _generatedAudioUrls.containsKey(q.id)) {
        audioUrl = _generatedAudioUrls[q.id];
      }

      // Priority 3: Generate audio via backend TTS API if we have text
      if ((audioUrl == null || audioUrl.isEmpty) &&
          q.audioText != null &&
          q.audioText!.isNotEmpty) {
        if (kDebugMode) {
          print(
            '🎤 Generating TTS audio for question ${q.id} via backend API...',
          );
        }
        final ttsResult = await _ttsApi.generateGeminiTTS(
          text: q.audioText!,
          audioType: 'assessment',
        );

        if (ttsResult.success && ttsResult.audioUrl != null) {
          audioUrl = ttsResult.audioUrl;
          _generatedAudioUrls[q.id] = audioUrl!;
          if (kDebugMode) {
            print('✅ Backend TTS generated: $audioUrl');
          }
        } else {
          if (kDebugMode) {
            print('⚠️ Backend TTS failed: ${ttsResult.error}');
          }
        }
      }

      // Play the audio if we have a URL
      if (audioUrl != null && audioUrl.isNotEmpty) {
        final resolvedAudioUrl = _resolveAudioUrl(audioUrl);
        if (kDebugMode) {
          print('🔊 Playing audio from URL: $resolvedAudioUrl');
        }
        await _player.stop();

        // On web, play directly from URL; on mobile, download and cache first
        if (kIsWeb) {
          // Add explicit headers to help some CDNs and browsers
          final source = AudioSource.uri(
            Uri.parse(resolvedAudioUrl),
            headers: const {'Accept': 'audio/wav, audio/*'},
          );
          await _player.setAudioSource(source);
        } else {
          // Mobile: Download and cache the file for offline playback
          final file = await DefaultCacheManager().getSingleFile(
            resolvedAudioUrl,
          );
          await _player.setFilePath(file.path);
        }

        await _player.play();
        setState(() {
          _isAudioPlaying = true;
        });
        return;
      }

      // Fallback: Use Flutter TTS (device TTS) if no backend audio available
      if (q.audioText != null && q.audioText!.isNotEmpty) {
        if (kDebugMode) {
          print('🔊 Falling back to Flutter TTS...');
        }
        await _speakTTS(q.audioText);
      } else {
        setState(() {
          _ttsErrorMessage = 'No audio content available for this question.';
        });
      }
    } catch (e) {
      if (kDebugMode) {
        print('❌ Audio playback error: $e');
      }
      // Final fallback: try Flutter TTS
      if (q.audioText != null && q.audioText!.isNotEmpty) {
        try {
          await _speakTTS(q.audioText);
        } catch (ttsError) {
          setState(() {
            _ttsErrorMessage = 'Audio playback failed. Please try again.';
          });
        }
      } else {
        setState(() {
          _ttsErrorMessage = 'Audio playback failed. Please try again.';
        });
      }
    } finally {
      setState(() {
        _isAudioLoading = false;
      });
    }
  }

  Future<void> _initTTS() async {
    try {
      // Set up TTS event handlers
      _tts.setStartHandler(() {
        if (!mounted) return;
        setState(() {
          _isAudioPlaying = true;
        });
      });

      _tts.setCompletionHandler(() {
        if (!mounted) return;
        setState(() {
          _isAudioPlaying = false;
        });
      });

      _tts.setErrorHandler((error) {
        if (!mounted) return;
        setState(() {
          _isAudioPlaying = false;
          _isAudioLoading = false;
          _ttsErrorMessage =
              'Speech synthesis failed. Please check your device settings.';
        });
        if (kDebugMode) {
          print('TTS Error: $error');
        }
      });

      _tts.setCancelHandler(() {
        if (!mounted) return;
        setState(() {
          _isAudioPlaying = false;
        });
      });

      // Get available engines and set default settings
      final engines = await _tts.getEngines;
      if (engines != null && engines.isNotEmpty) {
        if (kDebugMode) {
          print('Available TTS engines: $engines');
        }
      }

      // Set default language and speech rate
      await _tts.setLanguage('en-US');
      await _tts.setSpeechRate(0.7); // Slightly faster than 0.5
      await _tts.setVolume(1.0); // Full volume
      await _tts.setPitch(1.0); // Normal pitch

      if (kDebugMode) {
        print('TTS initialized successfully');
      }
    } catch (e) {
      if (kDebugMode) {
        print('TTS initialization failed: $e');
      }
    }
  }

  Future<void> _speakTTS(String? text) async {
    if (text == null || text.isEmpty) return;

    try {
      setState(() {
        _isAudioLoading = true;
      });

      // Stop any current speech
      await _tts.stop();

      // Ensure language is set
      await _tts.setLanguage('en-US');

      // Set speech parameters
      await _tts.setSpeechRate(0.7);
      await _tts.setVolume(1.0);
      await _tts.setPitch(1.0);

      // Speak the text
      final result = await _tts.speak(text);
      if (kDebugMode) {
        print('TTS speak result: $result');
      }
    } catch (e) {
      if (kDebugMode) {
        print('TTS speak error: $e');
      }
      setState(() {
        _isAudioPlaying = false;
      });
    } finally {
      setState(() {
        _isAudioLoading = false;
      });
    }
  }

  Future<void> _pauseAllAudio() async {
    try {
      await _player.pause();
    } catch (_) {}
    try {
      await _tts.stop();
    } catch (_) {}
  }

  Future<void> _stopAllAudio() async {
    try {
      await _player.stop();
    } catch (_) {}
    try {
      await _tts.stop();
    } catch (_) {}
    if (mounted) {
      setState(() {
        _isAudioPlaying = false;
        _isAudioLoading = false;
      });
    } else {
      _isAudioPlaying = false;
      _isAudioLoading = false;
    }
  }

  /// Resolve audio URLs to absolute, production-safe URLs.
  /// - Ensures relative paths are prefixed with the API base.
  /// - Rewrites localhost URLs to the current origin to avoid mixed-host issues in web.
  String _resolveAudioUrl(String url) {
    final trimmed = url.trim();
    if (trimmed.isEmpty) return trimmed;

    final current = Uri.base;
    bool isLocal(String host) =>
        host == 'localhost' || host == '127.0.0.1' || host.endsWith('.local');

    // DigitalOcean setup note:
    // - In production we serve the app (web) and API behind the same origin.
    // - The API is routed under `/api/*` (ingress), while media links sometimes
    //   come back as `/media/...` (backend default).
    // - If we request `/media/...` in the browser, it can hit the web nginx instead
    //   of the API service and 404.
    //
    // So: when we are on web + same-origin + non-localhost, rewrite `/media/*`
    // and `/audio/*` to go through `/api/...`.
    final apiBaseUri = Uri.tryParse(AppEnvironment.apiBaseUrl);
    final sameOriginApi =
        apiBaseUri != null && apiBaseUri.origin == current.origin;
    final shouldIngressRewrite =
        kIsWeb && sameOriginApi && !isLocal(current.host);

    String addApiPrefixIfNeeded(String pathOrUrl) {
      final p = pathOrUrl.trim();
      if (p.isEmpty) return p;
      final normalized = p.startsWith('/') ? p : '/$p';
      if (!shouldIngressRewrite) return normalized;
      if (normalized.startsWith('/api/')) return normalized;
      if (normalized.startsWith('/media/') || normalized.startsWith('/audio/')) {
        return '/api$normalized';
      }
      return normalized;
    }

    // Already absolute → optionally rewrite localhost host and/or ingress path.
    final uri = Uri.tryParse(trimmed);
    if (uri != null && uri.hasScheme && uri.host.isNotEmpty) {
      // If backend responded with localhost but app runs on another host (web prod),
      // rewrite to current origin to satisfy CORS/mixed-content requirements.
      Uri fixed = uri;
      if (isLocal(fixed.host) && !isLocal(current.host)) {
        fixed = fixed.replace(
          scheme: current.scheme,
          host: current.host,
          // Keep explicit port only when current origin specifies one
          port: current.hasPort ? current.port : null,
        );
      }

      // If the absolute URL points to our same origin, make sure media goes through /api.
      if (shouldIngressRewrite && fixed.origin == current.origin) {
        final newPath = addApiPrefixIfNeeded(fixed.path);
        if (newPath != fixed.path) {
          fixed = fixed.replace(path: newPath);
        }
      }

      return fixed.toString();
    }

    // Relative path → prefix with API base URL
    final base = AppEnvironment.apiBaseUrl;
    final normalizedBase = base.endsWith('/')
        ? base.substring(0, base.length - 1)
        : base;
    final normalizedPath = addApiPrefixIfNeeded(trimmed);
    return '$normalizedBase$normalizedPath';
  }

  Widget _buildAnswerOptions(AssessmentQuestion question) {
    // Support text input for fill-in-the-blank questions
    if (question.questionType.toLowerCase() == 'fill_in_blank') {
      // Support multiple blanks: count underscores or infer from correctAnswerText split by comma
      final blanks = RegExp(r'____+').allMatches(question.question).length;
      final expectedParts = (question.correctAnswerText ?? '')
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
      final numFields = blanks > 0
          ? blanks
          : (expectedParts.isNotEmpty ? expectedParts.length : 1);
      if (_blankControllers.length != numFields) {
        for (final c in _blankControllers) {
          c.dispose();
        }
        _blankControllers = List.generate(
          numFields,
          (_) => TextEditingController(),
        );
      }
      
      // Determine if answers are correct after showing feedback
      List<bool> answerCorrectness = [];
      if (_showFeedback) {
        for (int i = 0; i < numFields; i++) {
          final userAnswer = _blankControllers[i].text.trim().toLowerCase();
          final expectedAnswer = i < expectedParts.length 
              ? expectedParts[i].toLowerCase() 
              : '';
          answerCorrectness.add(userAnswer == expectedAnswer);
        }
      }
      
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ...List.generate(numFields, (i) {
            final isAnswered = _showFeedback;
            final isCorrect = isAnswered && i < answerCorrectness.length 
                ? answerCorrectness[i] 
                : false;
            final expectedAnswer = i < expectedParts.length 
                ? expectedParts[i] 
                : '';
            
            return Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    key: ValueKey('fib_${question.id}_$i'),
                    controller: _blankControllers[i],
                    enabled: !_showFeedback,
                    decoration: InputDecoration(
                      hintText: numFields > 1 ? 'Blank ${i + 1}' : 'Type your answer',
                      filled: isAnswered,
                      fillColor: isAnswered
                          ? (isCorrect 
                              ? Colors.green.withValues(alpha: 0.1)
                              : Colors.red.withValues(alpha: 0.1))
                          : null,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide(
                          color: isAnswered
                              ? (isCorrect ? Colors.green : Colors.red)
                              : Theme.of(context).colorScheme.outline,
                          width: isAnswered ? 2 : 1,
                        ),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide(
                          color: isAnswered
                              ? (isCorrect ? Colors.green : Colors.red)
                              : Theme.of(context).colorScheme.outline,
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
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      suffixIcon: isAnswered
                          ? Icon(
                              isCorrect ? Icons.check_circle : Icons.cancel,
                              color: isCorrect ? Colors.green : Colors.red,
                            )
                          : null,
                    ),
                    onChanged: (_) {
                      final anyFilled = _blankControllers.any(
                        (c) => c.text.trim().isNotEmpty,
                      );
                      setState(() {
                        _selectedAnswerIndex = anyFilled ? 0 : null;
                      });
                    },
                  ),
                  // Show correct answer if wrong
                  if (isAnswered && !isCorrect && expectedAnswer.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 4, left: 4),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.lightbulb_outline,
                            size: 14,
                            color: Colors.green,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'Correct: $expectedAnswer',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Colors.green,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            );
          }),
        ],
      );
    }

    return Column(
      children: question.options.asMap().entries.map((entry) {
        final index = entry.key;
        final option = entry.value;
        final isSelected = _selectedAnswerIndex == index;
        final isCorrect = index == question.correctAnswerIndex;

        Color? cardColor;
        Color? borderColor;

        if (_showFeedback) {
          if (index == question.correctAnswerIndex) {
            cardColor = Colors.green.withValues(alpha: 0.1);
            borderColor = Colors.green;
          } else if (isSelected && !isCorrect) {
            cardColor = Colors.red.withValues(alpha: 0.1);
            borderColor = Colors.red;
          }
        } else if (isSelected) {
          cardColor = Theme.of(
            context,
          ).colorScheme.primary.withValues(alpha: 0.1);
          borderColor = Theme.of(context).colorScheme.primary;
        }

        return TweenAnimationBuilder<double>(
          duration: Duration(milliseconds: 400 + (index * 100)),
          tween: Tween<double>(begin: 0.0, end: 1.0),
          curve: Curves.elasticOut,
          builder: (context, value, child) {
            // Clamp value to ensure it stays within 0.0 to 1.0 range
            final clampedValue = value.clamp(0.0, 1.0);
            return Transform.translate(
              offset: Offset(20 * (1 - clampedValue), 0),
              child: Opacity(opacity: clampedValue, child: child),
            );
          },
          child: Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: GestureDetector(
              onTap: () => _selectAnswer(index),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: cardColor,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color:
                        borderColor ??
                        Theme.of(
                          context,
                        ).colorScheme.outline.withValues(alpha: 0.3),
                    width: borderColor != null ? 2 : 1,
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: isSelected
                            ? Theme.of(context).colorScheme.primary
                            : Theme.of(
                                context,
                              ).colorScheme.outline.withValues(alpha: 0.2),
                        shape: BoxShape.circle,
                      ),
                      child: Center(
                        child: Text(
                          String.fromCharCode(65 + index), // A, B, C, D
                          style: Theme.of(context).textTheme.titleSmall
                              ?.copyWith(
                                color: isSelected
                                    ? Theme.of(context).colorScheme.onPrimary
                                    : Theme.of(
                                        context,
                                      ).colorScheme.onSurfaceVariant,
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                      ),
                    ),

                    const SizedBox(width: 16),

                    Expanded(
                      child: Text(
                        option,
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: Theme.of(context).colorScheme.onSurface,
                          fontWeight: isSelected
                              ? FontWeight.w500
                              : FontWeight.normal,
                        ),
                      ),
                    ),

                    if (_showFeedback && index == question.correctAnswerIndex)
                      Icon(Icons.check_circle, color: Colors.green, size: 24)
                    else if (_showFeedback && isSelected && !isCorrect)
                      Icon(Icons.cancel, color: Colors.red, size: 24),
                  ],
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildFeedback(AssessmentQuestion question) {
    final isCorrect = _selectedAnswerIndex == question.correctAnswerIndex;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 500),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: isCorrect
            ? Colors.green.withValues(alpha: 0.1)
            : Colors.orange.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isCorrect ? Colors.green : Colors.orange,
          width: 1,
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
                size: 24,
              ),
              const SizedBox(width: 12),
              Text(
                isCorrect ? 'Correct!' : 'Not quite right',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: isCorrect ? Colors.green : Colors.orange,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Show correct answer for fill-in-the-blank questions
          if (question.questionType.toLowerCase() == 'fill_in_blank' &&
              (question.correctAnswerText != null &&
                  question.correctAnswerText!.trim().isNotEmpty)) ...[
            Text(
              'Correct answer: ${question.correctAnswerText}',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurface,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
          ],
          Text(
            question.explanation,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: BlocBuilder<OnboardingBloc, OnboardingState>(
        builder: (context, state) {
          if (state is AssessmentInProgressState &&
              state.isLoadingNextQuestion) {
            return AnimatedOnboardingButton(
              text: 'Loading next question...',
              isEnabled: false,
              isLoading: true,
              onPressed: null,
            );
          }

          // Determine button text and state
          final isFillBlank = widget.state.currentQuestion.questionType.toLowerCase() == 'fill_in_blank';
          final hasAnswer = _selectedAnswerIndex != null;
          final showingFeedback = _showFeedback;
          
          String buttonText;
          if (!hasAnswer) {
            buttonText = isFillBlank ? 'Type your answer' : 'Select an answer';
          } else if (isFillBlank && !showingFeedback) {
            buttonText = 'Check Answer';
          } else if (widget.state.isLastQuestion) {
            buttonText = 'Complete Assessment';
          } else {
            buttonText = 'Next Question';
          }
          
          return AnimatedOnboardingButton(
            text: buttonText,
            icon: widget.state.isLastQuestion && showingFeedback
                ? Icons.check
                : isFillBlank && !showingFeedback
                    ? Icons.spellcheck
                    : Icons.arrow_forward,
            isEnabled: hasAnswer,
            onPressed: hasAnswer ? _submitAnswer : null,
          );
        },
      ),
    );
  }

  void _selectAnswer(int index) {
    if (_showFeedback) return; // Don't allow changing after feedback shown

    setState(() {
      _selectedAnswerIndex = index;
    });

    // Show feedback immediately for better UX
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted && _selectedAnswerIndex == index) {
        setState(() {
          _showFeedback = true;
        });
      }
    });
  }

  void _submitAnswer() {
    final q = widget.state.currentQuestion;
    final timeSpent = DateTime.now().difference(_questionStartTime).inSeconds;

    if (q.questionType.toLowerCase() == 'fill_in_blank') {
      // For fill-in-blank: first click shows feedback, second click proceeds
      if (!_showFeedback) {
        // First click: show feedback (Check Answer)
        setState(() {
          _showFeedback = true;
        });
        return;
      }
      
      // Second click: proceed to next question
      _actuallySubmitFillBlankAnswer(q, timeSpent);
      return;
    }

    if (_selectedAnswerIndex == null) return;

    context.read<OnboardingBloc>().add(
      SubmitAssessmentAnswerEvent(
        questionId: q.id,
        selectedAnswerIndex: _selectedAnswerIndex!,
        timeSpentSeconds: timeSpent,
      ),
    );
  }

  void _actuallySubmitFillBlankAnswer(AssessmentQuestion q, int timeSpent) {
    final parts = _blankControllers
        .map((c) => c.text.trim())
        .where((s) => s.isNotEmpty)
        .toList();
    final textAnswer = parts.join(', ');
    context.read<OnboardingBloc>().add(
      SubmitAssessmentAnswerEvent(
        questionId: q.id,
        selectedAnswerIndex: 0,
        timeSpentSeconds: timeSpent,
        textAnswer: textAnswer,
      ),
    );
  }

  void _showExitDialog() {
    // Capture the bloc from the parent context before showing dialog
    final onboardingBloc = context.read<OnboardingBloc>();

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.orange.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.warning_amber_rounded,
                color: Colors.orange,
                size: 24,
              ),
            ),
            const SizedBox(width: 12),
            const Text('Exit Assessment?'),
          ],
        ),
        content: const Text(
          'Your progress will be lost if you exit now. You can take the assessment again later from your profile.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Continue Assessment'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(dialogContext).pop(); // Close dialog
              onboardingBloc.add(CancelAssessmentEvent());
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Theme.of(dialogContext).colorScheme.error,
              foregroundColor: Theme.of(dialogContext).colorScheme.onError,
            ),
            child: const Text('Exit'),
          ),
        ],
      ),
    );
  }

  Color _getSkillColor(String skillType) {
    switch (skillType.toLowerCase()) {
      case 'grammar':
        return Colors.blue;
      case 'vocabulary':
        return Colors.purple;
      case 'reading':
        return Colors.green;
      case 'listening':
        return Colors.orange;
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }

  IconData _getSkillIcon(String skillType) {
    switch (skillType.toLowerCase()) {
      case 'grammar':
        return Icons.spellcheck;
      case 'vocabulary':
        return Icons.translate;
      case 'reading':
        return Icons.menu_book;
      case 'listening':
        return Icons.hearing;
      default:
        return Icons.quiz;
    }
  }
}
