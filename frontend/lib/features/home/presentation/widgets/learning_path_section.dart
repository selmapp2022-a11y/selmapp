import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_theme.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../onboarding/data/models/onboarding_models.dart';
import '../../../onboarding/data/repositories/onboarding_repository.dart';
import '../../../onboarding/presentation/widgets/lesson_loading_screen.dart';

/// Collapsible learning path section for the Coach Center home page
class LearningPathSection extends StatefulWidget {
  final VoidCallback? onModuleCompleted;

  const LearningPathSection({super.key, this.onModuleCompleted});

  @override
  State<LearningPathSection> createState() => _LearningPathSectionState();
}

class _LearningPathSectionState extends State<LearningPathSection>
    with TickerProviderStateMixin {
  LearningPath? _learningPath;
  bool _isLoading = true;
  bool _isExpanded = false;
  int _selectedWeek = 0;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadLearningPath());
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _loadLearningPath() async {
    setState(() => _isLoading = true);
    
    try {
      final repo = context.read<OnboardingRepository>();
      var path = await repo.loadLearningPath();

      if (path == null || path.modules.isEmpty) {
        final profile = await repo.getUserProfile('me');
        if (profile != null) {
          path = await repo.generateLearningPath(profile);
          await repo.saveLearningPath(path);
        }
      }

      if (mounted) {
        setState(() {
          _learningPath = path;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return _buildLoadingState();
    }

    if (_learningPath == null || _learningPath!.modules.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildHeader(context),
        const SizedBox(height: AppConstants.paddingM),
        AnimatedCrossFade(
          duration: const Duration(milliseconds: 300),
          crossFadeState: _isExpanded 
              ? CrossFadeState.showSecond 
              : CrossFadeState.showFirst,
          firstChild: _buildCollapsedView(context),
          secondChild: _buildExpandedView(context),
        ),
      ],
    );
  }

  Widget _buildLoadingState() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          height: 100,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
          ),
          child: Center(
            child: CircularProgressIndicator(
              color: Colors.white.withValues(alpha: 0.7),
              strokeWidth: 2,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    final path = _learningPath!;
    final completedCount = path.modules.where((m) => m.isCompleted).length;
    final progress = path.modules.isEmpty 
        ? 0.0 
        : completedCount / path.modules.length;

    return GestureDetector(
      onTap: () => setState(() => _isExpanded = !_isExpanded),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF6366F1).withValues(alpha: 0.4),
                  const Color(0xFF8B5CF6).withValues(alpha: 0.25),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: const Color(0xFF6366F1).withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
                    ),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Center(
                    child: Icon(Icons.route_rounded, color: Colors.white, size: 24),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            'Learning Path',
                            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              '${(progress * 100).toInt()}%',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      // Progress bar
                      Stack(
                        children: [
                          Container(
                            height: 6,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(3),
                            ),
                          ),
                          FractionallySizedBox(
                            widthFactor: progress.clamp(0.0, 1.0),
                            child: Container(
                              height: 6,
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(3),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '$completedCount of ${path.modules.length} days completed',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.white.withValues(alpha: 0.8),
                        ),
                      ),
                    ],
                  ),
                ),
                AnimatedRotation(
                  duration: const Duration(milliseconds: 200),
                  turns: _isExpanded ? 0.5 : 0,
                  child: Icon(
                    Icons.keyboard_arrow_down,
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCollapsedView(BuildContext context) {
    final path = _learningPath!;
    
    // Find next unlocked, incomplete module
    final nextModule = path.modules.firstWhere(
      (m) => m.isUnlocked && !m.isCompleted,
      orElse: () => path.modules.first,
    );
    final dayNumber = path.modules.indexOf(nextModule) + 1;

    return GestureDetector(
      onTap: () => _startModule(nextModule, dayNumber),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withValues(alpha: 0.2)),
            ),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        'Day',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.8),
                          fontSize: 9,
                        ),
                      ),
                      Text(
                        '$dayNumber',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        nextModule.title,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(
                            Icons.timer_outlined,
                            size: 12,
                            color: Colors.white.withValues(alpha: 0.7),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            '${nextModule.estimatedMinutes} min',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Colors.white.withValues(alpha: 0.7),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.play_arrow, color: Colors.white, size: 18),
                      const SizedBox(width: 4),
                      Text(
                        nextModule.isCompleted ? 'Review' : 'Start',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
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

  Widget _buildExpandedView(BuildContext context) {
    final path = _learningPath!;
    
    // Group modules by week
    final weeks = <List<LearningModule>>[];
    for (int i = 0; i < path.modules.length; i += 7) {
      final end = (i + 7).clamp(0, path.modules.length);
      weeks.add(path.modules.sublist(i, end));
    }

    return Column(
      children: [
        // Week selector
        if (weeks.length > 1) _buildWeekSelector(weeks),
        const SizedBox(height: 12),
        
        // Module list for selected week
        _buildWeekModules(
          context, 
          weeks.isNotEmpty ? weeks[_selectedWeek.clamp(0, weeks.length - 1)] : [],
          _selectedWeek * 7,
        ),
      ],
    );
  }

  Widget _buildWeekSelector(List<List<LearningModule>> weeks) {
    return SizedBox(
      height: 40,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: weeks.length,
        itemBuilder: (context, index) {
          final isSelected = index == _selectedWeek;
          final weekCompleted = weeks[index].every((m) => m.isCompleted);

          return GestureDetector(
            onTap: () => setState(() => _selectedWeek = index),
            child: Container(
              margin: const EdgeInsets.only(right: 10),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                gradient: isSelected ? AppTheme.primaryGradient : null,
                color: isSelected ? null : Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isSelected 
                      ? Colors.transparent 
                      : Colors.white.withValues(alpha: 0.2),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (weekCompleted)
                    Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: Icon(
                        Icons.check_circle,
                        size: 14,
                        color: isSelected ? Colors.white : Colors.green,
                      ),
                    ),
                  Text(
                    'Week ${index + 1}',
                    style: TextStyle(
                      color: isSelected 
                          ? Colors.white 
                          : Colors.white.withValues(alpha: 0.8),
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildWeekModules(
    BuildContext context, 
    List<LearningModule> modules,
    int weekStartIndex,
  ) {
    if (modules.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Center(
          child: Text(
            'No modules for this week',
            style: TextStyle(color: Colors.white.withValues(alpha: 0.7)),
          ),
        ),
      );
    }

    // Find current day index
    int currentDayIndex = 0;
    final path = _learningPath!;
    for (int i = 0; i < path.modules.length; i++) {
      if (!path.modules[i].isCompleted && path.modules[i].isUnlocked) {
        currentDayIndex = i;
        break;
      }
    }

    return Column(
      children: modules.asMap().entries.map((entry) {
        final index = entry.key;
        final module = entry.value;
        final dayNumber = weekStartIndex + index + 1;
        final isCurrentDay = weekStartIndex + index == currentDayIndex;

        return _buildModuleCard(context, module, dayNumber, isCurrentDay);
      }).toList(),
    );
  }

  Widget _buildModuleCard(
    BuildContext context,
    LearningModule module,
    int dayNumber,
    bool isCurrentDay,
  ) {
    final isLocked = !module.isUnlocked;
    final isCompleted = module.isCompleted;

    Color statusColor;
    IconData statusIcon;
    if (isCompleted) {
      statusColor = Colors.green;
      statusIcon = Icons.check_circle_rounded;
    } else if (isCurrentDay && !isLocked) {
      statusColor = AppTheme.primaryColor;
      statusIcon = Icons.play_circle_filled_rounded;
    } else if (isLocked) {
      statusColor = Colors.grey;
      statusIcon = Icons.lock_rounded;
    } else {
      statusColor = Colors.orange;
      statusIcon = Icons.radio_button_unchecked_rounded;
    }

    return GestureDetector(
      onTap: isLocked ? null : () => _startModule(module, dayNumber),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isLocked 
                    ? Colors.grey.withValues(alpha: 0.15) 
                    : Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
                border: isCurrentDay && !isLocked
                    ? Border.all(color: AppTheme.primaryColor, width: 2)
                    : Border.all(color: Colors.white.withValues(alpha: 0.15)),
              ),
              child: Row(
                children: [
                  // Day indicator
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      gradient: isLocked
                          ? null
                          : isCompleted
                              ? const LinearGradient(colors: [Colors.green, Colors.teal])
                              : AppTheme.primaryGradient,
                      color: isLocked ? Colors.grey.withValues(alpha: 0.3) : null,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'Day',
                          style: TextStyle(
                            color: isLocked 
                                ? Colors.grey 
                                : Colors.white.withValues(alpha: 0.8),
                            fontSize: 9,
                          ),
                        ),
                        Text(
                          '$dayNumber',
                          style: TextStyle(
                            color: isLocked ? Colors.grey : Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          module.title,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: isLocked ? Colors.grey : Colors.white,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(
                              Icons.timer_outlined,
                              size: 12,
                              color: isLocked 
                                  ? Colors.grey.withValues(alpha: 0.5) 
                                  : Colors.white.withValues(alpha: 0.6),
                            ),
                            const SizedBox(width: 4),
                            Text(
                              '${module.estimatedMinutes} min',
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: isLocked 
                                    ? Colors.grey.withValues(alpha: 0.5) 
                                    : Colors.white.withValues(alpha: 0.6),
                              ),
                            ),
                            if (!isLocked && module.progressPercentage > 0) ...[
                              const SizedBox(width: 10),
                              Container(
                                width: 50,
                                height: 4,
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.2),
                                  borderRadius: BorderRadius.circular(2),
                                ),
                                child: FractionallySizedBox(
                                  alignment: Alignment.centerLeft,
                                  widthFactor: (module.progressPercentage / 100).clamp(0.0, 1.0),
                                  child: Container(
                                    decoration: BoxDecoration(
                                      color: AppTheme.primaryColor,
                                      borderRadius: BorderRadius.circular(2),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ],
                    ),
                  ),
                  Icon(statusIcon, color: statusColor, size: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _startModule(LearningModule module, int dayNumber) async {
    if (!module.isUnlocked) return;

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => LessonLoadingScreen(
          moduleId: module.id,
          dayNumber: dayNumber,
        ),
      ),
    );

    // Refresh after returning
    if (mounted) {
      _loadLearningPath();
      widget.onModuleCompleted?.call();
    }
  }
}






