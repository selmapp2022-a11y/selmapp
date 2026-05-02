import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/rive_coach_widget.dart';

/// Innovative Welcome Page with "The Confidence Loop" Story Animation
/// Shows the transformation: Confused user -> AI Coach appears -> User becomes confident
class InnovativeWelcomePage extends StatefulWidget {
  const InnovativeWelcomePage({super.key});

  @override
  State<InnovativeWelcomePage> createState() => _InnovativeWelcomePageState();
}

class _InnovativeWelcomePageState extends State<InnovativeWelcomePage>
    with TickerProviderStateMixin {
  // Animation controllers
  late AnimationController _storyController;
  late AnimationController _pulseController;
  late AnimationController _particleController;
  late AnimationController _contentController;

  // Story phases
  int _currentPhase = 0;

  @override
  void initState() {
    super.initState();
    _initAnimations();
    _startStorySequence();
  }

  void _initAnimations() {
    _storyController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);

    _particleController = AnimationController(
      duration: const Duration(seconds: 15),
      vsync: this,
    )..repeat();

    _contentController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    // Don't block the user from logging in/registering.
    // Keep the story animation, but show the CTA immediately.
    _contentController.value = 1.0;
  }

  void _startStorySequence() async {
    // Phase 0: Initial confused state
    await Future.delayed(const Duration(milliseconds: 500));
    if (!mounted) return;

    // Phase 1: Show confused user
    setState(() => _currentPhase = 1);
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;

    // Phase 2: AI Tutor appears
    setState(() => _currentPhase = 2);
    _storyController.forward();
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;

    // Phase 3: Transformation wave
    setState(() => _currentPhase = 3);
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;

    // Phase 4: User confident
    setState(() => _currentPhase = 4);
    await Future.delayed(const Duration(milliseconds: 1500));
    if (!mounted) return;

    // Show features and CTA
    _contentController.forward();
  }

  @override
  void dispose() {
    _storyController.dispose();
    _pulseController.dispose();
    _particleController.dispose();
    _contentController.dispose();
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

          // Magic wave effect during transformation
          if (_currentPhase == 3) _buildMagicWaveEffect(size),

          // Main content
          SafeArea(
            child: Column(
              children: [
                // Story Animation Area
                Expanded(
                  flex: 3,
                  child: _buildStoryAnimation(size),
                ),

                // Features and CTA
                _buildBottomContent(),
              ],
            ),
          ),

          // Skip button removed per user request
        ],
      ),
    );
  }

  Widget _buildAnimatedBackground() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final pulseValue = Tween<double>(begin: 0.0, end: 1.0)
            .animate(_pulseController)
            .value;

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
                  pulseValue,
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
          painter: MagicParticlesPainter(
            animation: _particleController.value,
            phase: _currentPhase,
          ),
        );
      },
    );
  }

  Widget _buildMagicWaveEffect(Size size) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 1500),
      builder: (context, value, child) {
        return CustomPaint(
          size: size,
          painter: MagicWavePainter(
            progress: value,
            color: AppTheme.primaryColor,
          ),
        );
      },
    );
  }

  Widget _buildStoryAnimation(Size size) {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Phase 1-4: The Story
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 600),
          child: _buildCurrentPhaseContent(),
        ),
      ],
    );
  }

  Widget _buildCurrentPhaseContent() {
    switch (_currentPhase) {
      case 0:
        return _buildLoadingState();
      case 1:
        return _buildConfusedUserPhase();
      case 2:
        return _buildCoachAppearsPhase();
      case 3:
        return _buildTransformationPhase();
      case 4:
        return _buildConfidentUserPhase();
      default:
        return _buildFinalState();
    }
  }

  Widget _buildLoadingState() {
    return const SizedBox.shrink();
  }

  Widget _buildConfusedUserPhase() {
    return Column(
      key: const ValueKey('phase1'),
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Confused speech bubble
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.0, end: 1.0),
          duration: const Duration(milliseconds: 500),
          builder: (context, value, child) {
            return Transform.scale(
              scale: value,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 16,
                ),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.2),
                      blurRadius: 15,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    const Text(
                      'Hmm...',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: Colors.grey,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '"I want to speak English\nbut I\'m not sure how..."',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 16,
                        color: Colors.grey[600],
                        fontStyle: FontStyle.italic,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),

        const SizedBox(height: 24),

        // Confused user representation
        _buildUserAvatar(isConfused: true),

        const SizedBox(height: 24),

        // Phase indicator text
        _buildPhaseText('You want to improve your English...'),
      ],
    );
  }

  Widget _buildCoachAppearsPhase() {
    return Column(
      key: const ValueKey('phase2'),
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // AI Coach appears with glow
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.0, end: 1.0),
          duration: const Duration(milliseconds: 800),
          curve: Curves.elasticOut,
          builder: (context, value, child) {
            return Transform.scale(
              scale: value,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // Glow effect
                  Container(
                    width: 180,
                    height: 180,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.primaryColor.withValues(alpha: 0.5),
                          blurRadius: 40,
                          spreadRadius: 10,
                        ),
                      ],
                    ),
                  ),

                  // Coach avatar (built-in Flutter robot)
                  RiveCoachWidget(
                    state: CoachState.waving,
                    size: 150,
                    showGlow: true,
                  ),
                ],
              ),
            );
          },
        ),

        const SizedBox(height: 24),

        // Coach introduction bubble
        _buildCoachSpeechBubble(
          'Hi there! I\'m your AI Coach.\nLet me help you speak with confidence!',
        ),

        const SizedBox(height: 24),

        _buildPhaseText('Meet your personal AI English trainer'),
      ],
    );
  }

  Widget _buildTransformationPhase() {
    return Column(
      key: const ValueKey('phase3'),
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Magic transformation in progress
        Stack(
          alignment: Alignment.center,
          children: [
            // Built-in coach + magic orb
            _buildMagicOrb(),
            Positioned.fill(
              child: Center(
                child: RiveCoachWidget(
                  state: CoachState.thinking,
                  size: 170,
                  showGlow: true,
                ),
              ),
            ),

            // Sparkles around
            ...List.generate(8, (index) => _buildSparkle(index)),
          ],
        ),

        const SizedBox(height: 32),

        _buildPhaseText(
          'Transforming your English skills...',
          showGlow: true,
        ),
      ],
    );
  }

  Widget _buildConfidentUserPhase() {
    return Column(
      key: const ValueKey('phase4'),
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Success speech bubble
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.0, end: 1.0),
          duration: const Duration(milliseconds: 500),
          builder: (context, value, child) {
            return Transform.scale(
              scale: value,
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 16,
                ),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.green.withValues(alpha: 0.9),
                      Colors.teal.withValues(alpha: 0.9),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.green.withValues(alpha: 0.4),
                      blurRadius: 15,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: const Column(
                  children: [
                    Text(
                      '✨',
                      style: TextStyle(fontSize: 28),
                    ),
                    SizedBox(height: 8),
                    Text(
                      '"Now I can speak English\nwith confidence!"',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 16,
                        color: Colors.white,
                        fontWeight: FontWeight.w500,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),

        const SizedBox(height: 24),

        // Confident user avatar
        _buildUserAvatar(isConfused: false),

        const SizedBox(height: 24),

        _buildPhaseText('You\'re ready to succeed! 🎉', isSuccess: true),
      ],
    );
  }

  Widget _buildFinalState() {
    return Column(
      key: const ValueKey('final'),
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // App logo with coach
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            RiveCoachWidget(
              state: CoachState.happy,
              size: 100,
              showGlow: true,
            ),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ShaderMask(
                  shaderCallback: (bounds) => const LinearGradient(
                    colors: [Colors.white, Color(0xFFE0E7FF)],
                  ).createShader(bounds),
                  child: const Text(
                    'Selm',
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
                Text(
                  'Your Personal English Coach',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildUserAvatar({required bool isConfused}) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 500),
      builder: (context, value, child) {
        return Transform.scale(
          scale: value,
          child: Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: isConfused
                    ? [Colors.grey[400]!, Colors.grey[600]!]
                    : [Colors.green, Colors.teal],
              ),
              boxShadow: [
                BoxShadow(
                  color: (isConfused ? Colors.grey : Colors.green)
                      .withValues(alpha: 0.4),
                  blurRadius: 15,
                  offset: const Offset(0, 5),
                ),
              ],
            ),
            child: Center(
              child: Text(
                isConfused ? '😕' : '😊',
                style: const TextStyle(fontSize: 36),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildCoachSpeechBubble(String text) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 500),
      curve: Curves.elasticOut,
      builder: (context, value, child) {
        return Transform.scale(
          scale: value,
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 32),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
              ),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primaryColor.withValues(alpha: 0.4),
                  blurRadius: 15,
                  offset: const Offset(0, 5),
                ),
              ],
            ),
            child: Text(
              text,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16,
                color: Colors.white,
                fontWeight: FontWeight.w500,
                height: 1.4,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildMagicOrb() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final scale = 1.0 +
            (Tween<double>(begin: 0.0, end: 0.2)
                .animate(_pulseController)
                .value);

        return Transform.scale(
          scale: scale,
          child: Container(
            width: 120,
            height: 120,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  AppTheme.primaryColor,
                  AppTheme.primaryColor.withValues(alpha: 0.5),
                  Colors.transparent,
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primaryColor.withValues(alpha: 0.6),
                  blurRadius: 30,
                  spreadRadius: 10,
                ),
              ],
            ),
            child: const Center(
              child: Icon(
                Icons.auto_awesome,
                size: 50,
                color: Colors.white,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildSparkle(int index) {
    final angle = (index / 8) * 2 * math.pi;
    final radius = 100.0;

    return AnimatedBuilder(
      animation: _particleController,
      builder: (context, child) {
        final offset = (_particleController.value + index * 0.1) % 1.0;
        final currentRadius = radius * (0.8 + offset * 0.4);
        final opacity = (1.0 - offset).clamp(0.0, 1.0);

        return Positioned(
          left: math.cos(angle) * currentRadius + 100 - 6,
          top: math.sin(angle) * currentRadius + 100 - 6,
          child: Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.amber.withValues(alpha: opacity),
              boxShadow: [
                BoxShadow(
                  color: Colors.amber.withValues(alpha: opacity * 0.5),
                  blurRadius: 8,
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildPhaseText(
    String text, {
    bool showGlow = false,
    bool isSuccess = false,
  }) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 400),
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            decoration: BoxDecoration(
              color: isSuccess
                  ? Colors.green.withValues(alpha: 0.2)
                  : Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
              boxShadow: showGlow
                  ? [
                      BoxShadow(
                        color: AppTheme.primaryColor.withValues(alpha: 0.3),
                        blurRadius: 20,
                      ),
                    ]
                  : null,
            ),
            child: Text(
              text,
              style: TextStyle(
                fontSize: 16,
                color: isSuccess ? Colors.green[300] : Colors.white,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildBottomContent() {
    return FadeTransition(
      opacity: CurvedAnimation(
        parent: _contentController,
        curve: Curves.easeOut,
      ),
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0, 0.3),
          end: Offset.zero,
        ).animate(CurvedAnimation(
          parent: _contentController,
          curve: Curves.easeOut,
        )),
        child: Container(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              // Feature highlights
              _buildFeatureHighlights(),

              const SizedBox(height: 24),

              // CTA Buttons
              _buildActionButtons(),

              const SizedBox(height: 16),

              // Terms text
              Text(
                'By continuing, you agree to our Terms of Service and Privacy Policy',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.white.withValues(alpha: 0.5),
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFeatureHighlights() {
    final features = [
      {'icon': Icons.psychology, 'text': 'AI Coach'},
      {'icon': Icons.record_voice_over, 'text': 'Speak'},
      {'icon': Icons.auto_graph, 'text': 'Progress'},
    ];

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: features.map((feature) {
        return Column(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                gradient: AppTheme.primaryGradient,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                feature['icon'] as IconData,
                color: Colors.white,
                size: 28,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              feature['text'] as String,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.9),
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        );
      }).toList(),
    );
  }

  Widget _buildActionButtons() {
    return Column(
      children: [
        // Primary CTA
        Container(
          width: double.infinity,
          height: 56,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: AppTheme.primaryColor.withValues(alpha: 0.4),
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
                  'Start Your Journey',
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
                    color: Colors.white.withValues(alpha: 0.2),
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

        // Secondary CTA
        SizedBox(
          width: double.infinity,
          height: 56,
          child: OutlinedButton(
            onPressed: () => context.go('/login'),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.white,
              side: BorderSide(
                color: Colors.white.withValues(alpha: 0.3),
                width: 1.5,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
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
    );
  }

}

/// Custom painter for magic particles during story
class MagicParticlesPainter extends CustomPainter {
  final double animation;
  final int phase;

  MagicParticlesPainter({
    required this.animation,
    required this.phase,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..style = PaintingStyle.fill;
    final random = math.Random(42);

    final particleCount = phase >= 3 ? 50 : 25;
    final baseOpacity = phase >= 3 ? 0.6 : 0.3;

    for (int i = 0; i < particleCount; i++) {
      final baseX = random.nextDouble() * size.width;
      final baseY = random.nextDouble() * size.height;
      final radius = 1.0 + random.nextDouble() * 3.0;
      final speed = 0.2 + random.nextDouble() * 0.8;
      final phase = random.nextDouble() * 2 * math.pi;

      final x = baseX + math.sin(animation * 2 * math.pi * speed + phase) * 30;
      final y = baseY + math.cos(animation * 2 * math.pi * speed + phase) * 20;

      final opacity =
          baseOpacity * math.sin(animation * 4 * math.pi + phase).abs();

      final colors = [
        AppTheme.primaryLightColor,
        AppTheme.secondaryColor,
        AppTheme.accentColor,
        Colors.white,
      ];
      final color = colors[i % colors.length];

      paint.color = color.withValues(alpha: opacity);
      canvas.drawCircle(Offset(x, y), radius, paint);
    }
  }

  @override
  bool shouldRepaint(covariant MagicParticlesPainter oldDelegate) {
    return animation != oldDelegate.animation || phase != oldDelegate.phase;
  }
}

/// Custom painter for magic wave effect during transformation
class MagicWavePainter extends CustomPainter {
  final double progress;
  final Color color;

  MagicWavePainter({
    required this.progress,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final maxRadius = math.sqrt(size.width * size.width + size.height * size.height) / 2;
    final currentRadius = maxRadius * progress;

    final paint = Paint()
      ..shader = RadialGradient(
        colors: [
          Colors.transparent,
          color.withValues(alpha: 0.3 * (1 - progress)),
          color.withValues(alpha: 0.5 * (1 - progress)),
          Colors.transparent,
        ],
        stops: const [0.0, 0.3, 0.6, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: currentRadius));

    canvas.drawCircle(center, currentRadius, paint);
  }

  @override
  bool shouldRepaint(covariant MagicWavePainter oldDelegate) {
    return progress != oldDelegate.progress;
  }
}



