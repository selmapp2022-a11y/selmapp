import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// A celebratory overlay that appears when the user achieves something
class CelebrationOverlay extends StatefulWidget {
  final String title;
  final String subtitle;
  final String? emoji;
  final int? points;
  final VoidCallback onDismiss;
  final CelebrationType type;

  const CelebrationOverlay({
    super.key,
    required this.title,
    required this.subtitle,
    this.emoji,
    this.points,
    required this.onDismiss,
    this.type = CelebrationType.success,
  });

  @override
  State<CelebrationOverlay> createState() => _CelebrationOverlayState();
}

enum CelebrationType {
  success,      // General success
  streak,       // Streak achievement
  levelUp,      // Level up
  perfectScore, // 100% accuracy
  dailyGoal,    // Daily goal met
  milestone,    // Milestone reached
}

class _CelebrationOverlayState extends State<CelebrationOverlay>
    with TickerProviderStateMixin {
  late AnimationController _mainController;
  late AnimationController _confettiController;
  late Animation<double> _scaleAnimation;
  late Animation<double> _fadeAnimation;
  late Animation<double> _bounceAnimation;
  
  final List<_ConfettiParticle> _particles = [];
  final Random _random = Random();

  @override
  void initState() {
    super.initState();
    
    _mainController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    
    _confettiController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    );

    _scaleAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainController,
        curve: Curves.elasticOut,
      ),
    );
    
    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainController,
        curve: const Interval(0.0, 0.5, curve: Curves.easeOut),
      ),
    );

    _bounceAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(
        parent: _mainController,
        curve: Curves.bounceOut,
      ),
    );

    // Generate confetti particles
    _generateConfetti();
    
    _mainController.forward();
    _confettiController.forward();
    
    // Auto dismiss after 3 seconds
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) {
        _dismiss();
      }
    });
  }

  void _generateConfetti() {
    for (int i = 0; i < 50; i++) {
      _particles.add(_ConfettiParticle(
        x: _random.nextDouble(),
        y: -0.1 - _random.nextDouble() * 0.3,
        color: _getRandomColor(),
        size: 6 + _random.nextDouble() * 8,
        speed: 0.5 + _random.nextDouble() * 0.5,
        rotation: _random.nextDouble() * 360,
        rotationSpeed: (_random.nextDouble() - 0.5) * 10,
      ));
    }
  }

  Color _getRandomColor() {
    final colors = [
      Colors.red,
      Colors.blue,
      Colors.green,
      Colors.yellow,
      Colors.purple,
      Colors.orange,
      Colors.pink,
      Colors.cyan,
    ];
    return colors[_random.nextInt(colors.length)];
  }

  void _dismiss() {
    _mainController.reverse().then((_) {
      widget.onDismiss();
    });
  }

  @override
  void dispose() {
    _mainController.dispose();
    _confettiController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: AnimatedBuilder(
        animation: Listenable.merge([_mainController, _confettiController]),
        builder: (context, child) {
          return Stack(
            children: [
              // Backdrop
              GestureDetector(
                onTap: _dismiss,
                child: Container(
                  color: Colors.black.withValues(alpha: 0.6 * _fadeAnimation.value),
                ),
              ),
              
              // Confetti
              ..._particles.map((particle) => _buildConfettiParticle(particle)),
              
              // Main content
              Center(
                child: Transform.scale(
                  scale: _scaleAnimation.value,
                  child: _buildCelebrationCard(context),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildConfettiParticle(_ConfettiParticle particle) {
    final progress = _confettiController.value;
    final y = particle.y + progress * particle.speed * 1.5;
    final rotation = particle.rotation + progress * particle.rotationSpeed * 360;
    
    if (y > 1.2) return const SizedBox.shrink();
    
    return Positioned(
      left: MediaQuery.of(context).size.width * particle.x,
      top: MediaQuery.of(context).size.height * y,
      child: Transform.rotate(
        angle: rotation * 3.14159 / 180,
        child: Container(
          width: particle.size,
          height: particle.size * 0.6,
          decoration: BoxDecoration(
            color: particle.color.withValues(alpha: 1.0 - progress * 0.5),
            borderRadius: BorderRadius.circular(2),
          ),
        ),
      ),
    );
  }

  Widget _buildCelebrationCard(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(32),
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        gradient: _getTypeGradient(),
        borderRadius: BorderRadius.circular(32),
        boxShadow: [
          BoxShadow(
            color: _getTypeColor().withValues(alpha: 0.4),
            blurRadius: 30,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Emoji/Icon
          Transform.scale(
            scale: _bounceAnimation.value,
            child: Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                shape: BoxShape.circle,
                border: Border.all(
                  color: Colors.white.withValues(alpha: 0.4),
                  width: 3,
                ),
              ),
              child: Center(
                child: Text(
                  widget.emoji ?? _getDefaultEmoji(),
                  style: const TextStyle(fontSize: 48),
                ),
              ),
            ),
          ),
          const SizedBox(height: 24),
          
          // Title
          Text(
            widget.title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          
          // Subtitle
          Text(
            widget.subtitle,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
          
          // Points
          if (widget.points != null) ...[
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.star, color: Colors.amber, size: 24),
                  const SizedBox(width: 8),
                  Text(
                    '+${widget.points} points',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ],
          
          const SizedBox(height: 24),
          
          // Coach message
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                const Text('🎯', style: TextStyle(fontSize: 24)),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _getCoachMessage(),
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.white.withValues(alpha: 0.9),
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
              ],
            ),
          ),
          
          const SizedBox(height: 24),
          
          // Continue button
          ElevatedButton(
            onPressed: _dismiss,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: _getTypeColor(),
              padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            child: const Text(
              'Continue Training',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 16,
              ),
            ),
          ),
        ],
      ),
    );
  }

  LinearGradient _getTypeGradient() {
    switch (widget.type) {
      case CelebrationType.success:
        return const LinearGradient(
          colors: [Color(0xFF4CAF50), Color(0xFF2E7D32)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CelebrationType.streak:
        return const LinearGradient(
          colors: [Colors.orange, Colors.deepOrange],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CelebrationType.levelUp:
        return LinearGradient(
          colors: [AppTheme.primaryColor, Colors.purple],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CelebrationType.perfectScore:
        return const LinearGradient(
          colors: [Colors.amber, Colors.orange],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CelebrationType.dailyGoal:
        return const LinearGradient(
          colors: [Colors.teal, Colors.cyan],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CelebrationType.milestone:
        return const LinearGradient(
          colors: [Colors.purple, Colors.pink],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
    }
  }

  Color _getTypeColor() {
    switch (widget.type) {
      case CelebrationType.success:
        return Colors.green;
      case CelebrationType.streak:
        return Colors.orange;
      case CelebrationType.levelUp:
        return AppTheme.primaryColor;
      case CelebrationType.perfectScore:
        return Colors.amber;
      case CelebrationType.dailyGoal:
        return Colors.teal;
      case CelebrationType.milestone:
        return Colors.purple;
    }
  }

  String _getDefaultEmoji() {
    switch (widget.type) {
      case CelebrationType.success:
        return '✅';
      case CelebrationType.streak:
        return '🔥';
      case CelebrationType.levelUp:
        return '⬆️';
      case CelebrationType.perfectScore:
        return '💯';
      case CelebrationType.dailyGoal:
        return '🎯';
      case CelebrationType.milestone:
        return '🏆';
    }
  }

  String _getCoachMessage() {
    switch (widget.type) {
      case CelebrationType.success:
        return '"Excellent work! Every exercise makes you stronger!"';
      case CelebrationType.streak:
        return '"Consistency is the key to mastery! Keep showing up!"';
      case CelebrationType.levelUp:
        return '"You\'re leveling up! Your hard work is paying off!"';
      case CelebrationType.perfectScore:
        return '"PERFECT! You nailed it! That\'s the focus I love to see!"';
      case CelebrationType.dailyGoal:
        return '"Goal crushed! You\'re building great habits!"';
      case CelebrationType.milestone:
        return '"What a milestone! You should be incredibly proud!"';
    }
  }
}

class _ConfettiParticle {
  final double x;
  final double y;
  final Color color;
  final double size;
  final double speed;
  final double rotation;
  final double rotationSpeed;

  _ConfettiParticle({
    required this.x,
    required this.y,
    required this.color,
    required this.size,
    required this.speed,
    required this.rotation,
    required this.rotationSpeed,
  });
}

/// Helper to show celebration overlay
void showCelebration(
  BuildContext context, {
  required String title,
  required String subtitle,
  String? emoji,
  int? points,
  CelebrationType type = CelebrationType.success,
}) {
  final overlay = OverlayEntry(
    builder: (context) => CelebrationOverlay(
      title: title,
      subtitle: subtitle,
      emoji: emoji,
      points: points,
      type: type,
      onDismiss: () {},
    ),
  );

  Overlay.of(context).insert(overlay);

  // The overlay removes itself when dismissed
  Future.delayed(const Duration(seconds: 4), () {
    overlay.remove();
  });
}











