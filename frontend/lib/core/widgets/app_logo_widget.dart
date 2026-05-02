import 'package:flutter/material.dart';

/// Reusable app logo widget that displays the actual SELM app icon
/// instead of generic icons throughout the app.
class AppLogoWidget extends StatelessWidget {
  final double size;
  final bool showGlow;
  final bool circular;
  final BoxDecoration? customDecoration;

  const AppLogoWidget({
    super.key,
    this.size = 80,
    this.showGlow = true,
    this.circular = true,
  }) : customDecoration = null;

  const AppLogoWidget.custom({
    super.key,
    this.size = 80,
    this.showGlow = true,
    this.circular = true,
    this.customDecoration,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: customDecoration ?? BoxDecoration(
        shape: circular ? BoxShape.circle : BoxShape.rectangle,
        borderRadius: circular ? null : BorderRadius.circular(size * 0.2),
        boxShadow: showGlow ? [
          BoxShadow(
            color: const Color(0xFF6366F1).withValues(alpha: 0.3),
            blurRadius: size * 0.25,
            offset: Offset(0, size * 0.1),
          ),
        ] : null,
      ),
      child: ClipRRect(
        borderRadius: circular 
            ? BorderRadius.circular(size / 2)
            : BorderRadius.circular(size * 0.2),
        child: Image.asset(
          'assets/images/selm.png',
          width: size,
          height: size,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) {
            // Fallback to icon-based logo if image fails to load
            return _FallbackLogo(size: size, circular: circular);
          },
        ),
      ),
    );
  }
}

/// Small app logo for use in app bars, nav bars, etc.
class AppLogoSmall extends StatelessWidget {
  final double size;

  const AppLogoSmall({super.key, this.size = 32});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(size * 0.25),
      child: Image.asset(
        'assets/images/selm.png',
        width: size,
        height: size,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) {
          return Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
              ),
              borderRadius: BorderRadius.circular(size * 0.25),
            ),
            child: Icon(
              Icons.auto_stories_rounded,
              size: size * 0.6,
              color: Colors.white,
            ),
          );
        },
      ),
    );
  }
}

/// Animated app logo with pulse effect for welcome/loading screens
class AppLogoAnimated extends StatefulWidget {
  final double size;
  final bool animate;

  const AppLogoAnimated({
    super.key,
    this.size = 140,
    this.animate = true,
  });

  @override
  State<AppLogoAnimated> createState() => _AppLogoAnimatedState();
}

class _AppLogoAnimatedState extends State<AppLogoAnimated>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    _pulseAnimation = Tween<double>(begin: 0.95, end: 1.05).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );

    if (widget.animate) {
      _controller.repeat(reverse: true);
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
      animation: _pulseAnimation,
      builder: (context, child) {
        return Transform.scale(
          scale: widget.animate ? _pulseAnimation.value : 1.0,
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Outer glow ring
              if (widget.animate)
                Container(
                  width: widget.size * 1.3,
                  height: widget.size * 1.3,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        const Color(0xFF6366F1).withValues(alpha: 0.0),
                        const Color(0xFF6366F1).withValues(alpha: 0.1),
                        const Color(0xFF6366F1).withValues(alpha: 0.0),
                      ],
                    ),
                  ),
                ),
              // Secondary glow
              Container(
                width: widget.size * 1.1,
                height: widget.size * 1.1,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF6366F1).withValues(alpha: 0.4),
                      blurRadius: 40,
                      spreadRadius: 10,
                    ),
                    BoxShadow(
                      color: const Color(0xFF8B5CF6).withValues(alpha: 0.2),
                      blurRadius: 60,
                      spreadRadius: 20,
                    ),
                  ],
                ),
              ),
              // Main logo
              ClipOval(
                child: Image.asset(
                  'assets/images/selm.png',
                  width: widget.size,
                  height: widget.size,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return _FallbackLogo(size: widget.size, circular: true);
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Fallback logo widget when image fails to load
class _FallbackLogo extends StatelessWidget {
  final double size;
  final bool circular;

  const _FallbackLogo({
    required this.size,
    required this.circular,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF6366F1),
            Color(0xFF8B5CF6),
            Color(0xFFA855F7),
          ],
        ),
        shape: circular ? BoxShape.circle : BoxShape.rectangle,
        borderRadius: circular ? null : BorderRadius.circular(size * 0.2),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Icon(
            Icons.auto_stories_rounded,
            size: size * 0.4,
            color: Colors.white.withValues(alpha: 0.9),
          ),
          Positioned(
            top: size * 0.15,
            right: size * 0.15,
            child: Icon(
              Icons.auto_awesome,
              size: size * 0.18,
              color: Colors.amber.withValues(alpha: 0.9),
            ),
          ),
        ],
      ),
    );
  }
}




