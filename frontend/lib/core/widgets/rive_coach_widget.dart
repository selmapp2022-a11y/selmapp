import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../constants/app_constants.dart';
import '../theme/app_theme.dart';

/// Coach states that affect the Rive animation
enum CoachState {
  idle,          // Default breathing/blinking
  listening,     // Attentive, ears perked
  thinking,      // Processing user's response
  happy,         // User did well
  encouraging,   // User made a mistake, but supportive
  celebrating,   // Big achievement
  speaking,      // Coach is giving feedback
  waving,        // Greeting the user
}

/// Interactive AI Coach Character (built-in Flutter robot)
///
/// NOTE:
/// We intentionally do **not** depend on external `.riv` assets here.
/// This keeps the project self-contained and avoids asset/licensing issues.
class RiveCoachWidget extends StatefulWidget {
  final CoachState state;
  final bool showGlow;
  final double size;
  final VoidCallback? onTap;

  /// Kept for backward compatibility with earlier Rive-based versions.
  /// Currently unused (the avatar is drawn in Flutter).
  final String? riveAsset;

  const RiveCoachWidget({
    super.key,
    this.state = CoachState.idle,
    this.showGlow = true,
    this.size = 120,
    this.onTap,
    this.riveAsset,
  });

  @override
  State<RiveCoachWidget> createState() => _RiveCoachWidgetState();
}

class _RiveCoachWidgetState extends State<RiveCoachWidget>
    with TickerProviderStateMixin {
  late AnimationController _glowController;
  late AnimationController _bounceController;
  late AnimationController _idleController;
  late Animation<double> _glowAnimation;
  late Animation<double> _bounceAnimation;

  @override
  void initState() {
    super.initState();

    _glowController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _bounceController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );

    _idleController = AnimationController(
      duration: const Duration(milliseconds: 2400),
      vsync: this,
    )..repeat();

    _glowAnimation = Tween<double>(begin: 0.3, end: 0.8).animate(
      CurvedAnimation(parent: _glowController, curve: Curves.easeInOut),
    );

    _bounceAnimation = Tween<double>(begin: 1.0, end: 1.1).animate(
      CurvedAnimation(parent: _bounceController, curve: Curves.elasticOut),
    );

    if (widget.showGlow) {
      _glowController.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(RiveCoachWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state != widget.state) {
      _bounceController.forward(from: 0);
    }
    if (widget.showGlow && !_glowController.isAnimating) {
      _glowController.repeat(reverse: true);
    } else if (!widget.showGlow && _glowController.isAnimating) {
      _glowController.stop();
    }
  }

  @override
  void dispose() {
    _glowController.dispose();
    _bounceController.dispose();
    _idleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        _bounceController.forward(from: 0);
        widget.onTap?.call();
      },
      child: AnimatedBuilder(
        animation: Listenable.merge([
          _glowController,
          _bounceController,
          _idleController,
        ]),
        builder: (context, child) {
          final t = _idleController.value;
          final bob = math.sin(t * 2 * math.pi) * (widget.size * 0.015);
          final tilt = _getTiltRadians(t);

          return Transform.scale(
            scale: _bounceAnimation.value,
            child: Transform.translate(
              offset: Offset(0, bob),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Glow effect
                  if (widget.showGlow)
                    Container(
                      width: widget.size * 1.4,
                      height: widget.size * 1.4,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: _getStateColor().withValues(
                              alpha: _glowAnimation.value * 0.5,
                            ),
                            blurRadius: 30,
                            spreadRadius: 10,
                          ),
                        ],
                      ),
                    ),

                  // Main avatar container
                  Container(
                    width: widget.size,
                    height: widget.size,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          _getStateColor().withValues(alpha: 0.9),
                          _getStateColor().withValues(alpha: 0.6),
                        ],
                      ),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.4),
                        width: 3,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: _getStateColor().withValues(alpha: 0.4),
                          blurRadius: 20,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: ClipOval(
                      child: Transform.rotate(
                        angle: tilt,
                        child: CustomPaint(
                          painter: _RobotCoachPainter(
                            state: widget.state,
                            t: t,
                            accent: _getStateColor(),
                          ),
                        ),
                      ),
                    ),
                  ),

                  // State indicator badge
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: _buildStateIndicator(),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  double _getTiltRadians(double t) {
    switch (widget.state) {
      case CoachState.thinking:
        return math.sin(t * 2 * math.pi) * 0.06;
      case CoachState.encouraging:
        return -0.06;
      case CoachState.waving:
        return math.sin(t * 2 * math.pi) * 0.08;
      default:
        return 0.0;
    }
  }

  Widget _buildStateIndicator() {
    final indicatorColor = _getIndicatorColor();
    final indicatorIcon = _getIndicatorIcon();

    return Container(
      width: widget.size * 0.3,
      height: widget.size * 0.3,
      decoration: BoxDecoration(
        color: indicatorColor,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
        boxShadow: [
          BoxShadow(
            color: indicatorColor.withValues(alpha: 0.5),
            blurRadius: 8,
          ),
        ],
      ),
      child: Center(
        child: Icon(
          indicatorIcon,
          color: Colors.white,
          size: widget.size * 0.15,
        ),
      ),
    );
  }

  Color _getStateColor() {
    switch (widget.state) {
      case CoachState.happy:
      case CoachState.celebrating:
        return Colors.green;
      case CoachState.encouraging:
        return Colors.orange;
      case CoachState.listening:
        return Colors.blue;
      case CoachState.thinking:
        return Colors.purple;
      case CoachState.speaking:
        return AppTheme.primaryColor;
      case CoachState.waving:
        return Colors.amber;
      case CoachState.idle:
        return AppTheme.primaryColor;
    }
  }

  Color _getIndicatorColor() {
    switch (widget.state) {
      case CoachState.listening:
        return Colors.red;
      case CoachState.thinking:
        return Colors.amber;
      case CoachState.happy:
      case CoachState.celebrating:
        return Colors.green;
      default:
        return Colors.green;
    }
  }

  IconData _getIndicatorIcon() {
    switch (widget.state) {
      case CoachState.listening:
        return Icons.mic;
      case CoachState.thinking:
        return Icons.psychology;
      case CoachState.happy:
      case CoachState.celebrating:
        return Icons.star;
      case CoachState.speaking:
        return Icons.volume_up;
      default:
        return Icons.check;
    }
  }
}

class _RobotCoachPainter extends CustomPainter {
  final CoachState state;
  final double t; // 0..1 repeating
  final Color accent;

  _RobotCoachPainter({
    required this.state,
    required this.t,
    required this.accent,
  });

  double _wrapDelta(double a, double b) {
    final d = (a - b).abs();
    return math.min(d, 1.0 - d);
  }

  double _pulse(double center, double width) {
    final d = _wrapDelta(t, center);
    final x = (1.0 - (d / width)).clamp(0.0, 1.0);
    return Curves.easeInOut.transform(x);
  }

  double _blink() {
    // Two quick blinks per loop, but keep it subtle.
    final b1 = _pulse(0.18, 0.05);
    final b2 = _pulse(0.72, 0.04);
    return math.max(b1, b2);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final s = math.min(size.width, size.height);
    final center = Offset(size.width / 2, size.height / 2);

    final bob = math.sin(t * 2 * math.pi) * (s * 0.03);
    final headW = s * 0.72;
    final headH = s * 0.58;
    final headRect = Rect.fromCenter(
      center: center.translate(0, bob * 0.25),
      width: headW,
      height: headH,
    );
    final headRRect = RRect.fromRectAndRadius(
      headRect,
      Radius.circular(headH * 0.22),
    );

    // Head gradient
    final headPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color.lerp(accent, Colors.white, 0.30)!,
          Color.lerp(accent, Colors.black, 0.15)!,
        ],
      ).createShader(headRect);
    canvas.drawRRect(headRRect, headPaint);

    // Head outline
    canvas.drawRRect(
      headRRect,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = s * 0.02
        ..color = Colors.white.withValues(alpha: 0.35),
    );

    // Inner panel
    final panelRect = headRect.deflate(headW * 0.10);
    final panelRRect = RRect.fromRectAndRadius(
      panelRect,
      Radius.circular(headH * 0.18),
    );
    canvas.drawRRect(
      panelRRect,
      Paint()..color = Colors.black.withValues(alpha: 0.14),
    );

    // Antenna
    final antennaX = center.dx;
    final antennaBottom = headRect.top + s * 0.02;
    final antennaTop = headRect.top - s * 0.12;
    final antennaPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.55)
      ..strokeWidth = s * 0.03
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(antennaX, antennaBottom),
      Offset(antennaX, antennaTop),
      antennaPaint,
    );

    final antennaPulse = 0.55 + 0.45 * math.sin(t * 2 * math.pi * 2);
    final antennaColor = switch (state) {
      CoachState.listening => Colors.redAccent,
      CoachState.thinking => Colors.purpleAccent,
      CoachState.celebrating => Colors.amber,
      CoachState.happy => Colors.greenAccent,
      _ => accent,
    };
    final antennaCenter = Offset(antennaX, antennaTop);
    canvas.drawCircle(
      antennaCenter,
      s * 0.05 * (0.9 + 0.15 * antennaPulse),
      Paint()..color = antennaColor.withValues(alpha: 0.95),
    );
    canvas.drawCircle(
      antennaCenter,
      s * 0.10 * (0.9 + 0.20 * antennaPulse),
      Paint()..color = antennaColor.withValues(alpha: 0.18),
    );

    // Eyes
    final blink = _blink();
    final eyeY = panelRect.top + panelRect.height * 0.40;
    final eyeDX = panelRect.width * 0.22;
    final lookShift = state == CoachState.thinking
        ? math.sin(t * 2 * math.pi) * (s * 0.035)
        : 0.0;

    final eyeW = s * 0.12;
    final eyeH = eyeW * (1.0 - 0.78 * blink);

    void drawEye(Offset c) {
      final eyeRect = Rect.fromCenter(
        center: c.translate(lookShift, 0),
        width: eyeW,
        height: eyeH.clamp(s * 0.02, eyeW),
      );
      final eyeRRect = RRect.fromRectAndRadius(
        eyeRect,
        Radius.circular(eyeW * 0.45),
      );

      // Listening glow
      if (state == CoachState.listening) {
        canvas.drawRRect(
          eyeRRect.inflate(s * 0.03),
          Paint()..color = Colors.redAccent.withValues(alpha: 0.16),
        );
      }

      // Celebrating sparkle eyes
      if (state == CoachState.celebrating) {
        canvas.drawRRect(
          eyeRRect,
          Paint()..color = Colors.white.withValues(alpha: 0.92),
        );
        // Star pupil
        final p = Paint()..color = Colors.amber.shade200.withValues(alpha: 0.95);
        canvas.drawCircle(eyeRect.center, eyeRect.width * 0.15, p);
        return;
      }

      // Happy eyes: slightly squinted with a hint of smile
      if (state == CoachState.happy) {
        final squint = (eyeRect.height * 0.55).clamp(s * 0.02, eyeW);
        final squintRect = Rect.fromCenter(
          center: eyeRect.center,
          width: eyeW,
          height: squint,
        );
        canvas.drawRRect(
          RRect.fromRectAndRadius(squintRect, Radius.circular(eyeW * 0.45)),
          Paint()..color = Colors.white.withValues(alpha: 0.90),
        );
        return;
      }

      // Default eye
      canvas.drawRRect(
        eyeRRect,
        Paint()..color = Colors.white.withValues(alpha: 0.90),
      );

      // Pupil (skip if blink)
      if (eyeRect.height > s * 0.04) {
        final pupilPaint = Paint()..color = Colors.black.withValues(alpha: 0.55);
        canvas.drawCircle(
          eyeRect.center.translate(lookShift * 0.25, 0),
          eyeRect.width * 0.18,
          pupilPaint,
        );
      }
    }

    drawEye(Offset(center.dx - eyeDX, eyeY));
    drawEye(Offset(center.dx + eyeDX, eyeY));

    // Mouth
    final mouthW = s * 0.22;
    final mouthY = panelRect.top + panelRect.height * 0.70;
    final mouthRect = Rect.fromCenter(
      center: Offset(center.dx, mouthY),
      width: mouthW,
      height: s * 0.12,
    );
    final mouthPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = s * 0.02
      ..strokeCap = StrokeCap.round
      ..color = Colors.white.withValues(alpha: 0.55);

    final mouthPath = Path();
    final smile = switch (state) {
      CoachState.happy => 0.85,
      CoachState.celebrating => 1.0,
      CoachState.encouraging => 0.55,
      CoachState.thinking => 0.15,
      _ => 0.35,
    };
    mouthPath.moveTo(mouthRect.left, mouthRect.center.dy);
    mouthPath.quadraticBezierTo(
      mouthRect.center.dx,
      mouthRect.center.dy + (mouthRect.height * (smile - 0.5)),
      mouthRect.right,
      mouthRect.center.dy,
    );
    canvas.drawPath(mouthPath, mouthPaint);

    // Thinking dots
    if (state == CoachState.thinking) {
      final dotY = headRect.top - s * 0.18;
      final dotBaseX = center.dx;
      for (int i = 0; i < 3; i++) {
        final phase = (t * 3 + i * 0.25) % 1.0;
        final a = (0.25 + 0.55 * (1.0 - (phase - 0.5).abs() * 2).clamp(0.0, 1.0));
        canvas.drawCircle(
          Offset(dotBaseX + (i - 1) * s * 0.06, dotY),
          s * 0.018,
          Paint()..color = Colors.white.withValues(alpha: a),
        );
      }
    }

    // Waving arm
    if (state == CoachState.waving) {
      final armW = s * 0.12;
      final armH = s * 0.20;
      final armAnchor = Offset(headRect.right + s * 0.02, headRect.top + headRect.height * 0.52);
      final wave = math.sin(t * 2 * math.pi * 2) * 0.6;

      canvas.save();
      canvas.translate(armAnchor.dx, armAnchor.dy);
      canvas.rotate(wave * 0.6);
      final armRect = Rect.fromLTWH(0, -armH * 0.5, armW, armH);
      canvas.drawRRect(
        RRect.fromRectAndRadius(armRect, Radius.circular(armW * 0.5)),
        Paint()..color = Colors.white.withValues(alpha: 0.30),
      );
      canvas.restore();
    }

    // Celebration confetti
    if (state == CoachState.celebrating) {
      final rnd = math.Random(42);
      for (int i = 0; i < 10; i++) {
        final angle = rnd.nextDouble() * 2 * math.pi;
        final radius = s * (0.38 + rnd.nextDouble() * 0.10);
        final p = Offset(
          center.dx + math.cos(angle) * radius,
          center.dy + math.sin(angle) * radius,
        );
        final color = [Colors.amber, Colors.pinkAccent, Colors.lightBlueAccent][i % 3];
        canvas.drawCircle(
          p,
          s * 0.012,
          Paint()..color = color.withValues(alpha: 0.65),
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _RobotCoachPainter oldDelegate) {
    return oldDelegate.state != state || oldDelegate.t != t || oldDelegate.accent != accent;
  }
}

/// Compact Rive Coach Avatar for headers and inline usage
class RiveCoachAvatar extends StatelessWidget {
  final CoachState state;
  final double size;
  final VoidCallback? onTap;

  const RiveCoachAvatar({
    super.key,
    this.state = CoachState.idle,
    this.size = 48,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return RiveCoachWidget(
      state: state,
      size: size,
      showGlow: false,
      onTap: onTap,
    );
  }
}

/// Coach speech bubble with typing animation
class CoachSpeechBubble extends StatefulWidget {
  final String message;
  final CoachState mood;
  final bool animate;
  final VoidCallback? onComplete;

  const CoachSpeechBubble({
    super.key,
    required this.message,
    this.mood = CoachState.idle,
    this.animate = true,
    this.onComplete,
  });

  @override
  State<CoachSpeechBubble> createState() => _CoachSpeechBubbleState();
}

class _CoachSpeechBubbleState extends State<CoachSpeechBubble>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  String _displayedText = '';
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: Duration(milliseconds: widget.message.length * 30),
      vsync: this,
    );

    if (widget.animate) {
      _startTypingAnimation();
    } else {
      _displayedText = widget.message;
    }
  }

  void _startTypingAnimation() async {
    for (int i = 0; i < widget.message.length; i++) {
      if (!mounted) return;
      await Future.delayed(const Duration(milliseconds: 30));
      setState(() {
        _currentIndex = i + 1;
        _displayedText = widget.message.substring(0, _currentIndex);
      });
    }
    widget.onComplete?.call();
  }

  @override
  void didUpdateWidget(CoachSpeechBubble oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.message != widget.message) {
      _displayedText = '';
      _currentIndex = 0;
      if (widget.animate) {
        _startTypingAnimation();
      } else {
        _displayedText = widget.message;
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(20),
          topRight: Radius.circular(20),
          bottomRight: Radius.circular(20),
          bottomLeft: Radius.circular(4),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                AppConstants.coachDisplayName,
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: _getMoodColor(),
                  fontSize: 12,
                ),
              ),
              const SizedBox(width: 6),
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: Colors.green,
                  shape: BoxShape.circle,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _displayedText,
            style: const TextStyle(
              fontSize: 15,
              height: 1.4,
              color: Colors.black87,
            ),
          ),
          if (widget.animate && _currentIndex < widget.message.length)
            _buildTypingIndicator(),
        ],
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(3, (index) {
          return TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.3, end: 1.0),
            duration: Duration(milliseconds: 400 + (index * 100)),
            curve: Curves.easeInOut,
            builder: (context, value, child) {
              return Container(
                margin: const EdgeInsets.symmetric(horizontal: 2),
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: Colors.grey.withValues(alpha: value),
                  shape: BoxShape.circle,
                ),
              );
            },
          );
        }),
      ),
    );
  }

  Color _getMoodColor() {
    switch (widget.mood) {
      case CoachState.happy:
      case CoachState.celebrating:
        return Colors.green;
      case CoachState.encouraging:
        return Colors.orange;
      case CoachState.listening:
        return Colors.blue;
      default:
        return AppTheme.primaryColor;
    }
  }
}

/// Coach with speech bubble combined layout
class CoachWithBubble extends StatelessWidget {
  final String message;
  final CoachState state;
  final double coachSize;
  final VoidCallback? onCoachTap;
  final bool animateMessage;

  const CoachWithBubble({
    super.key,
    required this.message,
    this.state = CoachState.idle,
    this.coachSize = 80,
    this.onCoachTap,
    this.animateMessage = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        RiveCoachWidget(
          state: state,
          size: coachSize,
          showGlow: state == CoachState.speaking || state == CoachState.happy,
          onTap: onCoachTap,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: CoachSpeechBubble(
            message: message,
            mood: state,
            animate: animateMessage,
          ),
        ),
      ],
    );
  }
}





