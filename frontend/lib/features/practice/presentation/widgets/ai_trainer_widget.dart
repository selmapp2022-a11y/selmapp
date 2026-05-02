import 'package:flutter/material.dart';
import '../../data/models/exercise_models.dart';
import '../../../../core/theme/app_theme.dart';

class AITrainerWidget extends StatefulWidget {
  final AITrainerMessage currentMessage;
  final VoidCallback? onMessageTap;

  const AITrainerWidget({
    super.key,
    required this.currentMessage,
    this.onMessageTap,
  });

  @override
  State<AITrainerWidget> createState() => _AITrainerWidgetState();
}

class _AITrainerWidgetState extends State<AITrainerWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _scaleAnimation = Tween<double>(begin: 0.95, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOutBack),
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOut),
    );

    _animationController.forward();
  }

  @override
  void didUpdateWidget(AITrainerWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.currentMessage.id != widget.currentMessage.id) {
      _animationController.reset();
      _animationController.forward();
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animationController,
      builder: (context, child) {
        return Transform.scale(
          scale: _scaleAnimation.value,
          child: Opacity(
            opacity: _fadeAnimation.value,
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: _getGradientColors(widget.currentMessage.type),
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: _getGradientColors(widget.currentMessage.type)[0].withValues(alpha: 0.3),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  onTap: widget.onMessageTap,
                  borderRadius: BorderRadius.circular(20),
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Row(
                      children: [
                        // AI Trainer Avatar
                        Container(
                          width: 60,
                          height: 60,
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: Colors.white.withValues(alpha: 0.3),
                              width: 2,
                            ),
                          ),
                          child: Center(
                            child: _buildTrainerIcon(widget.currentMessage.type),
                          ),
                        ),
                        const SizedBox(width: 14),

                        // Message Content
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  const Text(
                                    'AI Trainer',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 15,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: Colors.green,
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: const Text(
                                      'Online',
                                      style: TextStyle(
                                        color: Colors.white,
                                        fontSize: 10,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                  const Spacer(),
                                  _buildMessageTypeChip(widget.currentMessage.type),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                widget.currentMessage.message,
                                style: TextStyle(
                                  color: Colors.white.withValues(alpha: 0.95),
                                  fontSize: 13,
                                  height: 1.4,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 10),
                              Row(
                                children: [
                                  Icon(
                                    Icons.chat_bubble_outline,
                                    color: Colors.white.withValues(alpha: 0.7),
                                    size: 14,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    'Tap to chat',
                                    style: TextStyle(
                                      color: Colors.white.withValues(alpha: 0.7),
                                      fontSize: 12,
                                    ),
                                  ),
                                  const Spacer(),
                                  Icon(
                                    Icons.arrow_forward_ios,
                                    color: Colors.white.withValues(alpha: 0.5),
                                    size: 12,
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
            ),
          ),
        );
      },
    );
  }

  Widget _buildTrainerIcon(AITrainerMessageType type) {
    final iconData = _getMessageIcon(type);
    return Icon(iconData, color: Colors.white, size: 26);
  }

  IconData _getMessageIcon(AITrainerMessageType type) {
    switch (type) {
      case AITrainerMessageType.welcome:
        return Icons.waving_hand;
      case AITrainerMessageType.encouragement:
        return Icons.thumb_up;
      case AITrainerMessageType.correction:
        return Icons.lightbulb_outline;
      case AITrainerMessageType.feedback:
        return Icons.analytics;
      case AITrainerMessageType.celebration:
        return Icons.celebration;
      case AITrainerMessageType.instruction:
        return Icons.school;
      case AITrainerMessageType.question:
        return Icons.help_outline;
    }
  }

  Widget _buildMessageTypeChip(AITrainerMessageType type) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        _getMessageTypeLabel(type),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  List<Color> _getGradientColors(AITrainerMessageType type) {
    switch (type) {
      case AITrainerMessageType.welcome:
        return [AppTheme.primaryColor, const Color(0xFF21CBF3)];
      case AITrainerMessageType.encouragement:
        return [const Color(0xFF4CAF50), const Color(0xFF8BC34A)];
      case AITrainerMessageType.correction:
        return [const Color(0xFFFF9800), const Color(0xFFFFC107)];
      case AITrainerMessageType.feedback:
        return [const Color(0xFF9C27B0), const Color(0xFFE91E63)];
      case AITrainerMessageType.celebration:
        return [const Color(0xFFE91E63), const Color(0xFFFF5722)];
      case AITrainerMessageType.instruction:
        return [const Color(0xFF607D8B), const Color(0xFF90A4AE)];
      case AITrainerMessageType.question:
        return [const Color(0xFF795548), const Color(0xFFBCAAA4)];
    }
  }

  String _getMessageTypeLabel(AITrainerMessageType type) {
    switch (type) {
      case AITrainerMessageType.welcome:
        return 'Welcome';
      case AITrainerMessageType.encouragement:
        return 'Encourage';
      case AITrainerMessageType.correction:
        return 'Tip';
      case AITrainerMessageType.feedback:
        return 'Feedback';
      case AITrainerMessageType.celebration:
        return 'Celebrate';
      case AITrainerMessageType.instruction:
        return 'Instruction';
      case AITrainerMessageType.question:
        return 'Question';
    }
  }
}
