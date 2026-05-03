import 'package:flutter/material.dart';

/// SELM brand logo — Symbol "S" lockup (Navy bg / White letter).
/// Per SELM Brand Guidelines v1.0 — Symbol use for app icon, favicon, avatars.
const Color _kSelmNavy = Color(0xFF183048);

class AppLogoWidget extends StatelessWidget {
  final double size;
  final bool showGlow;
  final bool circular;
  final BoxDecoration? customDecoration;

  const AppLogoWidget({
    super.key,
    this.size = 80,
    this.showGlow = false,
    this.circular = false,
  }) : customDecoration = null;

  const AppLogoWidget.custom({
    super.key,
    this.size = 80,
    this.showGlow = false,
    this.circular = false,
    this.customDecoration,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: customDecoration ??
          BoxDecoration(
            color: _kSelmNavy,
            shape: circular ? BoxShape.circle : BoxShape.rectangle,
            borderRadius: circular ? null : BorderRadius.circular(size * 0.22),
            boxShadow: showGlow
                ? [
                    BoxShadow(
                      color: _kSelmNavy.withValues(alpha: 0.18),
                      blurRadius: size * 0.30,
                      offset: Offset(0, size * 0.08),
                    ),
                  ]
                : null,
          ),
      alignment: Alignment.center,
      child: Text(
        'S',
        style: TextStyle(
          color: Colors.white,
          fontSize: size * 0.62,
          fontWeight: FontWeight.w800,
          fontFamily: 'Poppins',
          height: 1.0,
          letterSpacing: -1,
        ),
      ),
    );
  }
}

/// Small symbol logo for app bars / nav bars.
class AppLogoSmall extends StatelessWidget {
  final double size;
  const AppLogoSmall({super.key, this.size = 32});

  @override
  Widget build(BuildContext context) =>
      AppLogoWidget(size: size, circular: false, showGlow: false);
}

/// Animated symbol logo with subtle pulse glow for welcome / loading screens.
class AppLogoAnimated extends StatefulWidget {
  final double size;
  final bool animate;

  const AppLogoAnimated({super.key, this.size = 140, this.animate = true});

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
      duration: const Duration(milliseconds: 2200),
      vsync: this,
    );
    _pulseAnimation = Tween<double>(begin: 0.96, end: 1.04)
        .animate(CurvedAnimation(parent: _controller, curve: Curves.easeInOut));
    if (widget.animate) _controller.repeat(reverse: true);
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
      builder: (context, _) => Transform.scale(
        scale: widget.animate ? _pulseAnimation.value : 1.0,
        child: AppLogoWidget(size: widget.size, showGlow: true, circular: false),
      ),
    );
  }
}
