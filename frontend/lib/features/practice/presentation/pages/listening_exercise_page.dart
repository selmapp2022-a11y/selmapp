import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:just_audio/just_audio.dart';

import '../../../../core/config/app_environment.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../data/repositories/practice_repository.dart';
import '../../data/models/exercise_models.dart';

class ListeningExercisePage extends StatefulWidget {
  final ListeningExercise exercise;

  const ListeningExercisePage({super.key, required this.exercise});

  @override
  State<ListeningExercisePage> createState() => _ListeningExercisePageState();
}

class _ListeningExercisePageState extends State<ListeningExercisePage> {
  final AudioPlayer _audioPlayer = AudioPlayer();
  late final PracticeRepositoryImpl _repository;
  late ListeningExercise _exercise;
  bool _attemptedRegeneration = false;
  bool _listenersAttached = false;

  int _currentQuestionIndex = 0;
  final Map<int, String> _selectedAnswers = {};
  bool _showResults = false;
  bool _showTranscript = false;
  bool _isPlaying = false;
  bool _isLoading = false;
  Duration _duration = Duration.zero;
  Duration _position = Duration.zero;
  int _playCount = 0;
  bool _audioAvailable = false;
  String? _audioError;
  
  // Audio polling state
  bool _isPollingForAudio = false;

  // Accent preference: 'american' (Sarah) or 'british' (Charlotte).
  // Persisted in SecureStorage under `pref.tts_accent`.
  String _accent = 'american';
  static const String _kAccentPrefKey = 'pref.tts_accent';
  late final SecureStorage _storage;

  @override
  void initState() {
    super.initState();
    _exercise = widget.exercise;
    _storage = SecureStorage();
    _repository = PracticeRepositoryImpl(ApiClient(_storage));
    _attachPlayerListeners();
    _loadAccentPreference().then((_) => _setupAudio());
  }

  Future<void> _loadAccentPreference() async {
    try {
      final saved = await _storage.read(_kAccentPrefKey);
      if (saved != null && (saved == 'american' || saved == 'british')) {
        if (mounted) setState(() => _accent = saved);
      }
    } catch (_) {/* keep default */}
  }

  Future<void> _setAccent(String accent) async {
    if (accent != 'american' && accent != 'british') return;
    if (accent == _accent) return;
    setState(() => _accent = accent);
    try {
      await _storage.write(_kAccentPrefKey, accent);
    } catch (_) {/* non-fatal */}
    if (_exercise.transcript.trim().isNotEmpty) {
      _attemptedRegeneration = false;
      await _tryGenerateAudioFromTranscript();
    }
  }

  void _attachPlayerListeners() {
    if (_listenersAttached) return;
    _listenersAttached = true;

    // Explicitly set playback speed to 1.0x to prevent fast-forward on some Android devices
    _audioPlayer.setSpeed(1.0);

    _audioPlayer.durationStream.listen((d) {
      if (d != null && mounted) {
        setState(() {
          _duration = d;
        });
      }
    });

    _audioPlayer.positionStream.listen((p) {
      if (mounted) {
        setState(() => _position = p);
      }
    });

    _audioPlayer.playerStateStream.listen((state) {
      if (mounted) {
        setState(() {
          _isPlaying = state.playing;
          if (state.processingState == ProcessingState.completed) {
            _isPlaying = false;
            _position = Duration.zero;
            _audioPlayer.seek(Duration.zero);
            _audioPlayer.pause();
          }
        });
      }
    });
  }

  String _resolveAudioUrl(String url) {
    final trimmed = url.trim();
    if (trimmed.isEmpty) return trimmed;

    final current = Uri.base;
    bool isLocalHost(String host) =>
        host == 'localhost' || host == '127.0.0.1' || host.endsWith('.local');

    // In production (DigitalOcean / nginx), the app and API are often served behind the same origin,
    // but the backend is routed through an ingress prefix like `/api/*`.
    // The backend may return media links as `/media/...` (or absolute `https://host/media/...`).
    // On the public site those paths 404 unless they go through `/api/media/...`.
    final apiBaseUri = Uri.tryParse(AppEnvironment.apiBaseUrl);
    final sameOriginApi = apiBaseUri != null && apiBaseUri.origin == current.origin;
    final shouldIngressRewrite = kIsWeb && sameOriginApi && !isLocalHost(current.host);

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

    final uri = Uri.tryParse(trimmed);

    // Absolute URL
    if (uri != null && uri.hasScheme && uri.host.isNotEmpty) {
      Uri fixed = uri;

      // Backend may build links using localhost; rewrite to the configured API host.
      final isLocal = isLocalHost(fixed.host);
      if (isLocal && apiBaseUri != null) {
        fixed = fixed.replace(
          scheme: apiBaseUri.scheme,
          host: apiBaseUri.host,
          port: apiBaseUri.hasPort ? apiBaseUri.port : null,
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

    // Relative path → prefix with API base URL (origin)
    final base = AppEnvironment.apiBaseUrl;
    final normalizedBase = base.endsWith('/') ? base.substring(0, base.length - 1) : base;
    final normalizedPath = addApiPrefixIfNeeded(trimmed);
    return '$normalizedBase$normalizedPath';
  }

  String _extractTopicFromTitle(String title) {
    var topic = title;
    topic = topic.replaceAll(RegExp(r'listening', caseSensitive: false), '');
    topic = topic.replaceAll(RegExp(r'practice', caseSensitive: false), '');
    topic = topic.replaceAll(RegExp(r'[-–•]'), ' ');
    topic = topic.replaceAll(RegExp(r'\s+'), ' ').trim();
    return topic.isNotEmpty ? topic : 'Daily Conversation';
  }

  /// Generate TTS audio for the current transcript WITHOUT changing the transcript/questions.
  /// This prevents the user from seeing one text in "Reading Mode" and a different text once audio loads.
  Future<void> _tryGenerateAudioFromTranscript() async {
    final transcript = _exercise.transcript.trim();
    if (transcript.isEmpty) return;

    setState(() {
      _isLoading = true;
      _audioAvailable = false;
      _audioError = 'Generating audio for this transcript...';
      _showTranscript = true;
    });

    try {
      final audioUrl = await _repository.generateGeminiTtsAudio(
        text: transcript,
        audioType: 'conversation',
        accent: _accent,
      );

      if (!mounted) return;

      if (audioUrl != null && audioUrl.isNotEmpty) {
        // Update ONLY the audio URL, keep transcript/questions stable.
        setState(() {
          _exercise = ListeningExercise(
            id: _exercise.id,
            title: _exercise.title,
            description: _exercise.description,
            level: _exercise.level,
            estimatedDurationMinutes: _exercise.estimatedDurationMinutes,
            points: _exercise.points,
            tags: _exercise.tags,
            audioUrl: audioUrl,
            transcript: _exercise.transcript,
            questions: _exercise.questions,
            durationSeconds: _exercise.durationSeconds,
            imageUrl: _exercise.imageUrl,
          );
          _audioError = null;
        });

        // Try to set up the audio player with the new URL
        await _setupAudioWithUrl(audioUrl);
      } else {
        setState(() {
          _audioAvailable = false;
          _audioError = 'Audio is not available right now. You can continue in Reading Mode.';
          _showTranscript = true;
        });
      }
    } catch (e) {
      debugPrint('Failed to generate audio for transcript: $e');
      if (mounted) {
        setState(() {
          _audioAvailable = false;
          _audioError = 'Could not generate audio. You can continue in Reading Mode.';
          _showTranscript = true;
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _tryGenerateListeningExercise() async {
    if (_attemptedRegeneration) return;
    _attemptedRegeneration = true;

    setState(() {
      _isLoading = true;
      _audioError = 'Generating audio...';
      _showTranscript = true;
    });

    try {
      final generated = await _repository.generateListeningExercise(
        topic: _extractTopicFromTitle(_exercise.title),
        contentType: 'conversation',
        accent: _accent,
      );

      if (!mounted) return;

      if (generated != null) {
        setState(() {
          _exercise = generated;
          _currentQuestionIndex = 0;
          _selectedAnswers.clear();
          _showResults = false;
          _playCount = 0;
          _duration = Duration.zero;
          _position = Duration.zero;
          _audioAvailable = false;
          _audioError = null;
        });
        
        // If audio URL is empty but we have a transcript, generate audio for THIS transcript
        // (keeps text/questions stable).
        if (generated.audioUrl.isEmpty && generated.transcript.isNotEmpty) {
          await _tryGenerateAudioFromTranscript();
        } else if (generated.audioUrl.isEmpty && !_isPollingForAudio) {
          // Fallback (older backend behavior): poll for audio URL
          _startAudioPolling();
        }
      }
    } catch (e) {
      debugPrint('Failed to generate listening exercise: $e');
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  /// Start polling for audio availability in the background
  Future<void> _startAudioPolling() async {
    if (_isPollingForAudio) return;
    
    setState(() {
      _isPollingForAudio = true;
      _audioError = 'Audio is generating... You can read the transcript while waiting.';
    });

    try {
      final audioUrl = await _repository.pollForAudio(
        exerciseId: _exercise.id,
        maxRetries: 5,
        interval: const Duration(seconds: 3),
      );

      if (!mounted) return;

      if (audioUrl != null && audioUrl.isNotEmpty) {
        // Audio is now available - update exercise and try to play
        setState(() {
          _exercise = ListeningExercise(
            id: _exercise.id,
            title: _exercise.title,
            description: _exercise.description,
            level: _exercise.level,
            estimatedDurationMinutes: _exercise.estimatedDurationMinutes,
            points: _exercise.points,
            tags: _exercise.tags,
            audioUrl: audioUrl,
            transcript: _exercise.transcript,
            questions: _exercise.questions,
            durationSeconds: _exercise.durationSeconds,
          );
          _audioError = null;
          _isPollingForAudio = false;
        });
        
        // Try to set up the audio player with the new URL
        await _setupAudioWithUrl(audioUrl);
      } else {
        setState(() {
          _isPollingForAudio = false;
          _audioError = 'Audio generation is taking longer than expected. You can continue with Reading Mode.';
        });
      }
    } catch (e) {
      debugPrint('Error polling for audio: $e');
      if (mounted) {
        setState(() {
          _isPollingForAudio = false;
          _audioError = 'Could not load audio. Continue with Reading Mode.';
        });
      }
    }
  }

  /// Set up audio player with a specific URL
  Future<void> _setupAudioWithUrl(String url) async {
    try {
      await _audioPlayer.setUrl(_resolveAudioUrl(url));
      if (!mounted) return;
      setState(() {
        _audioAvailable = true;
        _audioError = null;
        _showTranscript = false;
      });
    } catch (e) {
      debugPrint('Error setting up audio with URL: $e');
      if (mounted) {
        setState(() {
          _audioAvailable = false;
          _audioError = 'Could not play audio';
        });
      }
    }
  }

  Future<void> _setupAudio() async {
    final hasAudio = _exercise.audioUrl.trim().isNotEmpty;
    final hasTranscript = _exercise.transcript.trim().isNotEmpty;

    // Prefer generating audio for the existing transcript (stable content).
    if (!hasAudio && hasTranscript) {
      await _tryGenerateAudioFromTranscript();
      if (!mounted) return;
      // If audio was successfully generated and loaded, we can stop here.
      if (_audioAvailable) return;
    }

    // As a last resort (no transcript or still no audio), generate a brand-new listening exercise.
    if (_exercise.audioUrl.trim().isEmpty && !hasTranscript) {
      await _tryGenerateListeningExercise();
    }

    if (_exercise.audioUrl.trim().isEmpty) {
      if (!mounted) return;
      setState(() {
        _audioAvailable = false;
        _audioError = 'Audio not available. Continue in Reading Mode.';
        _showTranscript = true;
      });
      return;
    }

    setState(() => _isLoading = true);

    try {
      await _audioPlayer.setUrl(_resolveAudioUrl(_exercise.audioUrl));
      if (!mounted) return;
      setState(() {
        _audioAvailable = true;
        _audioError = null;
      });
    } catch (e) {
      debugPrint('Error setting up audio: $e');

      // If we had an audio URL but it wasn't playable, prefer generating fresh audio
      // for the existing transcript (keeps text/questions stable).
      if (_exercise.transcript.trim().isNotEmpty) {
        await _tryGenerateAudioFromTranscript();
        if (!mounted) return;
        if (_audioAvailable) return;
      }

      // Last resort: generate a brand-new listening exercise (may change transcript)
      if (!_attemptedRegeneration) {
        await _tryGenerateListeningExercise();
        if (_exercise.audioUrl.isNotEmpty) {
          try {
            await _audioPlayer.setUrl(_resolveAudioUrl(_exercise.audioUrl));
            if (!mounted) return;
            setState(() {
              _audioAvailable = true;
              _audioError = null;
            });
          } catch (e) {
            debugPrint('Error setting up regenerated audio: $e');
          }
        }
      }

      if (!mounted) return;
      setState(() {
        _audioAvailable = false;
        _audioError = 'Audio not available. Continue in Reading Mode.';
        _showTranscript = true;
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> _togglePlay() async {
    if (_isPlaying) {
      await _audioPlayer.pause();
    } else {
      if (_playCount == 0) {
        _playCount++;
      }
      await _audioPlayer.play();
    }
  }

  String _formatDuration(Duration duration) {
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    final minutes = twoDigits(duration.inMinutes.remainder(60));
    final seconds = twoDigits(duration.inSeconds.remainder(60));
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF1a1a2e), Color(0xFF16213e), Color(0xFF0f3460)],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              _buildAppBar(),
              Expanded(
                child: _showResults
                    ? _buildResultsView()
                    : Column(
                        children: [
                          _buildAudioPlayer(),
                          Expanded(child: _buildQuestionsView()),
                        ],
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAppBar() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back, color: Colors.white),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _exercise.title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  '${_exercise.durationSeconds ~/ 60}:${(_exercise.durationSeconds % 60).toString().padLeft(2, '0')} • ${_exercise.questions.length} questions',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.7),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          _buildAccentPicker(),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.orange.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                const Icon(Icons.star, color: Colors.amber, size: 16),
                const SizedBox(width: 4),
                Text(
                  '${_exercise.points}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Compact American/British accent toggle. Tapping switches the saved
  /// preference and regenerates the audio for the current transcript.
  Widget _buildAccentPicker() {
    Widget chip(String value, String label, String flag) {
      final selected = _accent == value;
      return GestureDetector(
        onTap: _isLoading ? null : () => _setAccent(value),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: selected
                ? const Color(0xFF2EC4B6).withValues(alpha: 0.85)
                : Colors.white.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(flag, style: const TextStyle(fontSize: 13)),
              const SizedBox(width: 4),
              Text(
                label,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Tooltip(
      message: 'Choose accent',
      child: Container(
        padding: const EdgeInsets.all(2),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white.withValues(alpha: 0.15)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            chip('american', 'US', '🇺🇸'),
            const SizedBox(width: 2),
            chip('british', 'UK', '🇬🇧'),
          ],
        ),
      ),
    );
  }

  Widget _buildAudioPlayer() {
    // Show reading mode when audio is not available
    if (!_audioAvailable && _audioError != null) {
      return Container(
        margin: const EdgeInsets.all(16),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Colors.blue.withValues(alpha: 0.3),
              Colors.indigo.withValues(alpha: 0.2),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: Colors.blue.withValues(alpha: 0.3),
          ),
        ),
        child: Column(
          children: [
            Row(
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Colors.blue, Colors.indigo],
                    ),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.menu_book,
                    color: Colors.white,
                    size: 32,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Reading Mode',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Read the transcript below and answer the questions',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.8),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_audioError != null) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  children: [
                    if (_isLoading)
                      const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70),
                      )
                    else
                      const Icon(Icons.info_outline, size: 18, color: Colors.white70),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        _audioError ?? '',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.85),
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
            ],
            // Always show transcript in reading mode
            if (_exercise.transcript.isNotEmpty) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.format_quote, color: Colors.white70, size: 18),
                        const SizedBox(width: 8),
                        Text(
                          'Transcript',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _exercise.transcript,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.9),
                        fontSize: 15,
                        height: 1.6,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _isLoading
                    ? null
                    : () async {
                        if (_exercise.transcript.trim().isNotEmpty) {
                          await _tryGenerateAudioFromTranscript();
                        } else {
                          await _tryGenerateListeningExercise();
                        }
                      },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white.withValues(alpha: 0.18),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                icon: const Icon(Icons.volume_up, size: 18),
                label: Text(
                  _exercise.transcript.trim().isNotEmpty ? 'Generate Audio for This Text' : 'Generate Listening Audio',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.orange.withValues(alpha: 0.3),
            Colors.deepOrange.withValues(alpha: 0.2),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: Colors.orange.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              // Play button
              GestureDetector(
                onTap: _isLoading ? null : _togglePlay,
                child: Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Colors.orange, Colors.deepOrange],
                    ),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.orange.withValues(alpha: 0.4),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: _isLoading
                      ? const Center(
                          child: SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          ),
                        )
                      : Icon(
                          _isPlaying ? Icons.pause : Icons.play_arrow,
                          color: Colors.white,
                          size: 32,
                        ),
                ),
              ),
              
              const SizedBox(width: 16),
              
              // Progress and time
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          _formatDuration(_position),
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.8),
                            fontSize: 12,
                          ),
                        ),
                        Text(
                          _formatDuration(_duration),
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.8),
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    SliderTheme(
                      data: SliderTheme.of(context).copyWith(
                        activeTrackColor: Colors.orange,
                        inactiveTrackColor: Colors.white.withValues(alpha: 0.2),
                        thumbColor: Colors.white,
                        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                        trackHeight: 4,
                      ),
                      child: Slider(
                        value: _duration.inMilliseconds > 0
                            ? _position.inMilliseconds / _duration.inMilliseconds
                            : 0,
                        onChanged: (value) {
                          final newPosition = Duration(
                            milliseconds: (value * _duration.inMilliseconds).round(),
                          );
                          _audioPlayer.seek(newPosition);
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 12),
          
          // Transcript toggle
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              TextButton.icon(
                onPressed: () => setState(() => _showTranscript = !_showTranscript),
                icon: Icon(
                  _showTranscript ? Icons.visibility_off : Icons.visibility,
                  size: 18,
                  color: Colors.white70,
                ),
                label: Text(
                  _showTranscript ? 'Hide Transcript' : 'Show Transcript',
                  style: const TextStyle(color: Colors.white70),
                ),
              ),
              if (_playCount > 0) ...[
                const SizedBox(width: 16),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.headphones, size: 14, color: Colors.white.withValues(alpha: 0.7)),
                      const SizedBox(width: 4),
                      Text(
                        'Played $_playCount ${_playCount == 1 ? 'time' : 'times'}',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.7),
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
          
          // Transcript
          if (_showTranscript && _exercise.transcript.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                _exercise.transcript,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.9),
                  fontSize: 14,
                  height: 1.6,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildQuestionsView() {
    final question = _exercise.questions[_currentQuestionIndex];
    final isAnswered = _selectedAnswers.containsKey(_currentQuestionIndex);

    return Column(
      children: [
        // Progress
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              Expanded(
                child: LinearProgressIndicator(
                  value: (_currentQuestionIndex + 1) / _exercise.questions.length,
                  backgroundColor: Colors.white.withValues(alpha: 0.2),
                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.orange),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                'Q${_currentQuestionIndex + 1}/${_exercise.questions.length}',
                style: const TextStyle(color: Colors.white70, fontSize: 14),
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // Question
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: Colors.white.withValues(alpha: 0.2),
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.orange.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.help_outline, color: Colors.orange),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          question.question,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 20),

                // Options
                ...question.options.asMap().entries.map((entry) {
                  final index = entry.key;
                  final option = entry.value;
                  final isSelected = _selectedAnswers[_currentQuestionIndex] == option;
                  final letter = String.fromCharCode(65 + index);

                  return Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: GestureDetector(
                      onTap: () {
                        setState(() {
                          _selectedAnswers[_currentQuestionIndex] = option;
                        });
                      },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          gradient: isSelected
                              ? LinearGradient(
                                  colors: [
                                    Colors.orange.withValues(alpha: 0.3),
                                    Colors.orange.withValues(alpha: 0.1),
                                  ],
                                )
                              : null,
                          color: isSelected ? null : Colors.white.withValues(alpha: 0.05),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(
                            color: isSelected
                                ? Colors.orange
                                : Colors.white.withValues(alpha: 0.2),
                            width: isSelected ? 2 : 1,
                          ),
                        ),
                        child: Row(
                          children: [
                            Container(
                              width: 32,
                              height: 32,
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? Colors.orange
                                    : Colors.white.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Center(
                                child: Text(
                                  letter,
                                  style: TextStyle(
                                    color: isSelected ? Colors.white : Colors.white70,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                option,
                                style: TextStyle(
                                  color: isSelected ? Colors.white : Colors.white70,
                                  fontSize: 14,
                                ),
                              ),
                            ),
                            if (isSelected)
                              const Icon(Icons.check_circle, color: Colors.orange, size: 22),
                          ],
                        ),
                      ),
                    ),
                  );
                }),
              ],
            ),
          ),
        ),

        // Navigation
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              if (_currentQuestionIndex > 0)
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      setState(() => _currentQuestionIndex--);
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white30),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text('Previous'),
                  ),
                ),
              if (_currentQuestionIndex > 0) const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: ElevatedButton(
                  onPressed: isAnswered
                      ? () {
                          if (_currentQuestionIndex < _exercise.questions.length - 1) {
                            setState(() => _currentQuestionIndex++);
                          } else {
                            setState(() => _showResults = true);
                          }
                        }
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.orange,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: Colors.grey.withValues(alpha: 0.3),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: Text(
                    _currentQuestionIndex < _exercise.questions.length - 1
                        ? 'Next'
                        : 'Finish',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildResultsView() {
    int correct = 0;
    for (int i = 0; i < _exercise.questions.length; i++) {
      if (_selectedAnswers[i] == _exercise.questions[i].correctAnswer) {
        correct++;
      }
    }

    final percentage = (correct / _exercise.questions.length * 100).round();
    final pointsEarned = (_exercise.points * correct / _exercise.questions.length).round();

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: percentage >= 70
                      ? [Colors.green, Colors.teal]
                      : percentage >= 50
                          ? [Colors.orange, Colors.amber]
                          : [Colors.red, Colors.orange],
                ),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: (percentage >= 70 ? Colors.green : Colors.orange)
                        .withValues(alpha: 0.4),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '$percentage%',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 32,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    '$correct/${_exercise.questions.length}',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.8),
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 32),
            
            Text(
              percentage >= 70
                  ? '🎉 Great Listening!'
                  : percentage >= 50
                      ? '👍 Good Progress!'
                      : '💪 Keep Practicing!',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            
            const SizedBox(height: 12),
            
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              decoration: BoxDecoration(
                color: Colors.amber.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.star, color: Colors.amber, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    '+$pointsEarned points',
                    style: const TextStyle(
                      color: Colors.amber,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 40),
            
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.orange,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: const Text(
                  'Continue',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}







