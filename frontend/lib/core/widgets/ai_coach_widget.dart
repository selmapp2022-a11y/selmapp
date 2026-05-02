import 'dart:ui';
import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../constants/app_constants.dart';

/// Coach mood types that affect the message and appearance
enum CoachMood {
  excited,      // High energy for celebrations
  encouraging,  // For motivation and support
  coaching,     // Giving tips and instructions
  celebrating,  // After achievements
  friendly,     // Default casual interaction
  focused,      // During practice sessions
}

/// The AI Coach persona (user-facing name defined in [AppConstants]).
class AICoachWidget extends StatefulWidget {
  final String message;
  final CoachMood mood;
  final VoidCallback? onTap;
  final bool showPulse;
  final bool compact;
  final Widget? action;

  const AICoachWidget({
    super.key,
    required this.message,
    this.mood = CoachMood.friendly,
    this.onTap,
    this.showPulse = false,
    this.compact = false,
    this.action,
  });

  @override
  State<AICoachWidget> createState() => _AICoachWidgetState();
}

class _AICoachWidgetState extends State<AICoachWidget>
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late AnimationController _bounceController;
  late Animation<double> _pulseAnimation;
  late Animation<double> _bounceAnimation;

  @override
  void initState() {
    super.initState();
    
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );
    
    _bounceController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.08).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    
    _bounceAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _bounceController, curve: Curves.elasticOut),
    );

    if (widget.showPulse) {
      _pulseController.repeat(reverse: true);
    }
    _bounceController.forward();
  }

  @override
  void didUpdateWidget(AICoachWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.message != widget.message) {
      _bounceController.reset();
      _bounceController.forward();
    }
    if (widget.showPulse && !_pulseController.isAnimating) {
      _pulseController.repeat(reverse: true);
    } else if (!widget.showPulse && _pulseController.isAnimating) {
      _pulseController.stop();
      _pulseController.value = 0;
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _bounceController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.compact) {
      return _buildCompactCoach(context);
    }
    return _buildFullCoach(context);
  }

  Widget _buildFullCoach(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([_pulseController, _bounceController]),
      builder: (context, child) {
        return Transform.scale(
          scale: widget.showPulse ? _pulseAnimation.value : 1.0,
          child: Transform.translate(
            offset: Offset(0, 10 * (1 - _bounceAnimation.value)),
            child: Opacity(
              opacity: _bounceAnimation.value.clamp(0.0, 1.0),
              child: _buildCard(context),
            ),
          ),
        );
      },
    );
  }

  Widget _buildCard(BuildContext context) {
    return GestureDetector(
      onTap: widget.onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 15, sigmaY: 15),
          child: Container(
            decoration: BoxDecoration(
              gradient: _getMoodGradient(),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(
                color: _getMoodColor().withValues(alpha: 0.4),
                width: 2,
              ),
              boxShadow: [
                BoxShadow(
                  color: _getMoodColor().withValues(alpha: 0.3),
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
                  Row(
                    children: [
                      _buildCoachAvatar(),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  AppConstants.coachDisplayName,
                                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                _buildMoodBadge(),
                              ],
                            ),
                            const SizedBox(height: 2),
                            Text(
                              _getMoodSubtitle(),
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
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
                          _getMoodEmoji(),
                          style: const TextStyle(fontSize: 24),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            widget.message,
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Colors.white,
                              height: 1.5,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (widget.action != null) ...[
                    const SizedBox(height: 16),
                    widget.action!,
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCompactCoach(BuildContext context) {
    return AnimatedBuilder(
      animation: _bounceController,
      builder: (context, child) {
        return Transform.translate(
          offset: Offset(0, 8 * (1 - _bounceAnimation.value)),
          child: Opacity(
            opacity: _bounceAnimation.value.clamp(0.0, 1.0),
            child: GestureDetector(
              onTap: widget.onTap,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      gradient: _getMoodGradient(),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: _getMoodColor().withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        _buildSmallAvatar(),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            widget.message,
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Colors.white,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
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

  Widget _buildCoachAvatar() {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.white.withValues(alpha: 0.3),
            Colors.white.withValues(alpha: 0.1),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.4),
          width: 2,
        ),
        boxShadow: [
          BoxShadow(
            color: _getMoodColor().withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Center(
        child: Text(
          _getMoodEmoji(),
          style: const TextStyle(fontSize: 28),
        ),
      ),
    );
  }

  Widget _buildSmallAvatar() {
    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.white.withValues(alpha: 0.3),
            Colors.white.withValues(alpha: 0.1),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.3),
        ),
      ),
      child: Center(
        child: Text(
          _getMoodEmoji(),
          style: const TextStyle(fontSize: 20),
        ),
      ),
    );
  }

  Widget _buildMoodBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: _getMoodBadgeColor(),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        _getMoodLabel(),
        style: const TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  LinearGradient _getMoodGradient() {
    switch (widget.mood) {
      case CoachMood.excited:
        return LinearGradient(
          colors: [
            Colors.orange.withValues(alpha: 0.4),
            Colors.deepOrange.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachMood.encouraging:
        return LinearGradient(
          colors: [
            Colors.green.withValues(alpha: 0.4),
            Colors.teal.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachMood.coaching:
        return LinearGradient(
          colors: [
            AppTheme.primaryColor.withValues(alpha: 0.4),
            Colors.blue.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachMood.celebrating:
        return LinearGradient(
          colors: [
            Colors.amber.withValues(alpha: 0.4),
            Colors.orange.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachMood.friendly:
        return LinearGradient(
          colors: [
            Colors.purple.withValues(alpha: 0.4),
            Colors.indigo.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
      case CoachMood.focused:
        return LinearGradient(
          colors: [
            Colors.cyan.withValues(alpha: 0.4),
            Colors.blue.withValues(alpha: 0.25),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        );
    }
  }

  Color _getMoodColor() {
    switch (widget.mood) {
      case CoachMood.excited:
        return Colors.orange;
      case CoachMood.encouraging:
        return Colors.green;
      case CoachMood.coaching:
        return AppTheme.primaryColor;
      case CoachMood.celebrating:
        return Colors.amber;
      case CoachMood.friendly:
        return Colors.purple;
      case CoachMood.focused:
        return Colors.cyan;
    }
  }

  Color _getMoodBadgeColor() {
    switch (widget.mood) {
      case CoachMood.excited:
        return Colors.orange;
      case CoachMood.encouraging:
        return Colors.green;
      case CoachMood.coaching:
        return AppTheme.primaryColor;
      case CoachMood.celebrating:
        return Colors.amber.shade700;
      case CoachMood.friendly:
        return Colors.purple;
      case CoachMood.focused:
        return Colors.cyan.shade700;
    }
  }

  String _getMoodLabel() {
    switch (widget.mood) {
      case CoachMood.excited:
        return 'Pumped!';
      case CoachMood.encouraging:
        return 'Go for it!';
      case CoachMood.coaching:
        return 'Coaching';
      case CoachMood.celebrating:
        return 'Celebrating!';
      case CoachMood.friendly:
        return 'Here to help';
      case CoachMood.focused:
        return 'Focus mode';
    }
  }

  String _getMoodSubtitle() {
    switch (widget.mood) {
      case CoachMood.excited:
        return 'Your AI English Trainer';
      case CoachMood.encouraging:
        return 'Cheering you on!';
      case CoachMood.coaching:
        return 'Personal guidance';
      case CoachMood.celebrating:
        return 'So proud of you!';
      case CoachMood.friendly:
        return 'Your AI English Trainer';
      case CoachMood.focused:
        return 'Let\'s train together';
    }
  }

  String _getMoodEmoji() {
    switch (widget.mood) {
      case CoachMood.excited:
        return '🔥';
      case CoachMood.encouraging:
        return '💪';
      case CoachMood.coaching:
        return '🎯';
      case CoachMood.celebrating:
        return '🎉';
      case CoachMood.friendly:
        return '👋';
      case CoachMood.focused:
        return '🧠';
    }
  }
}

/// Floating AI Coach button for quick access
class FloatingCoachButton extends StatefulWidget {
  final VoidCallback onPressed;
  final bool hasNotification;

  const FloatingCoachButton({
    super.key,
    required this.onPressed,
    this.hasNotification = false,
  });

  @override
  State<FloatingCoachButton> createState() => _FloatingCoachButtonState();
}

class _FloatingCoachButtonState extends State<FloatingCoachButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );
    _scaleAnimation = Tween<double>(begin: 1.0, end: 1.1).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    if (widget.hasNotification) {
      _controller.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(FloatingCoachButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.hasNotification && !_controller.isAnimating) {
      _controller.repeat(reverse: true);
    } else if (!widget.hasNotification) {
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
        return Transform.scale(
          scale: widget.hasNotification ? _scaleAnimation.value : 1.0,
          child: GestureDetector(
            onTap: widget.onPressed,
            child: Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                gradient: AppTheme.primaryGradient,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryColor.withValues(alpha: 0.4),
                    blurRadius: 16,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
              child: Stack(
                children: [
                  Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('🎯', style: TextStyle(fontSize: 24)),
                        Text(
                          'Coach',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (widget.hasNotification)
                    Positioned(
                      top: 4,
                      right: 4,
                      child: Container(
                        width: 14,
                        height: 14,
                        decoration: BoxDecoration(
                          color: Colors.red,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
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

/// Helper class for context-aware coach messages
class CoachMessages {
  static final Random _random = Random();

  static String getGreeting(String userName, int hour) {
    final greetings = hour < 12
        ? [
            'Rise and shine, $userName! 🌅 Ready to level up your English today?',
            'Good morning, champion! ☀️ Let\'s make today count!',
            'Morning, $userName! 💪 Your English muscles need some exercise!',
            'Hey early bird! 🐦 Great time to train those language skills!',
          ]
        : hour < 17
            ? [
                'Hey $userName! 👋 Perfect time for a quick training session!',
                'Good afternoon! 🎯 Let\'s squeeze in some practice!',
                'Hi there, $userName! 💪 Ready to crush some exercises?',
                'Afternoon boost time! ⚡ Let\'s keep that streak going!',
              ]
            : [
                'Evening, $userName! 🌙 Time for a relaxing study session?',
                'Hey night owl! 🦉 Let\'s wind down with some practice!',
                'Good evening! ✨ Even a few minutes of practice counts!',
                'Hi $userName! 🌟 Ready to end the day with some learning?',
              ];
    return greetings[_random.nextInt(greetings.length)];
  }

  static String getEncouragement(int streak) {
    if (streak == 0) {
      return 'Let\'s start your streak today! Just one exercise to begin! 🚀';
    } else if (streak < 3) {
      return 'You\'re building momentum! $streak day${streak > 1 ? 's' : ''} strong! 💪';
    } else if (streak < 7) {
      return 'Incredible consistency! $streak days and counting! 🔥';
    } else if (streak < 30) {
      return 'WOW! $streak day streak! You\'re unstoppable! 🏆';
    } else {
      return 'LEGENDARY! $streak days! You\'re an inspiration! 👑';
    }
  }

  static String getMotivation() {
    final messages = [
      'Every word you learn is a step toward fluency! 📚',
      'Mistakes are just lessons in disguise. Keep going! 💡',
      'You\'re doing better than you think. Trust the process! 🌟',
      'Small daily improvements lead to amazing results! 📈',
      'Your dedication today is tomorrow\'s success! 🎯',
      'Learning a language is a marathon, not a sprint. You\'ve got this! 🏃',
      'Each practice session makes your brain stronger! 🧠',
      'Consistency beats intensity. Keep showing up! 💪',
    ];
    return messages[_random.nextInt(messages.length)];
  }

  static String getCelebration(String achievement) {
    return 'AMAZING! 🎉 You just $achievement! I knew you could do it!';
  }

  static String getSessionStart() {
    final messages = [
      'Let\'s go! Time to make your English shine! ✨',
      'Ready when you are! Let\'s crush this session! 💥',
      'Focus mode: ON. Let\'s do this together! 🎯',
      'Game face on! Your English workout starts now! 🏋️',
    ];
    return messages[_random.nextInt(messages.length)];
  }

  static String getExerciseTip(String exerciseType) {
    switch (exerciseType.toLowerCase()) {
      case 'vocabulary':
        return 'Pro tip: Try to use new words in sentences to remember them better! 📝';
      case 'grammar':
        return 'Focus on understanding WHY, not just WHAT. Grammar will click! 💡';
      case 'listening':
        return 'Close your eyes and really focus on the sounds. You\'ve got this! 👂';
      case 'speaking':
        return 'Don\'t worry about being perfect. Confidence comes with practice! 🎤';
      case 'reading':
        return 'Read actively! Try to predict what comes next in the text. 📖';
      case 'writing':
        return 'Write first, edit later. Let your thoughts flow freely! ✍️';
      default:
        return 'Take your time and trust yourself. You know more than you think! 🌟';
    }
  }

  /// Get personalized message based on user's current state
  static String getPersonalizedMessage({
    required String userName,
    int streak = 0,
    int todayMinutes = 0,
    int dailyGoal = 30,
    String? weakestSkill,
    String? lastCompletedSkill,
    double overallProgress = 0,
  }) {
    final hour = DateTime.now().hour;
    
    // Priority 1: Celebrate goal completion
    if (todayMinutes >= dailyGoal && dailyGoal > 0) {
      final extras = [
        'You\'ve crushed your daily goal! Want to do a bonus round? 🏆',
        'Daily goal complete! You\'re on fire today! 🔥',
        'Look at you go! Goal achieved! Ready for more? 💪',
      ];
      return extras[_random.nextInt(extras.length)];
    }
    
    // Priority 2: Streak celebration
    if (streak >= 7) {
      return getEncouragement(streak);
    }
    
    // Priority 3: Skill-based recommendations
    if (weakestSkill != null && _random.nextBool()) {
      final skillMessages = [
        'I noticed your ${weakestSkill.toLowerCase()} could use some love. Want to work on it? 🎯',
        'Let\'s boost that ${weakestSkill.toLowerCase()} skill today! I have some great exercises ready! 💪',
        'Quick tip: A bit of ${weakestSkill.toLowerCase()} practice could really help you level up! 📈',
      ];
      return skillMessages[_random.nextInt(skillMessages.length)];
    }
    
    // Priority 4: Progress toward goal
    if (todayMinutes > 0 && todayMinutes < dailyGoal) {
      final remaining = dailyGoal - todayMinutes;
      if (remaining <= 5) {
        return 'Almost there! Just $remaining more minutes to hit your goal! 🎯';
      } else if (remaining <= 15) {
        return 'Great progress! $remaining minutes to go. You\'ve got this! 💪';
      }
    }
    
    // Priority 5: Last completed skill follow-up
    if (lastCompletedSkill != null && _random.nextDouble() < 0.3) {
      return 'Great job on that ${lastCompletedSkill.toLowerCase()} practice! Ready for more? ✨';
    }
    
    // Default: Time-based greeting
    return getGreeting(userName, hour);
  }

  /// Get a recommendation for what to practice next
  static String getRecommendation({
    String? weakestSkill,
    int streak = 0,
    int todayMinutes = 0,
    int dailyGoal = 30,
  }) {
    if (todayMinutes == 0) {
      return 'Start with a quick vocabulary exercise to warm up! 📚';
    }
    
    if (weakestSkill != null) {
      final tips = {
        'vocabulary': 'Let\'s expand your word bank! A strong vocabulary opens doors! 🚪',
        'grammar': 'Time to polish that grammar! Correct grammar = clear communication! ✨',
        'listening': 'Train your ears! Good listening = better understanding! 👂',
        'speaking': 'Let\'s practice speaking! Don\'t be shy, I\'m here to help! 🎤',
        'reading': 'Reading boosts all your skills! Let\'s dive into some texts! 📖',
        'writing': 'Express yourself in writing! Practice makes perfect! ✍️',
      };
      return tips[weakestSkill.toLowerCase()] ?? 'Let\'s keep practicing! Every bit counts! 💪';
    }
    
    // Default recommendations based on progress
    if (todayMinutes < 10) {
      return 'A quick 5-minute session is perfect to get started! ⚡';
    } else if (todayMinutes < dailyGoal / 2) {
      return 'You\'re doing great! Keep the momentum going! 🔥';
    } else {
      return 'Almost at your goal! One more exercise will get you there! 🎯';
    }
  }

  /// Get celebration message for completed exercises
  static String getExerciseComplete(int score, int totalQuestions) {
    final percentage = (score / totalQuestions * 100).round();
    
    if (percentage >= 90) {
      final messages = [
        'Outstanding! $percentage% correct! You\'re a star! ⭐',
        'Incredible performance! $score/$totalQuestions! Keep it up! 🏆',
        'Wow! Nearly perfect! You\'re mastering this! 🎉',
      ];
      return messages[_random.nextInt(messages.length)];
    } else if (percentage >= 70) {
      final messages = [
        'Great job! $percentage% is solid progress! 💪',
        'Well done! $score/$totalQuestions correct! 🌟',
        'Nice work! You\'re getting better every day! 📈',
      ];
      return messages[_random.nextInt(messages.length)];
    } else if (percentage >= 50) {
      return 'Good effort! $percentage% - each practice makes you stronger! 💪';
    } else {
      return 'Don\'t worry about the score! Learning happens through practice! 🌱';
    }
  }

  /// Get daily goal progress message
  static String getDailyProgress(int minutes, int goal) {
    final percentage = (minutes / goal * 100).clamp(0, 100).round();
    
    if (percentage >= 100) {
      return 'Daily goal smashed! $minutes minutes of pure dedication! 🎉';
    } else if (percentage >= 75) {
      return 'So close! Just ${goal - minutes} more minutes to your goal! 🔥';
    } else if (percentage >= 50) {
      return 'Halfway there! ${goal - minutes} minutes to go! 💪';
    } else if (percentage >= 25) {
      return 'Good start! Keep going to reach your $goal-minute goal! 📈';
    } else if (minutes > 0) {
      return 'You\'ve started! Every minute counts toward your goal! 🚀';
    } else {
      return 'Ready to begin? Your $goal-minute goal awaits! 🎯';
    }
  }
}











