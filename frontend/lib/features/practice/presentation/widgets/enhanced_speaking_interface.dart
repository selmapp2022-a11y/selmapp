import 'package:flutter/material.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/audio_waveform_widget.dart';
import '../../../../core/widgets/rive_coach_widget.dart';
import '../../../../core/widgets/speech_bubble_widget.dart';

/// Enhanced speaking interface with AI coach presence
/// Provides a personal trainer feel during speaking exercises
class EnhancedSpeakingInterface extends StatefulWidget {
  final bool isRecording;
  final bool isAnalyzing;
  final bool hasResult;
  final int recordingDuration;
  final int maxDuration;
  final String? statusMessage;
  final String? coachMessage;
  final int? score;
  final List<String>? suggestions;
  final VoidCallback onStartRecording;
  final VoidCallback onStopRecording;
  final VoidCallback? onPlayRecording;
  final VoidCallback? onRetry;

  const EnhancedSpeakingInterface({
    super.key,
    required this.isRecording,
    required this.isAnalyzing,
    required this.hasResult,
    required this.recordingDuration,
    required this.maxDuration,
    this.statusMessage,
    this.coachMessage,
    this.score,
    this.suggestions,
    required this.onStartRecording,
    required this.onStopRecording,
    this.onPlayRecording,
    this.onRetry,
  });

  @override
  State<EnhancedSpeakingInterface> createState() =>
      _EnhancedSpeakingInterfaceState();
}

class _EnhancedSpeakingInterfaceState extends State<EnhancedSpeakingInterface>
    with TickerProviderStateMixin {
  late AnimationController _breathingController;
  late AnimationController _successController;

  @override
  void initState() {
    super.initState();

    _breathingController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);

    _successController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
  }

  @override
  void didUpdateWidget(EnhancedSpeakingInterface oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.hasResult && !oldWidget.hasResult && widget.score != null) {
      if (widget.score! >= 70) {
        _successController.forward(from: 0);
      }
    }
  }

  @override
  void dispose() {
    _breathingController.dispose();
    _successController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.white.withValues(alpha: 0.1),
            Colors.white.withValues(alpha: 0.05),
          ],
        ),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.2),
          width: 1.5,
        ),
      ),
      child: Column(
        children: [
          // AI Coach presence
          _buildCoachPresence(),

          const SizedBox(height: 24),

          // Recording interface
          _buildRecordingOrb(),

          const SizedBox(height: 20),

          // Status and feedback
          _buildStatusArea(),

          // Suggestions if available
          if (widget.hasResult && widget.suggestions != null)
            _buildSuggestions(),
        ],
      ),
    );
  }

  Widget _buildCoachPresence() {
    final coachState = _getCoachState();
    final message = widget.coachMessage ?? _getDefaultMessage();

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Coach avatar
        RiveCoachAvatar(
          state: coachState,
          size: 56,
        ),

        const SizedBox(width: 12),

        // Coach message bubble
        Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4),
                topRight: Radius.circular(16),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.1),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      AppConstants.coachDisplayName,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: _getCoachColor(),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      width: 6,
                      height: 6,
                      decoration: const BoxDecoration(
                        color: Colors.green,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  message,
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.4,
                    color: Colors.black87,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRecordingOrb() {
    return AnimatedBuilder(
      animation: _breathingController,
      builder: (context, child) {
        final breathValue = Tween<double>(begin: 1.0, end: 1.08)
            .animate(_breathingController)
            .value;

        return GestureDetector(
          onTap: () {
            if (widget.isRecording) {
              widget.onStopRecording();
            } else if (!widget.isAnalyzing && !widget.hasResult) {
              widget.onStartRecording();
            }
          },
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Pulsing rings when recording
              if (widget.isRecording) ...[
                _buildPulsingRing(0),
                _buildPulsingRing(0.33),
                _buildPulsingRing(0.66),
              ],

              // Main orb
              Transform.scale(
                scale: widget.isRecording ? breathValue : 1.0,
                child: Container(
                  width: 100,
                  height: 100,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        _getOrbColor().withValues(alpha: 0.9),
                        _getOrbColor().withValues(alpha: 0.7),
                      ],
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: _getOrbColor().withValues(alpha: 0.5),
                        blurRadius: widget.isRecording ? 30 : 15,
                        spreadRadius: widget.isRecording ? 5 : 2,
                      ),
                    ],
                  ),
                  child: Center(
                    child: widget.isAnalyzing
                        ? const SizedBox(
                            width: 32,
                            height: 32,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 3,
                            ),
                          )
                        : Icon(
                            _getOrbIcon(),
                            size: 40,
                            color: Colors.white,
                          ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildPulsingRing(double delay) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 1500),
      builder: (context, value, child) {
        final adjustedValue = ((value + delay) % 1.0);
        final scale = 1.0 + (adjustedValue * 0.5);
        final opacity = (1.0 - adjustedValue) * 0.3;

        return Transform.scale(
          scale: scale,
          child: Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: Colors.red.withValues(alpha: opacity),
                width: 2,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildStatusArea() {
    return Column(
      children: [
        // Audio waveform when recording
        if (widget.isRecording)
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: AudioWaveformWidget(
              isActive: true,
              style: WaveformStyle.bars,
              height: 40,
              barCount: 7,
              color: Colors.red,
            ),
          ),

        // Progress bar when recording
        if (widget.isRecording) ...[
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${widget.recordingDuration}s',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.8),
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Text(
                '${widget.maxDuration}s max',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.6),
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: widget.recordingDuration / widget.maxDuration,
              backgroundColor: Colors.white.withValues(alpha: 0.2),
              valueColor: AlwaysStoppedAnimation<Color>(
                widget.recordingDuration / widget.maxDuration > 0.8
                    ? Colors.orange
                    : Colors.red,
              ),
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 12),
        ],

        // Status text
        Text(
          widget.statusMessage ?? _getStatusText(),
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: _getStatusColor(),
          ),
          textAlign: TextAlign.center,
        ),

        // Score display
        if (widget.hasResult && widget.score != null) ...[
          const SizedBox(height: 20),
          _buildScoreDisplay(),
        ],

        // Action buttons
        if (widget.hasResult) ...[
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (widget.onPlayRecording != null)
                _buildActionButton(
                  icon: Icons.play_arrow,
                  label: 'Play',
                  onTap: widget.onPlayRecording!,
                  color: Colors.blue,
                ),
              const SizedBox(width: 12),
              if (widget.onRetry != null)
                _buildActionButton(
                  icon: Icons.refresh,
                  label: 'Retry',
                  onTap: widget.onRetry!,
                  color: Colors.orange,
                ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildScoreDisplay() {
    final score = widget.score ?? 0;
    final color = score >= 80
        ? Colors.green
        : score >= 60
            ? Colors.orange
            : Colors.red;

    return AnimatedBuilder(
      animation: _successController,
      builder: (context, child) {
        final scale = score >= 70
            ? 1.0 +
                (Tween<double>(begin: 0.0, end: 0.1)
                    .animate(CurvedAnimation(
                      parent: _successController,
                      curve: Curves.elasticOut,
                    ))
                    .value)
            : 1.0;

        return Transform.scale(
          scale: scale,
          child: Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.15),
              border: Border.all(color: color, width: 4),
              boxShadow: [
                BoxShadow(
                  color: color.withValues(alpha: 0.3),
                  blurRadius: 20,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  '$score',
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
                Text(
                  'Score',
                  style: TextStyle(
                    fontSize: 12,
                    color: color.withValues(alpha: 0.8),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildSuggestions() {
    return Container(
      margin: const EdgeInsets.only(top: 20),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.blue.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Colors.blue.withValues(alpha: 0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.lightbulb_outline, color: Colors.blue, size: 18),
              const SizedBox(width: 8),
              Text(
                'Tips to improve:',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.blue[700],
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...widget.suggestions!.take(3).map((tip) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 4,
                      height: 4,
                      margin: const EdgeInsets.only(top: 7, right: 8),
                      decoration: BoxDecoration(
                        color: Colors.blue[400],
                        shape: BoxShape.circle,
                      ),
                    ),
                    Expanded(
                      child: Text(
                        tip,
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey[800],
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

  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    required Color color,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  CoachState _getCoachState() {
    if (widget.isRecording) return CoachState.listening;
    if (widget.isAnalyzing) return CoachState.thinking;
    if (widget.hasResult) {
      if (widget.score != null && widget.score! >= 80) {
        return CoachState.celebrating;
      } else if (widget.score != null && widget.score! >= 60) {
        return CoachState.happy;
      } else {
        return CoachState.encouraging;
      }
    }
    return CoachState.speaking;
  }

  Color _getCoachColor() {
    final state = _getCoachState();
    switch (state) {
      case CoachState.listening:
        return Colors.red;
      case CoachState.thinking:
        return Colors.purple;
      case CoachState.celebrating:
      case CoachState.happy:
        return Colors.green;
      case CoachState.encouraging:
        return Colors.orange;
      default:
        return AppTheme.primaryColor;
    }
  }

  Color _getOrbColor() {
    if (widget.isRecording) return Colors.red;
    if (widget.isAnalyzing) return Colors.purple;
    if (widget.hasResult) {
      if (widget.score != null && widget.score! >= 70) {
        return Colors.green;
      }
      return Colors.orange;
    }
    return AppTheme.primaryColor;
  }

  IconData _getOrbIcon() {
    if (widget.isRecording) return Icons.stop;
    if (widget.hasResult) return Icons.check;
    return Icons.mic;
  }

  String _getDefaultMessage() {
    if (widget.isRecording) {
      return "I'm listening! Take your time and speak clearly. You're doing great! 👂";
    }
    if (widget.isAnalyzing) {
      return "Analyzing your speech... Let me give you personalized feedback! 🤔";
    }
    if (widget.hasResult) {
      if (widget.score != null && widget.score! >= 80) {
        return "Outstanding! Your pronunciation is excellent! Keep it up! 🌟";
      } else if (widget.score != null && widget.score! >= 60) {
        return "Good effort! A few areas to practice, but you're improving! 💪";
      } else {
        return "Don't worry! Every practice makes you better. Try again? 🎯";
      }
    }
    return "Ready when you are! Tap the mic and show me what you've got! 🎤";
  }

  String _getStatusText() {
    if (widget.isRecording) {
      final remaining = widget.maxDuration - widget.recordingDuration;
      return remaining <= 5
          ? '$remaining seconds remaining...'
          : 'Recording... Tap to stop';
    }
    if (widget.isAnalyzing) return 'Analyzing your speech...';
    if (widget.hasResult) return 'Analysis complete!';
    return 'Tap to start speaking';
  }

  Color _getStatusColor() {
    if (widget.isRecording) {
      final remaining = widget.maxDuration - widget.recordingDuration;
      return remaining <= 5 ? Colors.orange : Colors.red;
    }
    if (widget.isAnalyzing) return Colors.purple;
    if (widget.hasResult) {
      if (widget.score != null && widget.score! >= 70) {
        return Colors.green;
      }
      return Colors.orange;
    }
    return Colors.white;
  }
}

/// Conversation mode speaking interface
class ConversationalSpeakingInterface extends StatelessWidget {
  final List<ConversationTurn> conversation;
  final bool isListening;
  final bool isProcessing;
  final String? currentPrompt;
  final VoidCallback onStartSpeaking;
  final VoidCallback onStopSpeaking;
  final ScrollController? scrollController;

  const ConversationalSpeakingInterface({
    super.key,
    required this.conversation,
    required this.isListening,
    required this.isProcessing,
    this.currentPrompt,
    required this.onStartSpeaking,
    required this.onStopSpeaking,
    this.scrollController,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Conversation transcript
        Expanded(
          child: ListView.builder(
            controller: scrollController,
            padding: const EdgeInsets.all(16),
            itemCount: conversation.length,
            itemBuilder: (context, index) {
              final turn = conversation[index];
              return _buildConversationTurn(context, turn, index);
            },
          ),
        ),

        // Input area
        Container(
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
            child: Column(
              children: [
                if (currentPrompt != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(
                      currentPrompt!,
                      style: TextStyle(
                        color: Colors.grey[600],
                        fontSize: 14,
                        fontStyle: FontStyle.italic,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),

                // Listening orb
                ListeningOrb(
                  isListening: isListening,
                  isProcessing: isProcessing,
                  statusText: isProcessing
                      ? 'Processing...'
                      : isListening
                          ? 'Listening...'
                          : 'Tap to speak',
                  onTap: isListening ? onStopSpeaking : onStartSpeaking,
                  size: 80,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildConversationTurn(
    BuildContext context,
    ConversationTurn turn,
    int index,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Speaker's message
          SpeechBubble(
            text: turn.text,
            direction:
                turn.isUser ? BubbleDirection.right : BubbleDirection.left,
            feedbackType: turn.feedbackType,
            senderName: turn.isUser ? null : AppConstants.coachDisplayName,
            animationDelay: Duration(milliseconds: index * 100),
            avatar: turn.isUser
                ? null
                : RiveCoachAvatar(
                    state: _getCoachStateForFeedback(turn.feedbackType),
                    size: 32,
                  ),
          ),

          // Correction if present
          if (turn.correction != null) ...[
            const SizedBox(height: 8),
            Padding(
              padding: EdgeInsets.only(
                left: turn.isUser ? 48 : 40,
                right: turn.isUser ? 0 : 48,
              ),
              child: CorrectionBubble(
                originalText: turn.text,
                correctedText: turn.correction!,
                corrections: turn.corrections ?? [],
              ),
            ),
          ],
        ],
      ),
    );
  }

  CoachState _getCoachStateForFeedback(FeedbackType type) {
    switch (type) {
      case FeedbackType.correct:
        return CoachState.happy;
      case FeedbackType.incorrect:
        return CoachState.encouraging;
      case FeedbackType.suggestion:
        return CoachState.speaking;
      default:
        return CoachState.idle;
    }
  }
}

/// Model for conversation turns
class ConversationTurn {
  final String text;
  final bool isUser;
  final FeedbackType feedbackType;
  final String? correction;
  final List<CorrectionItem>? corrections;
  final DateTime timestamp;

  ConversationTurn({
    required this.text,
    required this.isUser,
    this.feedbackType = FeedbackType.neutral,
    this.correction,
    this.corrections,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}





