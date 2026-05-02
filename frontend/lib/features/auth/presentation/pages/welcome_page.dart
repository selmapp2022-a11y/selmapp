import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/app_logo_widget.dart';

class WelcomePage extends StatefulWidget {
  const WelcomePage({super.key});

  @override
  State<WelcomePage> createState() => _WelcomePageState();
}

class _WelcomePageState extends State<WelcomePage>
    with TickerProviderStateMixin {
  late AnimationController _logoController;
  late AnimationController _pulseController;
  late AnimationController _contentController;
  late AnimationController _particleController;

  late Animation<double> _logoScale;
  late Animation<double> _logoRotation;
  late Animation<double> _pulseAnimation;
  late Animation<double> _fadeIn;
  late Animation<Offset> _slideUp;

  @override
  void initState() {
    super.initState();
    _initAnimations();
  }

  void _initAnimations() {
    // Logo entrance animation
    _logoController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    _logoScale = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _logoController,
        curve: const Interval(0.0, 0.6, curve: Curves.elasticOut),
      ),
    );

    _logoRotation = Tween<double>(begin: -0.1, end: 0.0).animate(
      CurvedAnimation(
        parent: _logoController,
        curve: const Interval(0.0, 0.6, curve: Curves.easeOut),
      ),
    );

    // Continuous pulse animation for glow effect
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.8, end: 1.2).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    // Content fade and slide animation
    _contentController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );

    _fadeIn = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _contentController,
        curve: const Interval(0.0, 0.8, curve: Curves.easeOut),
      ),
    );

    _slideUp = Tween<Offset>(
      begin: const Offset(0, 0.3),
      end: Offset.zero,
    ).animate(
      CurvedAnimation(
        parent: _contentController,
        curve: const Interval(0.0, 0.8, curve: Curves.easeOut),
      ),
    );

    // Floating particles animation
    _particleController = AnimationController(
      duration: const Duration(seconds: 10),
      vsync: this,
    )..repeat();

    // Start animations sequence
    _logoController.forward().then((_) {
      _contentController.forward();
    });
  }

  @override
  void dispose() {
    _logoController.dispose();
    _pulseController.dispose();
    _contentController.dispose();
    _particleController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;

    return Scaffold(
      body: Stack(
        children: [
          // Animated gradient background
          _buildAnimatedBackground(),

          // Floating particles
          _buildFloatingParticles(size),

          // Main content
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              child: Column(
                children: [
                  const Spacer(flex: 2),

                  // Animated Logo Section
                  _buildAnimatedLogo(),

                  const SizedBox(height: 32),

                  // App Title with Animation
                  _buildAnimatedTitle(),

                  const SizedBox(height: 16),

                  // Tagline
                  _buildTagline(),

                  const Spacer(flex: 2),

                  // Features Section
                  _buildFeaturesSection(),

                  const Spacer(flex: 2),

                  // Action Buttons
                  _buildActionButtons(),

                  const SizedBox(height: 24),

                  // Terms text
                  _buildTermsText(),

                  const SizedBox(height: 16),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnimatedBackground() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        return Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                const Color(0xFF1a1a2e),
                Color.lerp(
                  const Color(0xFF16213e),
                  const Color(0xFF0f3460),
                  _pulseAnimation.value - 0.8,
                )!,
                const Color(0xFF1a1a2e),
              ],
              stops: const [0.0, 0.5, 1.0],
            ),
          ),
        );
      },
    );
  }

  Widget _buildFloatingParticles(Size size) {
    return AnimatedBuilder(
      animation: _particleController,
      builder: (context, child) {
        return CustomPaint(
          size: size,
          painter: ParticlesPainter(
            animation: _particleController.value,
            particleColor: AppTheme.primaryLightColor.withValues(alpha: .3),
          ),
        );
      },
    );
  }

  Widget _buildAnimatedLogo() {
    return AnimatedBuilder(
      animation: Listenable.merge([_logoController, _pulseController]),
      builder: (context, child) {
        return Transform.scale(
          scale: _logoScale.value,
          child: Transform.rotate(
            angle: _logoRotation.value * math.pi,
            child: Stack(
              alignment: Alignment.center,
              children: [
                // Outer glow ring
                Container(
                  width: 180 * _pulseAnimation.value,
                  height: 180 * _pulseAnimation.value,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        AppTheme.primaryColor.withValues(alpha: .0),
                        AppTheme.primaryColor.withValues(alpha: .1),
                        AppTheme.primaryColor.withValues(alpha: .0),
                      ],
                    ),
                  ),
                ),

                // Secondary glow
                Container(
                  width: 150,
                  height: 150,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.primaryColor.withValues(alpha: .4),
                        blurRadius: 40,
                        spreadRadius: 10,
                      ),
                      BoxShadow(
                        color: AppTheme.secondaryColor.withValues(alpha: .2),
                        blurRadius: 60,
                        spreadRadius: 20,
                      ),
                    ],
                  ),
                ),

                // Main logo container - using actual app icon
                const AppLogoWidget(
                  size: 140,
                  showGlow: false,
                  circular: true,
                ),

                // Orbiting dots
                ..._buildOrbitingDots(),
              ],
            ),
          ),
        );
      },
    );
  }

  List<Widget> _buildOrbitingDots() {
    return List.generate(3, (index) {
      final delay = index * 0.33;
      return AnimatedBuilder(
        animation: _particleController,
        builder: (context, child) {
          final angle =
              (_particleController.value + delay) * 2 * math.pi;
          final radius = 85.0;
          return Positioned(
            left: 70 + radius * math.cos(angle) - 4,
            top: 70 + radius * math.sin(angle) - 4,
            child: Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: [
                  AppTheme.primaryLightColor,
                  AppTheme.secondaryColor,
                  AppTheme.accentColor,
                ][index],
                boxShadow: [
                  BoxShadow(
                    color: [
                      AppTheme.primaryLightColor,
                      AppTheme.secondaryColor,
                      AppTheme.accentColor,
                    ][index]
                        .withValues(alpha: .6),
                    blurRadius: 8,
                    spreadRadius: 2,
                  ),
                ],
              ),
            ),
          );
        },
      );
    });
  }

  Widget _buildAnimatedTitle() {
    return SlideTransition(
      position: _slideUp,
      child: FadeTransition(
        opacity: _fadeIn,
        child: ShaderMask(
          shaderCallback: (bounds) => const LinearGradient(
            colors: [Colors.white, Color(0xFFE0E7FF)],
          ).createShader(bounds),
          child: Text(
            'Selm',
            style: Theme.of(context).textTheme.displayLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 42,
                  letterSpacing: 1.5,
                ),
          ),
        ),
      ),
    );
  }

  Widget _buildTagline() {
    return SlideTransition(
      position: _slideUp,
      child: FadeTransition(
        opacity: _fadeIn,
        child: Column(
          children: [
            Text(
              'Your Personal English Coach',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: Colors.white.withValues(alpha: .95),
                    fontWeight: FontWeight.w500,
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: .1),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: Colors.white.withValues(alpha: .2),
                ),
              ),
              child: Text(
                '✨ AI-Powered Learning Experience',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppTheme.accentColor,
                      fontWeight: FontWeight.w500,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeaturesSection() {
    final features = [
      _FeatureItem(
        icon: Icons.psychology_outlined,
        title: 'Smart AI Coach',
        description: 'Personalized lessons that adapt to you',
        color: AppTheme.primaryLightColor,
        delay: 0,
      ),
      _FeatureItem(
        icon: Icons.record_voice_over_outlined,
        title: 'Speak & Practice',
        description: 'Perfect your pronunciation',
        color: AppTheme.secondaryColor,
        delay: 1,
      ),
      _FeatureItem(
        icon: Icons.auto_graph_outlined,
        title: 'Track Progress',
        description: 'Watch your skills grow daily',
        color: AppTheme.accentColor,
        delay: 2,
      ),
    ];

    return SlideTransition(
      position: _slideUp,
      child: FadeTransition(
        opacity: _fadeIn,
        child: Column(
          children: features.map((feature) {
            return TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.0, end: 1.0),
              duration: Duration(milliseconds: 600 + feature.delay * 200),
              curve: Curves.easeOut,
              builder: (context, value, child) {
                return Opacity(
                  opacity: value,
                  child: Transform.translate(
                    offset: Offset(30 * (1 - value), 0),
                    child: child,
                  ),
                );
              },
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8.0),
                child: Row(
                  children: [
                    Container(
                      width: 52,
                      height: 52,
                      decoration: BoxDecoration(
                        color: feature.color.withValues(alpha: .15),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: feature.color.withValues(alpha: .3),
                        ),
                      ),
                      child: Icon(
                        feature.icon,
                        color: feature.color,
                        size: 26,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            feature.title,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w600,
                                ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            feature.description,
                            style:
                                Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: Colors.white.withValues(alpha: .7),
                                    ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildActionButtons() {
    return SlideTransition(
      position: _slideUp,
      child: FadeTransition(
        opacity: _fadeIn,
        child: Column(
          children: [
            // Get Started Button with gradient
            Container(
              width: double.infinity,
              height: 56,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [
                    Color(0xFF6366F1),
                    Color(0xFF8B5CF6),
                  ],
                ),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryColor.withValues(alpha: .4),
                    blurRadius: 20,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: ElevatedButton(
                onPressed: () => context.go('/register'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.transparent,
                  shadowColor: Colors.transparent,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Text(
                      'Start Learning Free',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: .2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.arrow_forward_rounded,
                        size: 18,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // Sign In Button
            SizedBox(
              width: double.infinity,
              height: 56,
              child: OutlinedButton(
                onPressed: () => context.go('/login'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: BorderSide(
                    color: Colors.white.withValues(alpha: .3),
                    width: 1.5,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  backgroundColor: Colors.white.withValues(alpha: .05),
                ),
                child: const Text(
                  'I Already Have an Account',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTermsText() {
    return FadeTransition(
      opacity: _fadeIn,
      child: Text(
        'By continuing, you agree to our Terms of Service and Privacy Policy',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.white.withValues(alpha: .5),
            ),
        textAlign: TextAlign.center,
      ),
    );
  }
}

// Note: _LogoIcon class removed - now using AppLogoWidget with actual app icon

// Feature item model
class _FeatureItem {
  final IconData icon;
  final String title;
  final String description;
  final Color color;
  final int delay;

  _FeatureItem({
    required this.icon,
    required this.title,
    required this.description,
    required this.color,
    required this.delay,
  });
}

// Custom particles painter for floating background effect
class ParticlesPainter extends CustomPainter {
  final double animation;
  final Color particleColor;

  ParticlesPainter({
    required this.animation,
    required this.particleColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = particleColor
      ..style = PaintingStyle.fill;

    final random = math.Random(42); // Fixed seed for consistent particles

    for (int i = 0; i < 30; i++) {
      final baseX = random.nextDouble() * size.width;
      final baseY = random.nextDouble() * size.height;
      final radius = 1.0 + random.nextDouble() * 2.5;
      final speed = 0.3 + random.nextDouble() * 0.7;
      final phase = random.nextDouble() * 2 * math.pi;

      // Floating animation
      final x = baseX + math.sin(animation * 2 * math.pi * speed + phase) * 20;
      final y = baseY + math.cos(animation * 2 * math.pi * speed + phase) * 15;

      // Pulse opacity
      final opacity =
          0.3 + 0.4 * math.sin(animation * 4 * math.pi + phase).abs();
      paint.color = particleColor.withValues(alpha: opacity);

      canvas.drawCircle(Offset(x, y), radius, paint);
    }
  }

  @override
  bool shouldRepaint(covariant ParticlesPainter oldDelegate) {
    return animation != oldDelegate.animation;
  }
}
