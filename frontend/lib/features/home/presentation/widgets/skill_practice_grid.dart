import 'dart:ui';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';

/// Interactive skill practice grid with real-time data from API
class SkillPracticeGrid extends StatefulWidget {
  final Map<String, double>? skillLevels;

  const SkillPracticeGrid({super.key, this.skillLevels});

  @override
  State<SkillPracticeGrid> createState() => _SkillPracticeGridState();
}

class _SkillPracticeGridState extends State<SkillPracticeGrid> {
  late ApiClient _apiClient;
  Map<String, double> _skillLevels = {};
  final Map<String, int> _availableExercises = {};
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient(SecureStorage());
    _skillLevels = widget.skillLevels ?? {};
    _loadSkillData();
  }

  Future<void> _loadSkillData() async {
    try {
      // Get user progress with skill levels
      final progressResponse = await _apiClient.get('/progress/');
      if (!mounted) return;
      
      if (progressResponse.statusCode == 200) {
        final data = progressResponse.data as Map<String, dynamic>;
        final skillStats = data['skill_statistics'] as Map<String, dynamic>? ?? {};
        
        if (mounted) {
          setState(() {
            skillStats.forEach((key, value) {
              if (value is Map) {
                _skillLevels[key.toLowerCase()] = 
                    ((value['mastery_percentage'] ?? value['accuracy'] ?? 0) as num).toDouble();
              }
            });
          });
        }
      }

      if (!mounted) return;

      // Get ready content to check available exercises
      final contentResponse = await _apiClient.get('/practice-content/ready');
      if (!mounted) return;
      
      if (contentResponse.statusCode == 200) {
        final data = contentResponse.data as Map<String, dynamic>;
        final readyContent = data['ready_content'] as Map<String, dynamic>? ?? {};
        
        if (mounted) {
          setState(() {
            readyContent.forEach((key, value) {
              if (value is List) {
                _availableExercises[key.toLowerCase()] = value.length;
              }
            });
          });
        }
      }
    } catch (e) {
      if (kDebugMode) {
        print('Error loading skill data: $e');
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final skills = [
      _SkillData(
        type: 'vocabulary',
        name: 'Vocabulary',
        icon: Icons.menu_book_rounded,
        color: Colors.purple,
        level: _skillLevels['vocabulary'] ?? 0,
        available: _availableExercises['vocabulary'] ?? 0,
      ),
      _SkillData(
        type: 'grammar',
        name: 'Grammar',
        icon: Icons.spellcheck_rounded,
        color: Colors.blue,
        level: _skillLevels['grammar'] ?? 0,
        available: _availableExercises['grammar'] ?? 0,
      ),
      _SkillData(
        type: 'reading',
        name: 'Reading',
        icon: Icons.article_rounded,
        color: Colors.green,
        level: _skillLevels['reading'] ?? 0,
        available: _availableExercises['reading'] ?? 0,
      ),
      _SkillData(
        type: 'listening',
        name: 'Listening',
        icon: Icons.headphones_rounded,
        color: Colors.orange,
        level: _skillLevels['listening'] ?? 0,
        available: _availableExercises['listening'] ?? 0,
      ),
      _SkillData(
        type: 'speaking',
        name: 'Speaking',
        icon: Icons.mic_rounded,
        color: Colors.red,
        level: _skillLevels['speaking'] ?? 0,
        available: _availableExercises['speaking'] ?? 0,
      ),
      _SkillData(
        type: 'writing',
        name: 'Writing',
        icon: Icons.edit_rounded,
        color: Colors.teal,
        level: _skillLevels['writing'] ?? 0,
        available: _availableExercises['writing'] ?? 0,
      ),
    ];

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        childAspectRatio: 0.9,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
      ),
      itemCount: skills.length,
      itemBuilder: (context, index) {
        return _SkillCard(
          skill: skills[index],
          isLoading: _isLoading,
          onTap: () => context.push('/practice?type=${skills[index].type}'),
        );
      },
    );
  }
}

class _SkillData {
  final String type;
  final String name;
  final IconData icon;
  final Color color;
  final double level;
  final int available;

  _SkillData({
    required this.type,
    required this.name,
    required this.icon,
    required this.color,
    required this.level,
    required this.available,
  });
}

class _SkillCard extends StatelessWidget {
  final _SkillData skill;
  final bool isLoading;
  final VoidCallback onTap;

  const _SkillCard({
    required this.skill,
    required this.isLoading,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  skill.color.withValues(alpha: 0.35),
                  skill.color.withValues(alpha: 0.15),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(
                color: skill.color.withValues(alpha: 0.3),
              ),
            ),
            child: Stack(
              children: [
                // Background progress ring
                if (!isLoading && skill.level > 0)
                  Positioned(
                    top: 8,
                    right: 8,
                    child: _buildProgressRing(skill.level),
                  ),
                
                // Content
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: 46,
                        height: 46,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(14),
                          boxShadow: [
                            BoxShadow(
                              color: skill.color.withValues(alpha: 0.3),
                              blurRadius: 8,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                        child: Icon(
                          skill.icon,
                          color: Colors.white,
                          size: 24,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        skill.name,
                        style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 4),
                      if (isLoading)
                        SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white.withValues(alpha: 0.5),
                          ),
                        )
                      else if (skill.available > 0)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '${skill.available} ready',
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.9),
                              fontSize: 10,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        )
                      else
                        Text(
                          'Practice',
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.7),
                            fontSize: 10,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProgressRing(double level) {
    return SizedBox(
      width: 24,
      height: 24,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CircularProgressIndicator(
            value: (level / 100).clamp(0.0, 1.0),
            strokeWidth: 3,
            backgroundColor: Colors.white.withValues(alpha: 0.2),
            valueColor: AlwaysStoppedAnimation<Color>(
              Colors.white.withValues(alpha: 0.9),
            ),
          ),
          Text(
            '${level.toInt()}',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 8,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}

/// Compact quick actions row for the home page header area
class QuickActionsRow extends StatelessWidget {
  const QuickActionsRow({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _QuickActionChip(
            icon: Icons.menu_book,
            label: 'Vocab',
            onTap: () => context.push('/practice?type=vocabulary'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _QuickActionChip(
            icon: Icons.spellcheck,
            label: 'Grammar',
            onTap: () => context.push('/practice?type=grammar'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _QuickActionChip(
            icon: Icons.headphones,
            label: 'Listen',
            onTap: () => context.push('/practice?type=listening'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _QuickActionChip(
            icon: Icons.mic,
            label: 'Speak',
            onTap: () => context.push('/practice?type=speaking'),
          ),
        ),
      ],
    );
  }
}

class _QuickActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _QuickActionChip({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withValues(alpha: 0.15)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, color: Colors.white, size: 20),
                const SizedBox(height: 4),
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.9),
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}






