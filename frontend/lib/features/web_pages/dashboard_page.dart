import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/network/api_client.dart';
import '../../../core/di/injection_container.dart' as di;
import '../../../core/services/progress_service.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});
  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  static const Color _bg = Color(0xFF0C1C2C);
  static const Color _accent = Color(0xFF2DD4BF);
  static const Color _muted = Color(0xFF6B7B8C);
  late final ApiClient _api = di.sl<ApiClient>();
  ProgressSummary? _summary;
  Map<String, dynamic>? _today;

  @override
  void initState() {
    super.initState();
    _load();
    _loadToday();
    ProgressService.instance.addListener(_onProgress);
  }

  @override
  void dispose() {
    ProgressService.instance.removeListener(_onProgress);
    super.dispose();
  }

  void _onProgress(_) { _load(); _loadToday(); }

  Future<void> _load() async {
    final s = await ProgressService.instance.getSummary();
    if (mounted) setState(() => _summary = s);
  }

  Future<void> _loadToday() async {
    try {
      final r = await _api.get('/progress/today');
      if (mounted && r.data is Map) setState(() => _today = Map<String, dynamic>.from(r.data));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final s = _summary;
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 8),
              Row(
                children: [
                  const Expanded(
                    child: Text('SELM',
                        style: TextStyle(color: _accent, fontSize: 28, fontWeight: FontWeight.w900, letterSpacing: 2)),
                  ),
                  IconButton(
                    icon: const Icon(Icons.person_outline, color: Colors.white),
                    onPressed: () => context.go('/profile'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text('Welcome back',
                  style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              const Text('Pick a skill to practise.',
                  style: TextStyle(color: _muted, fontSize: 14)),
              const SizedBox(height: 20),
              if (s != null) _xpCard(s),
              if (_today != null) ...[
                const SizedBox(height: 12),
                _todayCard(_today!),
              ],
              const SizedBox(height: 20),
              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.0,
                children: [
                  _skillCard('🎧', 'Listening', 'Audio + Q&A', () => context.go('/listening')),
                  _skillCard('📖', 'Reading', 'Texts + vocab', () => context.go('/reading')),
                  _skillCard('🎤', 'Speaking', 'Record + score', () => context.go('/speaking')),
                  _skillCard('✍️', 'Writing', 'Grammar + score', () => context.go('/writing')),
                ],
              ),
              const SizedBox(height: 12),
              _actionCard('💡', 'Vocabulary review', 'Cards due for review', () => context.go('/vocabulary')),
              const SizedBox(height: 8),
              _actionCard('📈', 'Progress', 'Levels, streak, achievements', () => context.go('/progress')),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _xpCard(ProgressSummary s) {
    final pct = (s.xpThisLevel / 200).clamp(0.0, 1.0);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Level ${s.level}',
                        style: const TextStyle(color: Color(0xFF0C1C2C), fontSize: 22, fontWeight: FontWeight.w800)),
                    Text('${s.totalXP} XP total', style: const TextStyle(color: _muted, fontSize: 13)),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(color: _accent.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(20)),
                child: Text('🔥 ${s.streak}',
                    style: const TextStyle(color: _accent, fontSize: 14, fontWeight: FontWeight.w700)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: pct, minHeight: 8,
              backgroundColor: const Color(0xFFE2E8F0),
              valueColor: const AlwaysStoppedAnimation<Color>(_accent),
            ),
          ),
          const SizedBox(height: 6),
          Text('${s.xpToNext} XP to next level',
              style: const TextStyle(color: _muted, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _todayCard(Map<String, dynamic> t) {
    final goal = (t['daily_goal'] is Map ? Map<String, dynamic>.from(t['daily_goal']) : <String, dynamic>{});
    final streak = (t['streak'] is Map ? Map<String, dynamic>.from(t['streak']) : <String, dynamic>{});
    final vocab = (t['vocabulary'] is Map ? Map<String, dynamic>.from(t['vocabulary']) : <String, dynamic>{});
    final goalMin = (goal['goal_minutes'] as num?)?.toInt() ?? 0;
    final todayMin = (goal['minutes_today'] as num?)?.toInt() ?? 0;
    final pct = ((goal['progress_percentage'] as num?)?.toDouble() ?? 0) / 100;
    final met = goal['goal_met'] == true;
    final due = (vocab['due_reviews'] as num?)?.toInt() ?? 0;
    final serverStreak = (streak['current'] as num?)?.toInt() ?? 0;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Expanded(child: Text("Today's goal",
              style: TextStyle(color: Color(0xFF0C1C2C), fontSize: 15, fontWeight: FontWeight.w800))),
          if (met) Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(color: const Color(0xFFD1FAE5), borderRadius: BorderRadius.circular(10)),
            child: const Text('✓ Met', style: TextStyle(color: Color(0xFF047857), fontSize: 11, fontWeight: FontWeight.w800)),
          ),
        ]),
        const SizedBox(height: 8),
        if (goalMin > 0) ...[
          ClipRRect(borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(value: pct.clamp(0.0, 1.0), minHeight: 6,
              backgroundColor: const Color(0xFFE2E8F0), valueColor: const AlwaysStoppedAnimation<Color>(_accent))),
          const SizedBox(height: 4),
          Text('$todayMin / $goalMin minutes today',
              style: const TextStyle(color: _muted, fontSize: 12)),
        ] else
          const Text('Set a daily goal in your profile to track progress.',
              style: TextStyle(color: _muted, fontSize: 12)),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: _miniStat('🔥', '$serverStreak', 'streak')),
          Expanded(child: _miniStat('💡', '$due', 'words due')),
        ]),
      ]),
    );
  }

  Widget _miniStat(String emoji, String value, String label) => Container(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      Text(emoji, style: const TextStyle(fontSize: 16)),
      const SizedBox(width: 6),
      Text(value, style: const TextStyle(color: Color(0xFF0C1C2C), fontWeight: FontWeight.w800, fontSize: 16)),
      const SizedBox(width: 4),
      Text(label, style: const TextStyle(color: _muted, fontSize: 11)),
    ]),
  );

  Widget _skillCard(String emoji, String title, String desc, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 32)),
            const SizedBox(height: 8),
            Text(title, style: const TextStyle(color: Color(0xFF0C1C2C), fontSize: 16, fontWeight: FontWeight.w800)),
            const SizedBox(height: 2),
            Text(desc, style: const TextStyle(color: _muted, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Widget _actionCard(String emoji, String title, String desc, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)),
        child: Row(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 28)),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(color: Color(0xFF0C1C2C), fontSize: 15, fontWeight: FontWeight.w800)),
                  Text(desc, style: const TextStyle(color: _muted, fontSize: 12)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: _muted),
          ],
        ),
      ),
    );
  }
}
