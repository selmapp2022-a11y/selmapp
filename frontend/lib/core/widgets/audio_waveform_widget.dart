import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Modern audio waveform visualization similar to Siri/Google Assistant
/// Shows dynamic bars that respond to audio input
class AudioWaveformWidget extends StatefulWidget {
  final bool isActive;
  final double amplitude; // 0.0 to 1.0
  final Color? color;
  final double height;
  final int barCount;
  final WaveformStyle style;

  const AudioWaveformWidget({
    super.key,
    this.isActive = false,
    this.amplitude = 0.5,
    this.color,
    this.height = 60,
    this.barCount = 5,
    this.style = WaveformStyle.bars,
  });

  @override
  State<AudioWaveformWidget> createState() => _AudioWaveformWidgetState();
}

enum WaveformStyle {
  bars,      // Classic vertical bars
  wave,      // Smooth sine wave
  circle,    // Circular orb (Siri-style)
  dots,      // Google Assistant dots
}

class _AudioWaveformWidgetState extends State<AudioWaveformWidget>
    with TickerProviderStateMixin {
  late List<AnimationController> _barControllers;
  late AnimationController _waveController;
  late AnimationController _circleController;
  final math.Random _random = math.Random();

  @override
  void initState() {
    super.initState();

    // Initialize bar animations
    _barControllers = List.generate(widget.barCount, (index) {
      final controller = AnimationController(
        duration: Duration(milliseconds: 300 + _random.nextInt(200)),
        vsync: this,
      );
      return controller;
    });

    // Wave animation for smooth wave style
    _waveController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    // Circle animation for orb style
    _circleController = AnimationController(
      duration: const Duration(milliseconds: 3000),
      vsync: this,
    );

    if (widget.isActive) {
      _startAnimations();
    }
  }

  void _startAnimations() {
    for (final controller in _barControllers) {
      controller.repeat(reverse: true);
    }
    _waveController.repeat();
    _circleController.repeat();
  }

  void _stopAnimations() {
    for (final controller in _barControllers) {
      controller.stop();
      controller.value = 0.3;
    }
    _waveController.stop();
    _circleController.stop();
  }

  @override
  void didUpdateWidget(AudioWaveformWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isActive && !oldWidget.isActive) {
      _startAnimations();
    } else if (!widget.isActive && oldWidget.isActive) {
      _stopAnimations();
    }
  }

  @override
  void dispose() {
    for (final controller in _barControllers) {
      controller.dispose();
    }
    _waveController.dispose();
    _circleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = widget.color ?? AppTheme.primaryColor;

    switch (widget.style) {
      case WaveformStyle.bars:
        return _buildBarsWaveform(color);
      case WaveformStyle.wave:
        return _buildSineWaveform(color);
      case WaveformStyle.circle:
        return _buildCircleWaveform(color);
      case WaveformStyle.dots:
        return _buildDotsWaveform(color);
    }
  }

  Widget _buildBarsWaveform(Color color) {
    return SizedBox(
      height: widget.height,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: List.generate(widget.barCount, (index) {
          return AnimatedBuilder(
            animation: _barControllers[index],
            builder: (context, child) {
              final baseHeight = widget.height * 0.3;
              final maxExtraHeight = widget.height * 0.7 * widget.amplitude;
              final animatedHeight = baseHeight +
                  (maxExtraHeight * _barControllers[index].value);

              return Container(
                margin: const EdgeInsets.symmetric(horizontal: 3),
                width: 6,
                height: widget.isActive ? animatedHeight : baseHeight,
                decoration: BoxDecoration(
                  color: widget.isActive
                      ? color.withValues(
                          alpha: 0.7 + (_barControllers[index].value * 0.3),
                        )
                      : color.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(3),
                  boxShadow: widget.isActive
                      ? [
                          BoxShadow(
                            color: color.withValues(alpha: 0.3),
                            blurRadius: 8,
                            spreadRadius: 1,
                          ),
                        ]
                      : null,
                ),
              );
            },
          );
        }),
      ),
    );
  }

  Widget _buildSineWaveform(Color color) {
    return AnimatedBuilder(
      animation: _waveController,
      builder: (context, child) {
        return CustomPaint(
          size: Size(200, widget.height),
          painter: SineWavePainter(
            animation: _waveController.value,
            amplitude: widget.isActive ? widget.amplitude : 0.1,
            color: color,
            isActive: widget.isActive,
          ),
        );
      },
    );
  }

  Widget _buildCircleWaveform(Color color) {
    return AnimatedBuilder(
      animation: _circleController,
      builder: (context, child) {
        return CustomPaint(
          size: Size(widget.height, widget.height),
          painter: CircleOrbPainter(
            animation: _circleController.value,
            amplitude: widget.isActive ? widget.amplitude : 0.2,
            color: color,
            isActive: widget.isActive,
          ),
        );
      },
    );
  }

  Widget _buildDotsWaveform(Color color) {
    return SizedBox(
      height: widget.height,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(4, (index) {
          return AnimatedBuilder(
            animation: _barControllers[index % _barControllers.length],
            builder: (context, child) {
              final scale = widget.isActive
                  ? 1.0 + (_barControllers[index % _barControllers.length].value * 0.5)
                  : 1.0;
              final opacity = widget.isActive
                  ? 0.5 + (_barControllers[index % _barControllers.length].value * 0.5)
                  : 0.3;

              return Container(
                margin: const EdgeInsets.symmetric(horizontal: 4),
                child: Transform.scale(
                  scale: scale,
                  child: Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: opacity),
                      shape: BoxShape.circle,
                      boxShadow: widget.isActive
                          ? [
                              BoxShadow(
                                color: color.withValues(alpha: 0.3),
                                blurRadius: 10,
                                spreadRadius: 2,
                              ),
                            ]
                          : null,
                    ),
                  ),
                ),
              );
            },
          );
        }),
      ),
    );
  }
}

/// Sine wave painter for smooth waveform
class SineWavePainter extends CustomPainter {
  final double animation;
  final double amplitude;
  final Color color;
  final bool isActive;

  SineWavePainter({
    required this.animation,
    required this.amplitude,
    required this.color,
    required this.isActive,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;

    final path = Path();
    final waveHeight = size.height * 0.3 * amplitude;
    final mid = size.height / 2;

    for (int i = 0; i <= size.width.toInt(); i++) {
      final x = i.toDouble();
      final normalizedX = (x / size.width) * 4 * math.pi;
      final y = mid + math.sin(normalizedX + animation * 2 * math.pi) * waveHeight;

      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    // Draw gradient shadow behind
    if (isActive) {
      final shadowPaint = Paint()
        ..color = color.withValues(alpha: 0.2)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 8
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
      canvas.drawPath(path, shadowPaint);
    }

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant SineWavePainter oldDelegate) {
    return animation != oldDelegate.animation ||
        amplitude != oldDelegate.amplitude;
  }
}

/// Circle orb painter for Siri-style visualization
class CircleOrbPainter extends CustomPainter {
  final double animation;
  final double amplitude;
  final Color color;
  final bool isActive;

  CircleOrbPainter({
    required this.animation,
    required this.amplitude,
    required this.color,
    required this.isActive,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseRadius = size.width * 0.35;

    // Draw multiple pulsing rings
    for (int i = 0; i < 3; i++) {
      final ringOffset = (i * 0.33 + animation) % 1.0;
      final ringRadius = baseRadius + (baseRadius * 0.5 * ringOffset * amplitude);
      final ringOpacity = (1.0 - ringOffset) * 0.5;

      final ringPaint = Paint()
        ..color = color.withValues(alpha: isActive ? ringOpacity : 0.1)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2;

      canvas.drawCircle(center, ringRadius, ringPaint);
    }

    // Draw main orb
    final gradient = RadialGradient(
      colors: [
        color.withValues(alpha: isActive ? 0.9 : 0.4),
        color.withValues(alpha: isActive ? 0.6 : 0.2),
        color.withValues(alpha: isActive ? 0.3 : 0.1),
      ],
      stops: const [0.0, 0.6, 1.0],
    );

    final orbPaint = Paint()
      ..shader = gradient.createShader(
        Rect.fromCircle(center: center, radius: baseRadius),
      );

    canvas.drawCircle(center, baseRadius, orbPaint);

    // Draw highlight
    final highlightPaint = Paint()
      ..color = Colors.white.withValues(alpha: isActive ? 0.3 : 0.1)
      ..style = PaintingStyle.fill;

    canvas.drawCircle(
      Offset(center.dx - baseRadius * 0.3, center.dy - baseRadius * 0.3),
      baseRadius * 0.15,
      highlightPaint,
    );
  }

  @override
  bool shouldRepaint(covariant CircleOrbPainter oldDelegate) {
    return animation != oldDelegate.animation ||
        amplitude != oldDelegate.amplitude;
  }
}

/// Listening indicator that combines waveform with text
class ListeningIndicator extends StatelessWidget {
  final bool isListening;
  final String? statusText;
  final Color? color;

  const ListeningIndicator({
    super.key,
    required this.isListening,
    this.statusText,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.8),
        borderRadius: BorderRadius.circular(30),
        boxShadow: [
          BoxShadow(
            color: (color ?? AppTheme.primaryColor).withValues(alpha: 0.3),
            blurRadius: 20,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          AudioWaveformWidget(
            isActive: isListening,
            style: WaveformStyle.dots,
            height: 24,
            color: color ?? AppTheme.primaryColor,
          ),
          if (statusText != null) ...[
            const SizedBox(width: 12),
            Text(
              statusText!,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.9),
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Large centered listening orb (Siri-style)
class ListeningOrb extends StatefulWidget {
  final bool isListening;
  final bool isProcessing;
  final String? statusText;
  final VoidCallback? onTap;
  final double size;

  const ListeningOrb({
    super.key,
    this.isListening = false,
    this.isProcessing = false,
    this.statusText,
    this.onTap,
    this.size = 120,
  });

  @override
  State<ListeningOrb> createState() => _ListeningOrbState();
}

class _ListeningOrbState extends State<ListeningOrb>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    if (widget.isListening || widget.isProcessing) {
      _controller.repeat();
    }
  }

  @override
  void didUpdateWidget(ListeningOrb oldWidget) {
    super.didUpdateWidget(oldWidget);
    if ((widget.isListening || widget.isProcessing) && !_controller.isAnimating) {
      _controller.repeat();
    } else if (!widget.isListening && !widget.isProcessing && _controller.isAnimating) {
      _controller.stop();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isActive = widget.isListening || widget.isProcessing;
    final color = widget.isProcessing
        ? Colors.amber
        : widget.isListening
            ? Colors.red
            : AppTheme.primaryColor;

    return GestureDetector(
      onTap: widget.onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedBuilder(
            animation: _controller,
            builder: (context, child) {
              return Stack(
                alignment: Alignment.center,
                children: [
                  // Pulsing rings
                  if (isActive) ...[
                    _buildPulsingRing(0, color),
                    _buildPulsingRing(0.33, color),
                    _buildPulsingRing(0.66, color),
                  ],

                  // Main orb
                  Container(
                    width: widget.size,
                    height: widget.size,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: RadialGradient(
                        colors: [
                          color.withValues(alpha: isActive ? 0.9 : 0.6),
                          color.withValues(alpha: isActive ? 0.7 : 0.4),
                          color.withValues(alpha: isActive ? 0.5 : 0.2),
                        ],
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: color.withValues(alpha: isActive ? 0.5 : 0.2),
                          blurRadius: isActive ? 30 : 15,
                          spreadRadius: isActive ? 5 : 2,
                        ),
                      ],
                    ),
                    child: Center(
                      child: Icon(
                        widget.isProcessing
                            ? Icons.psychology
                            : widget.isListening
                                ? Icons.mic
                                : Icons.mic_none,
                        size: widget.size * 0.4,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
          if (widget.statusText != null) ...[
            const SizedBox(height: 16),
            Text(
              widget.statusText!,
              style: TextStyle(
                color: color,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPulsingRing(double delay, Color color) {
    final animValue = (_controller.value + delay) % 1.0;
    final scale = 1.0 + (animValue * 0.5);
    final opacity = (1.0 - animValue) * 0.3;

    return Transform.scale(
      scale: scale,
      child: Container(
        width: widget.size,
        height: widget.size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(
            color: color.withValues(alpha: opacity),
            width: 2,
          ),
        ),
      ),
    );
  }
}





