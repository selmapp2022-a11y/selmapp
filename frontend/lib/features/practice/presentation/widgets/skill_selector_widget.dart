import 'package:flutter/material.dart';
import '../../data/models/exercise_models.dart';

class SkillSelectorWidget extends StatelessWidget {
  final Function(ExerciseType) onSkillSelected;

  const SkillSelectorWidget({super.key, required this.onSkillSelected});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      crossAxisSpacing: 16,
      mainAxisSpacing: 16,
      childAspectRatio: 1.2,
      children: ExerciseType.values.map((type) {
        return _buildSkillCard(context, type);
      }).toList(),
    );
  }

  Widget _buildSkillCard(BuildContext context, ExerciseType type) {
    final skillData = _getSkillData(type);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => onSkillSelected(type),
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: skillData['colors'] as List<Color>,
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: (skillData['colors'] as List<Color>)[0].withValues(
                  alpha: 0.3,
                ),
                blurRadius: 8,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 50,
                  height: 50,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(25),
                  ),
                  child: Icon(
                    skillData['icon'] as IconData,
                    color: Colors.white,
                    size: 28,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  skillData['name'] as String,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 4),
                Text(
                  skillData['description'] as String,
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.9),
                    fontSize: 12,
                  ),
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Map<String, dynamic> _getSkillData(ExerciseType type) {
    switch (type) {
      case ExerciseType.vocabulary:
        return {
          'name': 'Vocabulary',
          'description': 'Learn new words and meanings',
          'icon': Icons.menu_book,
          'colors': [const Color(0xFF9C27B0), const Color(0xFFE91E63)],
        };
      case ExerciseType.grammar:
        return {
          'name': 'Grammar',
          'description': 'Master English rules',
          'icon': Icons.rule,
          'colors': [const Color(0xFF2196F3), const Color(0xFF03DAC6)],
        };
      case ExerciseType.reading:
        return {
          'name': 'Reading',
          'description': 'Improve comprehension',
          'icon': Icons.auto_stories,
          'colors': [const Color(0xFF4CAF50), const Color(0xFF8BC34A)],
        };
      case ExerciseType.listening:
        return {
          'name': 'Listening',
          'description': 'Train your ears',
          'icon': Icons.headphones,
          'colors': [const Color(0xFFFF9800), const Color(0xFFFFC107)],
        };
      case ExerciseType.speaking:
        return {
          'name': 'Speaking',
          'description': 'Practice pronunciation',
          'icon': Icons.record_voice_over,
          'colors': [const Color(0xFFF44336), const Color(0xFFFF5722)],
        };
      case ExerciseType.writing:
        return {
          'name': 'Writing',
          'description': 'Express your thoughts',
          'icon': Icons.edit,
          'colors': [const Color(0xFF607D8B), const Color(0xFF9E9E9E)],
        };
      case ExerciseType.conversation:
        return {
          'name': 'Conversation',
          'description': 'Interactive dialogues',
          'icon': Icons.chat,
          'colors': [const Color(0xFF795548), const Color(0xFFBCAAA4)],
        };
    }
  }
}
