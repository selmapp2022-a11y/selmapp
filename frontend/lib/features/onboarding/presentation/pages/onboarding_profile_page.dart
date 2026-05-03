import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

class OnboardingProfilePage extends StatefulWidget {
  const OnboardingProfilePage({super.key});
  @override
  State<OnboardingProfilePage> createState() => _OnboardingProfilePageState();
}

class _OnboardingProfilePageState extends State<OnboardingProfilePage> {
  static const Color _bg = Color(0xFF0C1C2C);
  static const Color _accent = Color(0xFF2DD4BF);
  static const Color _muted = Color(0xFF6B7B8C);

  static const _ages = ['13–17', '18–24', '25–34', '35–44', '45–54', '55+'];
  static const _occs = ['Student', 'Engineer', 'Doctor / Healthcare', 'Business / Finance', 'Teacher', 'Designer', 'Marketing', 'Researcher', 'Other'];
  static const _edus = ['High school', "Bachelor's", "Master's", 'PhD', 'Self-taught'];
  static const _goals = ['Career growth', 'Travel', 'IELTS / TOEFL', 'Academic study', 'Daily conversation', 'Entertainment'];
  static const _interests = ['Tech', 'Business', 'Health', 'Science', 'Arts', 'Sports', 'News', 'Lifestyle', 'Food', 'Music', 'Movies', 'Gaming'];

  int _step = 0;
  String _ageRange = '';
  String _occupation = '';
  String _education = '';
  String _goal = '';
  final List<String> _interestsSel = [];

  late final List<_StepDef> _steps = [
    _StepDef('How old are you?', null, Icons.calendar_today_outlined, _ages, false, () => _ageRange, (v) => setState(() => _ageRange = v)),
    _StepDef('What do you do?', null, Icons.work_outline, _occs, false, () => _occupation, (v) => setState(() => _occupation = v)),
    _StepDef('Your education level?', null, Icons.school_outlined, _edus, false, () => _education, (v) => setState(() => _education = v)),
    _StepDef('Why are you learning English?', null, Icons.flag_outlined, _goals, false, () => _goal, (v) => setState(() => _goal = v)),
    _StepDef('What topics interest you?', 'Pick up to 5 — your lessons will use these contexts.', Icons.favorite_border, _interests, true, () => _interestsSel.join(','), (v) {
      setState(() {
        if (_interestsSel.contains(v)) {
          _interestsSel.remove(v);
        } else if (_interestsSel.length < 5) {
          _interestsSel.add(v);
        }
      });
    }),
  ];

  bool get _answered {
    final s = _steps[_step];
    if (s.multi) return _interestsSel.isNotEmpty;
    return s.getValue().isNotEmpty;
  }

  Future<void> _next() async {
    if (_step < _steps.length - 1) {
      setState(() => _step++);
    } else {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('selm_demographics', jsonEncode({
        'age_range': _ageRange,
        'occupation': _occupation,
        'education': _education,
        'goal': _goal,
        'interests': _interestsSel,
      }));
      if (mounted) context.go('/onboarding/assessment');
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _steps[_step];
    final progress = (_step + 1) / _steps.length;
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Step ${_step + 1} of ${_steps.length}',
                      style: const TextStyle(color: Color(0xFFB7C6D6), fontSize: 13, fontWeight: FontWeight.w500)),
                  const Text('About you',
                      style: TextStyle(color: Color(0xFFB7C6D6), fontSize: 13, fontWeight: FontWeight.w500)),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: progress,
                  minHeight: 8,
                  backgroundColor: const Color(0xFF1A3346),
                  valueColor: const AlwaysStoppedAnimation<Color>(_accent),
                ),
              ),
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.fromLTRB(22, 24, 22, 22),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(children: [
                      Container(
                        width: 48, height: 48,
                        decoration: BoxDecoration(color: _accent.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(14)),
                        child: Icon(s.icon, color: _accent, size: 24),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(s.title,
                                style: const TextStyle(color: Color(0xFF0C1C2C), fontSize: 20, fontWeight: FontWeight.w800)),
                            if (s.subtitle != null) ...[
                              const SizedBox(height: 4),
                              Text(s.subtitle!, style: const TextStyle(color: _muted, fontSize: 13)),
                            ],
                          ],
                        ),
                      ),
                    ]),
                    const SizedBox(height: 20),
                    _buildOptions(s),
                    const SizedBox(height: 20),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        TextButton(
                          onPressed: _step == 0 ? null : () => setState(() => _step--),
                          child: const Text('Back', style: TextStyle(color: _muted, fontWeight: FontWeight.w600)),
                        ),
                        ElevatedButton(
                          onPressed: _answered ? _next : null,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _bg,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            disabledBackgroundColor: const Color(0xFFCBD5E1),
                          ),
                          child: Text(_step < _steps.length - 1 ? 'Continue' : 'Start assessment',
                              style: const TextStyle(fontWeight: FontWeight.w600)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildOptions(_StepDef s) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: s.options.map((opt) {
        final selected = s.multi ? _interestsSel.contains(opt) : s.getValue() == opt;
        return GestureDetector(
          onTap: () => s.setValue(opt),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: selected ? _accent.withValues(alpha: 0.12) : Colors.white,
              border: Border.all(
                color: selected ? _accent : const Color(0xFFE2E8F0),
                width: 2,
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(opt,
                style: TextStyle(
                    color: selected ? const Color(0xFF0C1C2C) : _muted,
                    fontWeight: FontWeight.w600,
                    fontSize: 14)),
          ),
        );
      }).toList(),
    );
  }
}

class _StepDef {
  final String title;
  final String? subtitle;
  final IconData icon;
  final List<String> options;
  final bool multi;
  final String Function() getValue;
  final void Function(String) setValue;
  _StepDef(this.title, this.subtitle, this.icon, this.options, this.multi, this.getValue, this.setValue);
}
