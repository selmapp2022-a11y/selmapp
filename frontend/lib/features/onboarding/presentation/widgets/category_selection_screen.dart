import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../bloc/onboarding_bloc.dart';
import '../../data/models/onboarding_models.dart';
import '../pages/onboarding_main_page.dart';

class CategorySelectionScreen extends StatefulWidget {
  final CategorySelectionState state;

  const CategorySelectionScreen({
    super.key,
    required this.state,
  });

  @override
  State<CategorySelectionScreen> createState() => _CategorySelectionScreenState();
}

class _CategorySelectionScreenState extends State<CategorySelectionScreen>
    with TickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late List<AnimationController> _cardAnimationControllers;
  late List<Animation<double>> _cardScaleAnimations;

  List<LearningCategory> _selectedCategories = [];
  final int _minCategories = 3;
  final int _maxCategories = 6;

  @override
  void initState() {
    super.initState();
    
    _selectedCategories = List.from(widget.state.selectedCategories);
    
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOut,
    ));

    // Create individual animation controllers for each category card
    _cardAnimationControllers = LearningCategory.values.map((category) {
      return AnimationController(
        duration: const Duration(milliseconds: 200),
        vsync: this,
      );
    }).toList();

    _cardScaleAnimations = _cardAnimationControllers.map((controller) {
      return Tween<double>(
        begin: 1.0,
        end: 0.95,
      ).animate(CurvedAnimation(
        parent: controller,
        curve: Curves.easeInOut,
      ));
    }).toList();

    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    for (var controller in _cardAnimationControllers) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isSelectionValid = _selectedCategories.length >= _minCategories;
    
    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Choose Your Interests',
        showProgress: true,
        progress: 0.3, // 30% through onboarding
        onBackPressed: () async {
          // In this onboarding flow we don't have a Navigator stack (states are swapped
          // by BLoC), so "back" should behave like "exit setup" rather than doing nothing.
          final shouldExit = await showDialog<bool>(
            context: context,
            builder: (dialogContext) => AlertDialog(
              title: const Text('Exit setup?'),
              content: const Text(
                'You can continue onboarding later from your Profile.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(false),
                  child: const Text('Stay'),
                ),
                ElevatedButton(
                  onPressed: () => Navigator.of(dialogContext).pop(true),
                  child: const Text('Go to Profile'),
                ),
              ],
            ),
          );

          if (shouldExit == true && mounted) {
            // ignore: use_build_context_synchronously
            context.go('/profile');
          }
        },
      ),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: Column(
            children: [
              // Header Section
              Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    // Welcome message with user name
                    Text(
                      'Great to meet you, ${widget.state.userName}! 👋',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                    const SizedBox(height: 16),
                    
                    // Instruction text
                    Text(
                      'Select $_minCategories to $_maxCategories topics you\'d like to focus on. This helps us personalize your learning experience.',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Selection counter
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primaryContainer,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            _selectedCategories.length >= _minCategories
                                ? Icons.check_circle
                                : Icons.radio_button_unchecked,
                            size: 16,
                            color: Theme.of(context).colorScheme.primary,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '${_selectedCategories.length} of $_minCategories-$_maxCategories selected',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context).colorScheme.primary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              
              // Categories Grid - Responsive for web
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    // Determine number of columns based on available width
                    // Mobile: 2 columns, Tablet: 3 columns, Desktop: 4 columns
                    final screenWidth = constraints.maxWidth;
                    int crossAxisCount;
                    double maxCardWidth;
                    
                    if (screenWidth >= 1200) {
                      crossAxisCount = 4;
                      maxCardWidth = 280;
                    } else if (screenWidth >= 900) {
                      crossAxisCount = 4;
                      maxCardWidth = 220;
                    } else if (screenWidth >= 600) {
                      crossAxisCount = 3;
                      maxCardWidth = 200;
                    } else {
                      crossAxisCount = 2;
                      maxCardWidth = 180;
                    }
                    
                    // Calculate aspect ratio based on available space
                    // Use taller cards (lower aspect ratio) to accommodate text better
                    final availableWidth = (screenWidth - 48 - (crossAxisCount - 1) * 16) / crossAxisCount;
                    final cardWidth = availableWidth.clamp(140.0, maxCardWidth);
                    final cardHeight = cardWidth * 1.35; // Taller cards for better text fit
                    final aspectRatio = cardWidth / cardHeight;
                    
                    return SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: BoxConstraints(maxWidth: screenWidth >= 1200 ? 1100 : double.infinity),
                          child: GridView.builder(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                              crossAxisCount: crossAxisCount,
                              crossAxisSpacing: 16,
                              mainAxisSpacing: 16,
                              childAspectRatio: aspectRatio,
                            ),
                            itemCount: LearningCategory.values.length,
                            itemBuilder: (context, index) {
                              final category = LearningCategory.values[index];
                              final isSelected = _selectedCategories.contains(category);
                              
                              return TweenAnimationBuilder<double>(
                                duration: Duration(milliseconds: 600 + (index * 100)),
                                tween: Tween<double>(begin: 0.0, end: 1.0),
                                curve: Curves.elasticOut,
                                builder: (context, value, child) {
                                  // Clamp value to ensure it stays within 0.0 to 1.0 range
                                  final clampedValue = value.clamp(0.0, 1.0);
                                  return Transform.translate(
                                    offset: Offset(0, 30 * (1 - clampedValue)),
                                    child: Opacity(
                                      opacity: clampedValue,
                                      child: child,
                                    ),
                                  );
                                },
                                child: _buildCategoryCard(
                                  category,
                                  isSelected,
                                  index,
                                ),
                              );
                            },
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              
              // Continue Button
              Padding(
                padding: const EdgeInsets.all(24),
                child: AnimatedOnboardingButton(
                  text: isSelectionValid 
                      ? 'Continue' 
                      : 'Select ${_minCategories - _selectedCategories.length} more',
                  icon: isSelectionValid ? Icons.arrow_forward : Icons.category,
                  isEnabled: isSelectionValid,
                  onPressed: isSelectionValid ? _continueToNext : null,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCategoryCard(LearningCategory category, bool isSelected, int index) {
    return AnimatedBuilder(
      animation: _cardScaleAnimations[index],
      builder: (context, child) {
        return Transform.scale(
          scale: _cardScaleAnimations[index].value,
          child: GestureDetector(
            onTap: () => _toggleCategory(category, index),
            onTapDown: (_) => _cardAnimationControllers[index].forward(),
            onTapUp: (_) => _cardAnimationControllers[index].reverse(),
            onTapCancel: () => _cardAnimationControllers[index].reverse(),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeInOutCubic,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: isSelected 
                      ? Theme.of(context).colorScheme.primary
                      : Theme.of(context).colorScheme.outline.withValues(alpha:0.3),
                  width: isSelected ? 2 : 1,
                ),
                gradient: isSelected
                    ? LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          Theme.of(context).colorScheme.primary.withValues(alpha:0.1),
                          Theme.of(context).colorScheme.primary.withValues(alpha:0.05),
                        ],
                      )
                    : null,
                color: isSelected 
                    ? null 
                    : Theme.of(context).colorScheme.surface,
                boxShadow: [
                  BoxShadow(
                    color: isSelected 
                        ? Theme.of(context).colorScheme.primary.withValues(alpha:0.2)
                        : Theme.of(context).colorScheme.shadow.withValues(alpha:0.1),
                    blurRadius: isSelected ? 8 : 4,
                    offset: Offset(0, isSelected ? 4 : 2),
                  ),
                ],
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.start,
                  mainAxisSize: MainAxisSize.max,
                  children: [
                    // Selection indicator row
                    SizedBox(
                      height: 20,
                      child: Align(
                        alignment: Alignment.topRight,
                        child: AnimatedScale(
                          scale: isSelected ? 1.0 : 0.0,
                          duration: const Duration(milliseconds: 200),
                          child: Container(
                            width: 20,
                            height: 20,
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.primary,
                              shape: BoxShape.circle,
                            ),
                            child: Icon(
                              Icons.check,
                              size: 14,
                              color: Theme.of(context).colorScheme.onPrimary,
                            ),
                          ),
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: 4),
                    
                    // Category Icon (Emoji) - adaptive size
                    Flexible(
                      flex: 2,
                      child: Container(
                        constraints: const BoxConstraints(
                          minWidth: 40,
                          minHeight: 40,
                          maxWidth: 56,
                          maxHeight: 56,
                        ),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primaryContainer.withValues(alpha:0.3),
                          borderRadius: BorderRadius.circular(28),
                        ),
                        child: Center(
                          child: FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              category.icon,
                              style: const TextStyle(fontSize: 24),
                            ),
                          ),
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: 8),
                    
                    // Category Title - wrapped and scaled to fit
                    Flexible(
                      flex: 1,
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Text(
                          category.title,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                            color: isSelected
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).colorScheme.onSurface,
                          ),
                          textAlign: TextAlign.center,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: 4),
                    
                    // Category Description - limited and scrollable if needed
                    Expanded(
                      flex: 2,
                      child: Text(
                        category.description,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                          height: 1.2,
                          fontSize: 11,
                        ),
                        textAlign: TextAlign.center,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  void _toggleCategory(LearningCategory category, int index) {
    setState(() {
      if (_selectedCategories.contains(category)) {
        // Deselect if already selected
        _selectedCategories.remove(category);
      } else {
        // Select if not selected and within limit
        if (_selectedCategories.length < _maxCategories) {
          _selectedCategories.add(category);
        } else {
          // Show feedback that max limit reached
          _showMaxSelectionFeedback();
          return;
        }
      }
    });

    // Haptic feedback
    // HapticFeedback.lightImpact();

    // Do NOT navigate on tap; proceed only when pressing Continue
  }

  void _showMaxSelectionFeedback() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('You can select up to $_maxCategories categories'),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
      ),
    );
  }

  void _continueToNext() {
    // Move to learning pace selection via BLoC state (no Navigator push)
    context.read<OnboardingBloc>().add(
      SelectCategoriesEvent(_selectedCategories),
    );
  }
}


