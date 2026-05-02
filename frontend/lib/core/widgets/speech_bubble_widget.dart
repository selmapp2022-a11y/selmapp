import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Direction of the speech bubble tail
enum BubbleDirection {
  left,
  right,
}

/// Type of feedback in the bubble
enum FeedbackType {
  neutral,
  correct,
  incorrect,
  suggestion,
}

/// Animated speech bubble for conversational UI
class SpeechBubble extends StatefulWidget {
  final String text;
  final BubbleDirection direction;
  final bool animate;
  final FeedbackType feedbackType;
  final VoidCallback? onTap;
  final Widget? avatar;
  final String? senderName;
  final Duration? animationDelay;

  const SpeechBubble({
    super.key,
    required this.text,
    this.direction = BubbleDirection.left,
    this.animate = true,
    this.feedbackType = FeedbackType.neutral,
    this.onTap,
    this.avatar,
    this.senderName,
    this.animationDelay,
  });

  @override
  State<SpeechBubble> createState() => _SpeechBubbleState();
}

class _SpeechBubbleState extends State<SpeechBubble>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );

    _scaleAnimation = Tween<double>(begin: 0.8, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.elasticOut),
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );

    _slideAnimation = Tween<Offset>(
      begin: Offset(widget.direction == BubbleDirection.left ? -0.2 : 0.2, 0),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOut));

    if (widget.animate) {
      Future.delayed(widget.animationDelay ?? Duration.zero, () {
        if (mounted) _controller.forward();
      });
    } else {
      _controller.value = 1.0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isUser = widget.direction == BubbleDirection.right;

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return FadeTransition(
          opacity: _fadeAnimation,
          child: SlideTransition(
            position: _slideAnimation,
            child: Transform.scale(
              scale: _scaleAnimation.value,
              alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
              child: _buildBubbleRow(isUser),
            ),
          ),
        );
      },
    );
  }

  Widget _buildBubbleRow(bool isUser) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isUser && widget.avatar != null) ...[
            widget.avatar!,
            const SizedBox(width: 8),
          ],
          Flexible(child: _buildBubble(isUser)),
          if (isUser && widget.avatar != null) ...[
            const SizedBox(width: 8),
            widget.avatar!,
          ],
        ],
      ),
    );
  }

  Widget _buildBubble(bool isUser) {
    return GestureDetector(
      onTap: widget.onTap,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: _getBubbleColor(isUser),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(isUser ? 18 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 18),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.08),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (widget.senderName != null && !isUser) ...[
              Text(
                widget.senderName!,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: _getTextColor(isUser).withValues(alpha: 0.7),
                ),
              ),
              const SizedBox(height: 4),
            ],
            Text(
              widget.text,
              style: TextStyle(
                fontSize: 15,
                height: 1.4,
                color: _getTextColor(isUser),
              ),
            ),
            if (widget.feedbackType != FeedbackType.neutral) ...[
              const SizedBox(height: 8),
              _buildFeedbackIndicator(),
            ],
          ],
        ),
      ),
    );
  }

  Color _getBubbleColor(bool isUser) {
    if (isUser) {
      return AppTheme.primaryColor;
    }

    switch (widget.feedbackType) {
      case FeedbackType.correct:
        return Colors.green.withValues(alpha: 0.1);
      case FeedbackType.incorrect:
        return Colors.orange.withValues(alpha: 0.1);
      case FeedbackType.suggestion:
        return Colors.blue.withValues(alpha: 0.1);
      case FeedbackType.neutral:
        return Colors.white;
    }
  }

  Color _getTextColor(bool isUser) {
    return isUser ? Colors.white : Colors.black87;
  }

  Widget _buildFeedbackIndicator() {
    IconData icon;
    Color color;
    String label;

    switch (widget.feedbackType) {
      case FeedbackType.correct:
        icon = Icons.check_circle;
        color = Colors.green;
        label = 'Great!';
        break;
      case FeedbackType.incorrect:
        icon = Icons.lightbulb_outline;
        color = Colors.orange;
        label = 'Let\'s improve';
        break;
      case FeedbackType.suggestion:
        icon = Icons.tips_and_updates;
        color = Colors.blue;
        label = 'Tip';
        break;
      default:
        return const SizedBox.shrink();
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: color,
          ),
        ),
      ],
    );
  }
}

/// Correction bubble that highlights mistakes and shows corrections
class CorrectionBubble extends StatefulWidget {
  final String originalText;
  final String correctedText;
  final List<CorrectionItem> corrections;
  final bool animate;
  final VoidCallback? onPlayCorrection;

  const CorrectionBubble({
    super.key,
    required this.originalText,
    required this.correctedText,
    this.corrections = const [],
    this.animate = true,
    this.onPlayCorrection,
  });

  @override
  State<CorrectionBubble> createState() => _CorrectionBubbleState();
}

class CorrectionItem {
  final String wrong;
  final String correct;
  final String? explanation;
  final int startIndex;
  final int endIndex;

  CorrectionItem({
    required this.wrong,
    required this.correct,
    this.explanation,
    required this.startIndex,
    required this.endIndex,
  });
}

class _CorrectionBubbleState extends State<CorrectionBubble>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;
  bool _showCorrected = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );

    if (widget.animate) {
      _controller.forward();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeAnimation,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: Colors.orange.withValues(alpha: 0.3),
            width: 2,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.orange.withValues(alpha: 0.1),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.orange.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.auto_fix_high,
                    color: Colors.orange,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Gentle Correction',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                          color: Colors.orange,
                        ),
                      ),
                      Text(
                        'Let me help you improve this',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
                if (widget.onPlayCorrection != null)
                  IconButton(
                    onPressed: widget.onPlayCorrection,
                    icon: const Icon(Icons.volume_up, color: Colors.orange),
                    iconSize: 20,
                  ),
              ],
            ),

            const SizedBox(height: 16),

            // Toggle between original and corrected
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              child: _showCorrected
                  ? _buildCorrectedText()
                  : _buildOriginalText(),
            ),

            const SizedBox(height: 12),

            // Toggle button
            Center(
              child: TextButton.icon(
                onPressed: () {
                  setState(() {
                    _showCorrected = !_showCorrected;
                  });
                },
                icon: Icon(
                  _showCorrected ? Icons.undo : Icons.check,
                  size: 18,
                ),
                label: Text(
                  _showCorrected ? 'Show Original' : 'Show Correction',
                ),
                style: TextButton.styleFrom(
                  foregroundColor: Colors.orange,
                ),
              ),
            ),

            // Detailed corrections list
            if (widget.corrections.isNotEmpty) ...[
              const Divider(height: 24),
              const Text(
                'Details:',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 8),
              ...widget.corrections.map((correction) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.red.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            correction.wrong,
                            style: const TextStyle(
                              color: Colors.red,
                              decoration: TextDecoration.lineThrough,
                              fontSize: 13,
                            ),
                          ),
                        ),
                        const Padding(
                          padding: EdgeInsets.symmetric(horizontal: 8),
                          child: Icon(Icons.arrow_forward, size: 16),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.green.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            correction.correct,
                            style: const TextStyle(
                              color: Colors.green,
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildOriginalText() {
    return Container(
      key: const ValueKey('original'),
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.red.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.record_voice_over, size: 14, color: Colors.red),
              const SizedBox(width: 6),
              Text(
                'What you said:',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Colors.red[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            widget.originalText,
            style: const TextStyle(
              fontSize: 15,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCorrectedText() {
    return Container(
      key: const ValueKey('corrected'),
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.green.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.green.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.check_circle, size: 14, color: Colors.green),
              const SizedBox(width: 6),
              Text(
                'Correct way:',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Colors.green[700],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            widget.correctedText,
            style: const TextStyle(
              fontSize: 15,
              height: 1.4,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

/// Chat message list with automatic animations
class ConversationalChat extends StatelessWidget {
  final List<ChatMessage> messages;
  final ScrollController? scrollController;
  final Widget Function(ChatMessage message, int index)? messageBuilder;

  const ConversationalChat({
    super.key,
    required this.messages,
    this.scrollController,
    this.messageBuilder,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      controller: scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: messages.length,
      itemBuilder: (context, index) {
        final message = messages[index];
        
        if (messageBuilder != null) {
          return messageBuilder!(message, index);
        }

        return SpeechBubble(
          text: message.text,
          direction: message.isUser ? BubbleDirection.right : BubbleDirection.left,
          feedbackType: message.feedbackType,
          senderName: message.isUser ? null : message.senderName,
          animationDelay: Duration(milliseconds: index * 50),
          avatar: message.isUser
              ? null
              : CircleAvatar(
                  radius: 16,
                  backgroundColor: AppTheme.primaryColor,
                  child: const Icon(
                    Icons.smart_toy,
                    size: 16,
                    color: Colors.white,
                  ),
                ),
        );
      },
    );
  }
}

/// Chat message model
class ChatMessage {
  final String text;
  final bool isUser;
  final String? senderName;
  final FeedbackType feedbackType;
  final DateTime timestamp;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.senderName,
    this.feedbackType = FeedbackType.neutral,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}





