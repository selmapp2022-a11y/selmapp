import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/models/onboarding_models.dart';
import '../../data/repositories/onboarding_repository.dart';
import 'lesson_runner_screen.dart';

class LessonLoadingScreen extends StatefulWidget {
  final String moduleId;
  final int dayNumber;

  const LessonLoadingScreen({super.key, required this.moduleId, this.dayNumber = 1});

  @override
  State<LessonLoadingScreen> createState() => _LessonLoadingScreenState();
}

class _LessonLoadingScreenState extends State<LessonLoadingScreen> {
  String? _error;

  @override
  void initState() {
    super.initState();
    // Kick off loading on next microtask to ensure context is ready
    Future.microtask(_loadSession);
  }

  Future<void> _loadSession() async {
    setState(() => _error = null);
    try {
      final repo = context.read<OnboardingRepository>();
      final LessonSession session = await repo.startLearningSession(
        moduleId: widget.moduleId,
        dayNumber: widget.dayNumber,
      );
      if (!mounted) return;
      // Replace loader with the runner screen
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => LessonRunnerScreen(session: session),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: const Text('Preparing your lesson'),
      ),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 56,
                  height: 56,
                  child: CircularProgressIndicator(
                    strokeWidth: 4,
                    valueColor: AlwaysStoppedAnimation<Color>(theme.colorScheme.primary),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  _error == null
                      ? 'Please wait while we generate AI-powered content for Day ${widget.dayNumber}.'
                      : 'Failed to prepare lesson',
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  _error == null
                      ? 'This may take up to a minute depending on your connection.'
                      : _error!,
                  style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  textAlign: TextAlign.center,
                ),
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      OutlinedButton.icon(
                        onPressed: _loadSession,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                      const SizedBox(width: 12),
                      TextButton(
                        onPressed: () => Navigator.of(context).maybePop(),
                        child: const Text('Cancel'),
                      )
                    ],
                  )
                ]
              ],
            ),
          ),
        ),
      ),
    );
  }
}





















