import 'dart:ui';
import 'package:flutter/material.dart';

import '../constants/app_constants.dart';
import '../theme/app_theme.dart';
import 'rive_coach_widget.dart';

/// Enhanced AI Coach Card with Rive animation support
/// Provides a personalized, living presence on the home screen
class EnhancedAICoachCard extends StatefulWidget {
  final String message;
  final CoachState state;
  final VoidCallback? onTap;
  final String? actionText;
  final VoidCallback? onAction;
  final bool compact;
  final bool showPulse;

  const EnhancedAICoachCard({
    super.key,
    required this.message,
    this.state = CoachState.idle,
    this.onTap,
    this.actionText,
    this.onAction,
    this.compact = false,
    this.showPulse = false,
  });

  @override
  State<EnhancedAICoachCard> createState() => _EnhancedAICoachCardState();
}

class _EnhancedAICoachCardState extends State<EnhancedAICoachCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _bounceAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    _bounceAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.elasticOut),
    );

    _controller.forward();
  }

  @override
  void didUpdateWidget(EnhancedAICoachCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.message != widget.message || oldWidget.state != widget.state) {
      _controller.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.compact) {
      return _buildCompactCard(context);
    }
    return _buildFullCard(context);
  }

  Widget _buildCompactCard(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Transform.scale(
          scale: 0.95 + (_bounceAnimation.value * 0.05),
          child: Opacity(
            opacity: _bounceAnimation.value.clamp(0.0, 1.0),
            child: GestureDetector(
              onTap: widget.onTap,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      gradient: _getStateGradient(),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: _getStateColor().withValues(alpha: 0.3),
                        width: 1.5,
                      ),
                    ),
                    child: Row(
                      children: [
                        // Coach Avatar
                        RiveCoachAvatar(
                          state: widget.state,
                          size: 44,
                        ),
                        const SizedBox(width: 12),

                        // Message
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    AppConstants.coachDisplayName,
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 12,
                                      color: Colors.white.withValues(alpha: 0.9),
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
                              const SizedBox(height: 4),
                              Text(
                                widget.message,
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Colors.white.withValues(alpha: 0.95),
                                  height: 1.3,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),

                        if (widget.onTap != null)
                          Icon(
                            Icons.arrow_forward_ios,
                            size: 14,
                            color: Colors.white.withValues(alpha: 0.5),
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

  Widget _buildFullCard(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Transform.translate(
          offset: Offset(0, 10 * (1 - _bounceAnimation.value)),
          child: Opacity(
            opacity: _bounceAnimation.value.clamp(0.0, 1.0),
            child: GestureDetector(
              onTap: widget.onTap,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: _getStateGradient(),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: _getStateColor().withValues(alpha: 0.4),
                        width: 2,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: _getStateColor().withValues(alpha: 0.3),
                          blurRadius: 20,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // Header
                          Row(
                            children: [
                              // Rive Coach Avatar
                              RiveCoachWidget(
                                state: widget.state,
                                size: 64,
                                showGlow: widget.showPulse,
                              ),
                              const SizedBox(width: 14),

                              // Title and subtitle
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        const Text(
                                          AppConstants.coachDisplayName,
                                          style: TextStyle(
                                            fontWeight: FontWeight.bold,
                                            fontSize: 16,
                                            color: Colors.white,
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        _buildStateBadge(),
                                      ],
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      _getStateSubtitle(),
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.white.withValues(alpha: 0.7),
                                      ),
                                    ),
                                  ],
                                ),
                              ),

                              if (widget.onTap != null)
                                Icon(
                                  Icons.arrow_forward_ios,
                                  size: 16,
                                  color: Colors.white.withValues(alpha: 0.5),
                                ),
                            ],
                          ),

                          const SizedBox(height: 16),

                          // Message bubble
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  _getStateEmoji(),
                                  style: const TextStyle(fontSize: 24),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    widget.message,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 14,
                                      height: 1.5,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),

                          // Action button if provided
                          if (widget.actionText != null && widget.onAction != null) ...[
                            const SizedBox(height: 16),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton(
                                onPressed: widget.onAction,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.white,
                                  foregroundColor: _getStateColor(),
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 14,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                ),
                                child: Text(
                                  widget.actionText!,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
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

  Widget _buildStateBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: _getStateBadgeColor(),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        _getStateLabel(),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  LinearGradient _getStateGradient() {
    switch (widget.state) {
      case CoachState.celebrating:
        return LinearGradient(
          colors: [
            Colors.amber.withValues(alpha: 0.4),
            Colors.orange.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachState.happy:
        return LinearGradient(
          colors: [
            Colors.green.withValues(alpha: 0.4),
            Colors.teal.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachState.encouraging:
        return LinearGradient(
          colors: [
            Colors.orange.withValues(alpha: 0.4),
            Colors.deepOrange.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachState.listening:
        return LinearGradient(
          colors: [
            Colors.red.withValues(alpha: 0.4),
            Colors.pink.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachState.thinking:
        return LinearGradient(
          colors: [
            Colors.purple.withValues(alpha: 0.4),
            Colors.indigo.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      default:
        return LinearGradient(
          colors: [
            AppTheme.primaryColor.withValues(alpha: 0.4),
            Colors.blue.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
    }
  }

  Color _getStateColor() {
    switch (widget.state) {
      case CoachState.celebrating:
        return Colors.amber;
      case CoachState.happy:
        return Colors.green;
      case CoachState.encouraging:
        return Colors.orange;
      case CoachState.listening:
        return Colors.red;
      case CoachState.thinking:
        return Colors.purple;
      default:
        return AppTheme.primaryColor;
    }
  }

  Color _getStateBadgeColor() {
    switch (widget.state) {
      case CoachState.celebrating:
        return Colors.amber.shade700;
      case CoachState.happy:
        return Colors.green;
      case CoachState.encouraging:
        return Colors.orange;
      case CoachState.listening:
        return Colors.red;
      case CoachState.thinking:
        return Colors.purple;
      default:
        return AppTheme.primaryColor;
    }
  }

  String _getStateLabel() {
    switch (widget.state) {
      case CoachState.celebrating:
        return 'Celebrating!';
      case CoachState.happy:
        return 'Great job!';
      case CoachState.encouraging:
        return 'Let\'s go!';
      case CoachState.listening:
        return 'Listening...';
      case CoachState.thinking:
        return 'Thinking...';
      case CoachState.speaking:
        return 'Coaching';
      case CoachState.waving:
        return 'Hello!';
      case CoachState.idle:
        return 'Here to help';
    }
  }

  String _getStateSubtitle() {
    switch (widget.state) {
      case CoachState.celebrating:
        return 'So proud of you!';
      case CoachState.happy:
        return 'Keep up the great work!';
      case CoachState.encouraging:
        return 'I believe in you!';
      case CoachState.listening:
        return 'I\'m all ears';
      case CoachState.thinking:
        return 'Processing...';
      case CoachState.speaking:
        return 'Personal guidance';
      default:
        return 'Your AI English Trainer';
    }
  }

  String _getStateEmoji() {
    switch (widget.state) {
      case CoachState.celebrating:
        return '🎉';
      case CoachState.happy:
        return '😊';
      case CoachState.encouraging:
        return '💪';
      case CoachState.listening:
        return '👂';
      case CoachState.thinking:
        return '🤔';
      case CoachState.speaking:
        return '🎯';
      case CoachState.waving:
        return '👋';
      case CoachState.idle:
        return '✨';
    }
  }
}

/// Floating Coach Button with enhanced animation
class EnhancedFloatingCoachButton extends StatefulWidget {
  final VoidCallback onPressed;
  final bool hasNotification;
  final CoachState state;

  const EnhancedFloatingCoachButton({
    super.key,
    required this.onPressed,
    this.hasNotification = false,
    this.state = CoachState.idle,
  });

  @override
  State<EnhancedFloatingCoachButton> createState() =>
      _EnhancedFloatingCoachButtonState();
}

class _EnhancedFloatingCoachButtonState
    extends State<EnhancedFloatingCoachButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    if (widget.hasNotification) {
      _controller.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(EnhancedFloatingCoachButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.hasNotification && !_controller.isAnimating) {
      _controller.repeat(reverse: true);
    } else if (!widget.hasNotification && _controller.isAnimating) {
      _controller.stop();
      _controller.value = 0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        final scale = widget.hasNotification
            ? 1.0 + (_controller.value * 0.1)
            : 1.0;

        return Transform.scale(
          scale: scale,
          child: GestureDetector(
            onTap: widget.onPressed,
            child: Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                gradient: AppTheme.primaryGradient,
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryColor.withValues(
                      alpha: widget.hasNotification ? 0.6 : 0.4,
                    ),
                    blurRadius: widget.hasNotification ? 20 : 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Coach avatar
                  RiveCoachAvatar(
                    state: widget.state,
                    size: 48,
                  ),

                  // Notification badge
                  if (widget.hasNotification)
                    Positioned(
                      top: 4,
                      right: 4,
                      child: Container(
                        width: 16,
                        height: 16,
                        decoration: BoxDecoration(
                          color: Colors.red,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.priority_high,
                            size: 10,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Quick coach tip widget for inline usage
class QuickCoachTip extends StatelessWidget {
  final String tip;
  final CoachState state;
  final VoidCallback? onDismiss;

  const QuickCoachTip({
    super.key,
    required this.tip,
    this.state = CoachState.speaking,
    this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppTheme.primaryColor.withValues(alpha: 0.2),
        ),
      ),
      child: Row(
        children: [
          RiveCoachAvatar(state: state, size: 36),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              tip,
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey[800],
                height: 1.3,
              ),
            ),
          ),
          if (onDismiss != null)
            IconButton(
              onPressed: onDismiss,
              icon: Icon(
                Icons.close,
                size: 18,
                color: Colors.grey[500],
              ),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
            ),
        ],
      ),
    );
  }
}





