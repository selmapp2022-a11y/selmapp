import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:universal_io/io.dart' as io;
import 'package:just_audio/just_audio.dart';
import 'package:selmapp/core/api/speaking_api.dart';
import 'package:selmapp/core/models/speaking_models.dart';
import 'package:selmapp/core/network/api_client.dart';
import 'package:selmapp/core/storage/secure_storage.dart';
import 'package:selmapp/features/speaking/recording_controller.dart';
import '../../data/models/exercise_models.dart';
import '../../data/repositories/practice_repository.dart';
import '../../../progress/data/repositories/progress_repository.dart';
import '../widgets/enhanced_speaking_interface.dart';
import '../../../../core/widgets/rive_coach_widget.dart';

class SpeakingExercisePage extends StatefulWidget {
  final SpeakingExercise exercise;

  const SpeakingExercisePage({super.key, required this.exercise});

  @override
  State<SpeakingExercisePage> createState() => _SpeakingExercisePageState();
}

class _SpeakingExercisePageState extends State<SpeakingExercisePage>
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late AnimationController _waveController;
  
  bool isRecording = false;
  bool hasRecorded = false;
  int recordingDuration = 0;
  int _remainingSeconds = 0; // Countdown timer
  String? _recordedPath;
  final RecordingController _recorder = RecordingController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  bool _isPlaying = false;
  List<AITrainerMessage> trainerMessages = [];
  String? aiAnalysis;
  int pronunciationScore = 0;
  List<String> suggestions = [];
  bool isAnalyzing = false;
  SpeechEvaluateResponseModel? _evaluationResult;
  late final PracticeRepositoryImpl _practiceRepository;
  late final ProgressRepository _progressRepository;
  DateTime _exerciseStartTime = DateTime.now();
  bool _isCompleting = false;
  String? _generatedImageUrl;
  bool _isLoadingImage = false;

  @override
  void initState() {
    super.initState();

    final apiClient = ApiClient(SecureStorage());
    _practiceRepository = PracticeRepositoryImpl(apiClient);
    _progressRepository = ProgressRepositoryImpl(apiClient);
    _exerciseStartTime = DateTime.now();
    
    // Explicitly set playback speed to 1.0x to prevent fast-forward on some Android devices
    _audioPlayer.setSpeed(1.0);
    
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
    
    _waveController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    _addTrainerMessage(
      'Ready to practice speaking? I\'ll listen to your pronunciation and give you personalized feedback. Take your time!',
      AITrainerMessageType.welcome,
    );
    
    // Load image if needed for the exercise
    _loadExerciseImage();
  }
  
  Future<void> _loadExerciseImage() async {
    // Check if exercise already has an image or needs one generated
    if (widget.exercise.imageUrl != null && widget.exercise.imageUrl!.isNotEmpty) {
      setState(() => _generatedImageUrl = widget.exercise.imageUrl);
      return;
    }
    
    // Generate image for certain speaking types
    if (widget.exercise.speakingType == SpeakingExerciseType.description ||
        widget.exercise.speakingType == SpeakingExerciseType.storytelling) {
      setState(() => _isLoadingImage = true);
      
      try {
        final apiClient = ApiClient(SecureStorage());
        final response = await apiClient.post(
          '/ai/generate-speaking-image',
          data: {
            'prompt': widget.exercise.prompt,
            'speaking_type': widget.exercise.speakingType.name,
            'user_level': widget.exercise.level.name,
          },
        );
        
        if (response.statusCode == 200 && response.data['success'] == true) {
          if (mounted) {
            setState(() {
              _generatedImageUrl = response.data['image_url'];
              _isLoadingImage = false;
            });
          }
        }
      } catch (e) {
        debugPrint('Failed to load exercise image: $e');
      }
      
      if (mounted) {
        setState(() => _isLoadingImage = false);
      }
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _waveController.dispose();
    _audioPlayer.dispose();
    _recorder.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: Text(widget.exercise.title),
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.white,
        elevation: 0,
        actions: [
          IconButton(
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.close),
            tooltip: 'Close',
          ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF1a1a2e), Color(0xFF16213e), Color(0xFF0f3460)],
            stops: [0.0, 0.5, 1.0],
          ),
        ),
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            16,
            MediaQuery.of(context).padding.top + kToolbarHeight + 8,
            16,
            24,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Coach presence (replaces the old list of trainer messages)
              CoachWithBubble(
                message: trainerMessages.isNotEmpty
                    ? trainerMessages.last.message
                    : "Ready to practice speaking? I'll listen to your pronunciation and give you personalized feedback. Take your time!",
                state: _getCoachStateForSession(),
                coachSize: 72,
                animateMessage: true,
              ),

              const SizedBox(height: 24),

              // Speaking Prompt Card
              _buildPromptCard(),

              const SizedBox(height: 24),

              // Key Words Section
              _buildKeyWordsSection(),

              const SizedBox(height: 28),

              // Recording Interface (enhanced)
              _buildRecordingInterface(),

              const SizedBox(height: 24),

              // Detailed AI Analysis Results (optional, keeps existing details)
              if (aiAnalysis != null) _buildAnalysisResults(),

              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }

  CoachState _getCoachStateForSession() {
    if (isRecording) return CoachState.listening;
    if (isAnalyzing) return CoachState.thinking;
    if (aiAnalysis != null) {
      if (pronunciationScore >= 80) return CoachState.celebrating;
      if (pronunciationScore >= 60) return CoachState.happy;
      return CoachState.encouraging;
    }
    return CoachState.speaking;
  }

  /// Get the reference text that will be used for pronunciation scoring
  String _getReferenceText() {
    String normalize(String input) {
      var s = input.trim().replaceAll(RegExp(r'\s+'), ' ');
      if (s.isEmpty) return s;
      if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
        s = s.substring(1, s.length - 1).trim();
      }
      if (s.isEmpty) return s;
      s = s[0].toUpperCase() + s.substring(1);
      if (!RegExp(r'[.!?]$').hasMatch(s)) {
        s = '$s.';
      }
      return s;
    }

    // For this app's speaking practice, the prompt is the reference sentence to read aloud.
    final prompt = widget.exercise.prompt;
    if (prompt.trim().isNotEmpty) return normalize(prompt);

    // Fallback for malformed content
    final kws = widget.exercise.keyWords.map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    return kws.isNotEmpty ? normalize(kws.join(' ')) : '';
  }
  
  /// Check if this exercise type requires showing a reference text to read
  bool _isPronunciationBasedExercise() {
    return widget.exercise.speakingType == SpeakingExerciseType.pronunciation ||
           widget.exercise.speakingType == SpeakingExerciseType.conversation;
  }

  Widget _buildPromptCard() {
    final isPronunciationBased = _isPronunciationBasedExercise();
    
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Colors.red, Colors.deepOrange],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.red.withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with exercise type
            Row(
              children: [
                Icon(
                  _getSpeakingTypeIcon(widget.exercise.speakingType),
                  color: Colors.white,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    widget.exercise.speakingType.name.toUpperCase(),
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
            
            // Instructions - brief and clear
            if (!isPronunciationBased) ...[
              Text(
                'Speaking Task:',
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
                  fontSize: 16,
                  height: 1.4,
                ),
              ),
            ] else ...[
              // For pronunciation exercises, show clear instruction
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.white.withValues(alpha: 0.9), size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Read the text below clearly. Your pronunciation will be scored.',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.95),
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            
            const SizedBox(height: 16),
            
            // Time and points badges
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.timer, color: Colors.white, size: 16),
                      const SizedBox(width: 4),
                      Text(
                        'Max ${widget.exercise.maxRecordingSeconds}s',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.star, color: Colors.amber, size: 16),
                      const SizedBox(width: 4),
                      Text(
                        '${widget.exercise.points} pts',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildKeyWordsSection() {
    final referenceText = _getReferenceText();
    final isPronunciationBased = _isPronunciationBasedExercise();
    
    // For pronunciation-based exercises, show clear "Read This Text" section
    if (isPronunciationBased) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.green.withValues(alpha: 0.3), width: 2),
          boxShadow: [
            BoxShadow(
              color: Colors.green.withValues(alpha: 0.1),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Clear header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.green,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Icon(
                      Icons.mic,
                      color: Colors.white,
                      size: 18,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '📖 Read This Text Aloud:',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: Colors.green[800],
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'This is the exact text your pronunciation will be scored on',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            
            // The reference text to read - prominent and clear
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.green.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.green.withValues(alpha: 0.2)),
              ),
              child: Text(
                referenceText,
                style: TextStyle(
                  color: Colors.grey[800],
                  fontSize: 18,
                  fontWeight: FontWeight.w500,
                  height: 1.6,
                ),
              ),
            ),
            
            // Hint about vocabulary
            if (widget.exercise.keyWords.isNotEmpty && 
                !widget.exercise.keyWords.any((kw) => kw.contains(' '))) ...[
              const SizedBox(height: 12),
              Text(
                '💡 Key vocabulary: ${widget.exercise.keyWords.join(', ')}',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ],
        ),
      );
    }
    
    // For description/storytelling exercises (non-pronunciation based)
    // Show image if available and keywords as suggestions
    return Column(
      children: [
        // Image section for description exercises
        if (_generatedImageUrl != null || _isLoadingImage) ...[
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.1),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: _isLoadingImage
                  ? Container(
                      height: 180,
                      width: double.infinity,
                      color: Colors.grey[200],
                      child: const Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            CircularProgressIndicator(),
                            SizedBox(height: 12),
                            Text('Generating image...'),
                          ],
                        ),
                      ),
                    )
                  : Image.network(
                      _generatedImageUrl!.startsWith('http') 
                          ? _generatedImageUrl!
                          : 'YOUR_BASE_URL$_generatedImageUrl',
                      height: 180,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) {
                        return Container(
                          height: 180,
                          color: Colors.grey[200],
                          child: Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.image_not_supported, color: Colors.grey[400], size: 48),
                                const SizedBox(height: 8),
                                Text('Image unavailable', style: TextStyle(color: Colors.grey[600])),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ),
          const SizedBox(height: 16),
        ],
        
        // Keywords as suggestions for open-ended exercises
        if (widget.exercise.keyWords.isNotEmpty)
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
                      Icons.lightbulb_outline,
                      color: Colors.orange[700],
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Suggested phrases to use:',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Colors.orange[800],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...widget.exercise.keyWords.map((phrase) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: Colors.orange.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.orange.withValues(alpha: 0.2)),
                      ),
                      child: Row(
                        children: [
                          Text('•', style: TextStyle(color: Colors.orange[700], fontWeight: FontWeight.bold)),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              phrase,
                              style: TextStyle(
                                color: Colors.grey[800],
                                fontSize: 14,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildRecordingInterface() {
    return EnhancedSpeakingInterface(
      isRecording: isRecording,
      isAnalyzing: isAnalyzing,
      hasResult: aiAnalysis != null,
      recordingDuration: recordingDuration,
      maxDuration: widget.exercise.maxRecordingSeconds,
      statusMessage: isRecording
          ? 'Recording... $_remainingSeconds s remaining'
          : hasRecorded
              ? 'Recording complete! Ready for feedback'
              : 'Tap the mic to start (max ${widget.exercise.maxRecordingSeconds}s)',
      coachMessage: trainerMessages.isNotEmpty ? trainerMessages.last.message : null,
      score: aiAnalysis != null ? pronunciationScore : null,
      suggestions: suggestions,
      onStartRecording: _toggleRecording,
      onStopRecording: _toggleRecording,
      onPlayRecording: hasRecorded ? () => _playRecording() : null,
      onRetry: _tryAgain,
    );
  }

  Widget _buildAnalysisResults() {
    final scoreColor = pronunciationScore >= 80
        ? Colors.green
        : pronunciationScore >= 60
            ? Colors.orange
            : Colors.red;

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
              const Icon(
                Icons.analytics,
                color: Colors.red,
                size: 24,
              ),
              const SizedBox(width: 8),
              Text(
                'AI Analysis Results',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.red,
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 20),
          
          // Overall Score Circle
          Center(
            child: Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    scoreColor.withValues(alpha: 0.2),
                    scoreColor.withValues(alpha: 0.1),
                  ],
                ),
                border: Border.all(color: scoreColor, width: 4),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '$pronunciationScore',
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.bold,
                      color: scoreColor,
                    ),
                  ),
                  Text(
                    'Score',
                    style: TextStyle(
                      fontSize: 14,
                      color: scoreColor,
                    ),
                  ),
                ],
              ),
            ),
          ),
          
          const SizedBox(height: 24),
          
          // Detailed Metrics (if available from SpeechAce - pronunciation-only plan)
          if (_evaluationResult != null) ...[
            Row(
              children: [
                // Pronunciation score (main metric from Speechace)
                if (_evaluationResult!.pronunciationScore != null &&
                    _evaluationResult!.pronunciationScore! > 0)
                  Expanded(
                    child: _buildMetricCard(
                      'Pronunciation',
                      '${_evaluationResult!.pronunciationScore!.toInt()}%',
                      Icons.record_voice_over,
                      Colors.green,
                    ),
                  ),
                if (_evaluationResult!.pronunciationScore != null &&
                    _evaluationResult!.pronunciationScore! > 0)
                  const SizedBox(width: 12),
                Expanded(
                  child: _buildMetricCard(
                    'Duration',
                    '${(_evaluationResult!.timing.durationMs / 1000).toStringAsFixed(1)}s',
                    Icons.timer,
                    Colors.purple,
                  ),
                ),
              ],
            ),
            
            const SizedBox(height: 20),
            
            // Reference text that was scored
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.withValues(alpha: 0.05),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.format_quote, size: 16, color: Colors.blue[600]),
                      const SizedBox(width: 8),
                      Text(
                        'Text that was scored:',
                        style: TextStyle(
                          color: Colors.blue[700],
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _getReferenceText(),
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[800],
                      height: 1.5,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            
            // Transcript (what we heard) - only if STT is available and has content
            if (_evaluationResult!.transcript.text.isNotEmpty &&
                _evaluationResult!.transcript.text != widget.exercise.prompt) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
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
                        Icon(Icons.record_voice_over, size: 16, color: Colors.grey[600]),
                        const SizedBox(width: 8),
                        Text(
                          'What you said (transcription):',
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
                      '"${_evaluationResult!.transcript.text}"',
                      style: const TextStyle(
                        fontSize: 14,
                        fontStyle: FontStyle.italic,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],
            
            // Pronunciation Issues - these are words from the reference that need improvement
            if (_evaluationResult!.pronunciation.issues.isNotEmpty) ...[
              Row(
                children: [
                  Icon(Icons.warning_amber, size: 18, color: Colors.orange[700]),
                  const SizedBox(width: 8),
                  Text(
                    'Words that need practice:',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'These words from the reference text had lower pronunciation scores:',
                style: TextStyle(
                  color: Colors.grey[600],
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _evaluationResult!.pronunciation.issues.take(5).map((issue) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.orange.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.orange.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          issue.word,
                          style: const TextStyle(
                            color: Colors.orange,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                        if (issue.suggestion != null) ...[
                          const SizedBox(width: 6),
                          Icon(Icons.arrow_forward, size: 14, color: Colors.orange[700]),
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
                }).toList(),
              ),
              const SizedBox(height: 16),
            ],
          ],
          
          // AI Analysis Text
          if (aiAnalysis != null) ...[
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
                  const Row(
                    children: [
                      Icon(
                        Icons.smart_toy,
                        color: Colors.blue,
                        size: 20,
                      ),
                      SizedBox(width: 8),
                      Text(
                        'Detailed Analysis:',
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
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.5,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          
          // Suggestions
          if (suggestions.isNotEmpty) ...[
            Text(
              'Tips for Improvement:',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),
            ...suggestions.map((suggestion) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    margin: const EdgeInsets.only(top: 8, right: 12),
                    decoration: BoxDecoration(
                      color: Colors.amber,
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
            )),
          ],
          
          const SizedBox(height: 20),
          
          // Playback and Action Buttons
          Row(
            children: [
              if (_recordedPath != null)
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _playRecording,
                    icon: Icon(_isPlaying ? Icons.stop : Icons.volume_up),
                    label: Text(_isPlaying ? 'Stop' : 'Listen Again'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.blue,
                      side: const BorderSide(color: Colors.blue),
                    ),
                  ),
                ),
              if (_recordedPath != null) const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton(
                  onPressed: _tryAgain,
                  child: const Text('Try Again'),
                ),
              ),
              const SizedBox(width: 8),
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
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              color: Colors.grey[600],
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  void _toggleRecording() async {
    if (isRecording) {
      // Stop recording
      debugPrint('🎤 Stopping recording...');
      _pulseController.stop();
      _waveController.stop();
      final path = await _recorder.stop();
      debugPrint('🎤 Recording stopped. Path: $path');
      setState(() {
        isRecording = false;
        hasRecorded = path != null;
        _recordedPath = path;
      });
      
      _addTrainerMessage(
        'Great! I received your recording. Now let me analyze your pronunciation and give you feedback.',
        AITrainerMessageType.encouragement,
      );
      
      // Automatically analyze the recording after stopping
      if (path != null) {
        _analyzeRecording();
      }
    } else {
      // Start recording
      debugPrint('🎤 Starting recording...');
      try {
        await _recorder.start();
        debugPrint('🎤 Recording started successfully');
        setState(() {
          isRecording = true;
          hasRecorded = false;
          recordingDuration = 0;
          _remainingSeconds = widget.exercise.maxRecordingSeconds;
          aiAnalysis = null;
          pronunciationScore = 0;
          suggestions.clear();
        });
        
        _pulseController.repeat(reverse: true);
        _waveController.repeat();
        
        // Start the recording timer with countdown
        _startRecordingTimer();
        
        _addTrainerMessage(
          'Perfect! I\'m listening now. You have ${widget.exercise.maxRecordingSeconds} seconds. Speak clearly and take your time.',
          AITrainerMessageType.instruction,
        );
      } catch (e) {
        debugPrint('🎤 ERROR starting recording: $e');
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not start recording: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _startRecordingTimer() async {
    // Initialize remaining seconds for countdown
    _remainingSeconds = widget.exercise.maxRecordingSeconds;
    
    while (isRecording && _remainingSeconds > 0) {
      await Future.delayed(const Duration(seconds: 1));
      if (mounted && isRecording) {
        setState(() {
          recordingDuration++;
          _remainingSeconds = widget.exercise.maxRecordingSeconds - recordingDuration;
        });
      }
    }
    
    // Auto-stop when max duration reached
    if (mounted && isRecording && _remainingSeconds <= 0) {
      _addTrainerMessage(
        'Time\'s up! Your recording has been saved.',
        AITrainerMessageType.instruction,
      );
      _toggleRecording();
    }
  }

  Future<void> _playRecording() async {
    if (_recordedPath == null) return;

    HapticFeedback.selectionClick();

    try {
      if (_isPlaying) {
        await _audioPlayer.stop();
        setState(() => _isPlaying = false);
        return;
      }

      setState(() => _isPlaying = true);

      // Handle both blob URLs (web) and file paths (native)
      if (kIsWeb) {
        // On web, _recordedPath is a blob URL
        await _audioPlayer.setUrl(_recordedPath!);
      } else {
        // On native platforms, _recordedPath is a file path
        await _audioPlayer.setFilePath(_recordedPath!);
      }
      
      _audioPlayer.playerStateStream.listen((state) {
        if (state.processingState == ProcessingState.completed) {
          if (mounted) setState(() => _isPlaying = false);
        }
      });
      await _audioPlayer.play();
    } catch (e) {
      if (mounted) {
        setState(() => _isPlaying = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error playing recording: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _analyzeRecording() async {
    if (_recordedPath == null) return;
    setState(() {
      isAnalyzing = true;
    });

    try {
      final api = SpeakingApi(SecureStorage());
      final SpeechEvaluateResponseModel res;
      
      // Use the correct reference text for pronunciation scoring
      final referenceText = _getReferenceText();

      if (kIsWeb) {
        // On web, _recordedPath is a blob URL
        res = await api.evaluate(
          referenceText: referenceText,
          language: 'en-US',
          audioFile: null,
          audioBlobUrl: _recordedPath,
        );
      } else {
        // On native platforms, _recordedPath is a file path
        res = await api.evaluate(
          referenceText: referenceText,
          language: 'en-US',
          audioFile: io.File(_recordedPath!),
        );
      }

      setState(() {
        isAnalyzing = false;
        pronunciationScore = res.overallScore.round();
        _evaluationResult = res;
        aiAnalysis = _buildAnalysisSummary(res);
        suggestions = res.tips;
      });

      _addTrainerMessage(
        _buildTrainerFeedback(res),
        AITrainerMessageType.feedback,
      );
    } catch (e) {
      setState(() {
        isAnalyzing = false;
      });
      _addTrainerMessage('Analysis failed: $e', AITrainerMessageType.correction);
    }
  }

  void _tryAgain() {
    setState(() {
      hasRecorded = false;
      aiAnalysis = null;
      pronunciationScore = 0;
      suggestions.clear();
      recordingDuration = 0;
    });
    
    _addTrainerMessage(
      'Let\'s try again! Take a deep breath and speak clearly. You\'ve got this!',
      AITrainerMessageType.encouragement,
    );
  }

  Future<void> _completeExercise() async {
    if (_isCompleting) return;
    setState(() => _isCompleting = true);

    final exerciseId = int.tryParse(widget.exercise.id) ?? 0;
    final accuracy = (pronunciationScore / 100).clamp(0.0, 1.0);
    var pointsEarned = widget.exercise.points;

    try {
      if (exerciseId > 0) {
        final transcriptText = _evaluationResult?.transcript.text ?? '';
        final timeTakenSeconds =
            DateTime.now().difference(_exerciseStartTime).inSeconds;

        final result = await _practiceRepository.submitExercise(
          exerciseId: exerciseId,
          userAnswer: {
            'text': transcriptText.isNotEmpty ? transcriptText : widget.exercise.prompt,
            'reference_text': widget.exercise.prompt,
            'pronunciation_score': pronunciationScore,
            if (suggestions.isNotEmpty) 'suggestions': suggestions,
          },
          timeTakenSeconds: timeTakenSeconds > 0 ? timeTakenSeconds : null,
        );
        if (result.pointsEarned > 0) {
          pointsEarned = result.pointsEarned;
        }
      } else {
        final minutes = (DateTime.now().difference(_exerciseStartTime).inSeconds / 60)
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
      debugPrint('Failed to persist speaking result: $e');
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
            Text('Your pronunciation score: $pronunciationScore%'),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                children: [
                  Text(
                    '+$pointsEarned',
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: Colors.red,
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
                'score': pronunciationScore,
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

  IconData _getSpeakingTypeIcon(SpeakingExerciseType type) {
    switch (type) {
      case SpeakingExerciseType.pronunciation:
        return Icons.record_voice_over;
      case SpeakingExerciseType.conversation:
        return Icons.chat;
      case SpeakingExerciseType.description:
        return Icons.description;
      case SpeakingExerciseType.storytelling:
        return Icons.auto_stories;
      case SpeakingExerciseType.presentation:
        return Icons.present_to_all;
    }
  }

  String _buildAnalysisSummary(SpeechEvaluateResponseModel res) {
    final pronunciationScore = res.pronunciationScore?.toInt() ?? res.overallScore.toInt();
    final duration = (res.timing.durationMs / 1000).toStringAsFixed(1);
    
    final buffer = StringBuffer();
    buffer.writeln('📊 Pronunciation Analysis:');
    buffer.writeln('• Pronunciation Score: $pronunciationScore%');
    if (res.timing.durationMs > 0) {
      buffer.writeln('• Recording Duration: ${duration}s');
    }
    
    // Show word-level feedback if available (these are words from the reference text)
    if (res.detailedWordFeedback != null && res.detailedWordFeedback!.isNotEmpty) {
      final wordsNeedingWork = res.wordsNeedingImprovement.take(5).toList();
      if (wordsNeedingWork.isNotEmpty) {
        buffer.writeln('\n📝 Words to improve (from reference):');
        for (final word in wordsNeedingWork) {
          buffer.writeln('• "${word.word}" - ${word.score.toInt()}% accuracy');
          // Show phoneme issues if available
          for (final phoneme in word.problemPhonemes.take(2)) {
            if (phoneme.issue != null) {
              buffer.writeln('  → ${phoneme.issue}');
            }
          }
        }
      } else {
        buffer.writeln('\n✅ All words pronounced well!');
      }
    } else if (res.pronunciation.issues.isNotEmpty) {
      buffer.writeln('\n⚠️ Words to improve:');
      for (final issue in res.pronunciation.issues.take(3)) {
        if (issue.suggestion != null) {
          buffer.writeln('• ${issue.word}: ${issue.suggestion}');
        } else {
          buffer.writeln('• ${issue.word}: ${issue.issue}');
        }
      }
    }
    
    buffer.writeln('\n💡 Note: Scores show how well each word in the reference text was pronounced.');
    
    return buffer.toString();
  }

  String _buildTrainerFeedback(SpeechEvaluateResponseModel res) {
    final score = res.overallScore.round();
    
    if (score >= 90) {
      return 'Outstanding! 🌟 Your pronunciation is excellent ($score%). Keep up the amazing work!';
    } else if (score >= 80) {
      return 'Great job! 👏 You scored $score%. Your pronunciation is very clear with minor areas to improve.';
    } else if (score >= 70) {
      return 'Good effort! 💪 You scored $score%. Focus on the highlighted words and you\'ll improve quickly.';
    } else if (score >= 60) {
      return 'Nice try! 📈 You scored $score%. Practice the problem areas and try again.';
    } else {
      return 'Keep practicing! 🎯 You scored $score%. Don\'t give up - every attempt makes you better!';
    }
  }
}
