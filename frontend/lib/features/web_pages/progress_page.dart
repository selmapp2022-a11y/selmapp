import 'package:flutter/material.dart';
import '../../../core/network/api_client.dart';
import '../../../core/di/injection_container.dart' as di;
import '../../../core/services/progress_service.dart';
import '_shared.dart';

class ProgressPageV2 extends StatefulWidget {
  const ProgressPageV2({super.key});
  @override
  State<ProgressPageV2> createState() => _ProgressPageV2State();
}

class _ProgressPageV2State extends State<ProgressPageV2> {
  late final ApiClient _api = di.sl<ApiClient>();
  ProgressSummary? _summary;
  List<Map<String, dynamic>> _ach = [];
  Map<String, dynamic>? _weekly;

  @override
  void initState() {
    super.initState();
    _load();
    _loadWeekly();
    ProgressService.instance.addListener(_onP);
  }

  @override
  void dispose() {
    ProgressService.instance.removeListener(_onP);
    super.dispose();
  }

  void _onP(_) { _load(); _loadWeekly(); }

  Future<void> _load() async {
    final s = await ProgressService.instance.getSummary();
    final a = await ProgressService.instance.getAchievements();
    if (mounted) setState(() { _summary = s; _ach = a; });
  }

  Future<void> _loadWeekly() async {
    try {
      final r = await _api.get('/progress/weekly-summary');
      if (mounted && r.data is Map) setState(() => _weekly = Map<String, dynamic>.from(r.data));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBg,
      appBar: pageAppBar(context, 'Progress'),
      body: SafeArea(child: _summary == null
        ? const Center(child: CircularProgressIndicator(color: kAccent))
        : SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              _topCard(_summary!),
              if (_weekly != null) ...[
                const SizedBox(height: 16),
                _weeklyCard(_weekly!),
              ],
              const SizedBox(height: 16),
              _skillsCard(_summary!),
              const SizedBox(height: 16),
              _achCard(),
              const SizedBox(height: 24),
            ]),
          )),
    );
  }

  Widget _topCard(ProgressSummary s) {
    final pct = (s.xpThisLevel / 200).clamp(0.0, 1.0);
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Level ${s.level}', style: const TextStyle(color: kInk, fontSize: 24, fontWeight: FontWeight.w800)),
          Text('${s.totalXP} XP total', style: const TextStyle(color: kMuted, fontSize: 13)),
        ])),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(color: kAccent.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(20)),
            child: Text('🔥 ${s.streak} day${s.streak == 1 ? '' : 's'}',
              style: const TextStyle(color: kAccent, fontSize: 14, fontWeight: FontWeight.w700))),
          const SizedBox(height: 4),
          Text('Best streak: ${s.longestStreak}', style: const TextStyle(color: kMuted, fontSize: 11)),
        ]),
      ]),
      const SizedBox(height: 12),
      ClipRRect(borderRadius: BorderRadius.circular(4),
        child: LinearProgressIndicator(value: pct, minHeight: 10,
          backgroundColor: const Color(0xFFE2E8F0), valueColor: const AlwaysStoppedAnimation(kAccent))),
      const SizedBox(height: 6),
      Text('${s.xpToNext} XP to level ${s.level + 1}', style: const TextStyle(color: kMuted, fontSize: 12)),
      const SizedBox(height: 12),
      Row(children: [
        Expanded(child: _stat('${s.totalExercises}', 'Exercises')),
        Expanded(child: _stat('${s.perfectCount}', 'Perfect')),
        Expanded(child: _stat('${_ach.where((a) => a['unlocked'] == true).length}', 'Achievements')),
      ]),
    ]));
  }

  Widget _stat(String value, String label) => Column(children: [
    Text(value, style: const TextStyle(color: kAccent, fontSize: 22, fontWeight: FontWeight.w800)),
    Text(label, style: const TextStyle(color: kMuted, fontSize: 11)),
  ]);

  Widget _skillsCard(ProgressSummary s) {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Skills', style: TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w800)),
      const SizedBox(height: 12),
      ..._skillRow('🎧 Listening', s.bySkill[SkillKey.listening]!),
      ..._skillRow('📖 Reading', s.bySkill[SkillKey.reading]!),
      ..._skillRow('🎤 Speaking', s.bySkill[SkillKey.speaking]!),
      ..._skillRow('✍️ Writing', s.bySkill[SkillKey.writing]!),
      ..._skillRow('💡 Vocabulary', s.bySkill[SkillKey.vocabulary]!),
    ]));
  }

  List<Widget> _skillRow(String label, SkillStats s) {
    final pct = (s.xpThisLevel / 120).clamp(0.0, 1.0);
    return [
      Padding(padding: const EdgeInsets.only(bottom: 12), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Expanded(child: Text(label, style: const TextStyle(color: kInk, fontWeight: FontWeight.w700))),
          Text('Lv ${s.level} · ${s.tier}', style: const TextStyle(color: kAccent, fontWeight: FontWeight.w700, fontSize: 12)),
        ]),
        const SizedBox(height: 6),
        ClipRRect(borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(value: pct, minHeight: 6,
            backgroundColor: const Color(0xFFE2E8F0), valueColor: const AlwaysStoppedAnimation(kAccent))),
        const SizedBox(height: 4),
        Row(children: [
          Text('${s.count} session${s.count == 1 ? '' : 's'}', style: const TextStyle(color: kMuted, fontSize: 11)),
          const Spacer(),
          if (s.bestPct != null) Text('Best ${s.bestPct!.round()}%', style: const TextStyle(color: kMuted, fontSize: 11)),
        ]),
      ])),
    ];
  }

  Widget _weeklyCard(Map<String, dynamic> w) {
    final days = (w['days'] as List? ?? []).whereType<Map>().map((d) => Map<String, dynamic>.from(d)).toList();
    final totals = (w['totals'] is Map ? Map<String, dynamic>.from(w['totals']) : <String, dynamic>{});
    final trend = (w['trend_vs_previous_week'] is Map ? Map<String, dynamic>.from(w['trend_vs_previous_week']) : <String, dynamic>{});
    final best = (w['best_day'] is Map ? Map<String, dynamic>.from(w['best_day']) : null);
    final goalMin = (w['daily_goal_minutes'] as num?)?.toInt() ?? 0;
    final maxMin = days.fold<int>(0, (a, d) {
      final m = (d['minutes'] as num?)?.toInt() ?? 0;
      return m > a ? m : a;
    });
    final scaleMax = [maxMin, goalMin, 10].reduce((a, b) => a > b ? a : b);
    final deltaPct = trend['minutes_change_percent'];
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        const Expanded(child: Text('This week', style: TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w800))),
        if (deltaPct is num) Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: deltaPct >= 0 ? const Color(0xFFD1FAE5) : const Color(0xFFFEE2E2),
            borderRadius: BorderRadius.circular(10)),
          child: Text('${deltaPct >= 0 ? '↑' : '↓'} ${deltaPct.abs().toStringAsFixed(0)}% vs last week',
              style: TextStyle(color: deltaPct >= 0 ? const Color(0xFF047857) : const Color(0xFFB91C1C),
                  fontSize: 11, fontWeight: FontWeight.w800)),
        ),
      ]),
      const SizedBox(height: 14),
      SizedBox(
        height: 110,
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: days.map((d) {
          final m = (d['minutes'] as num?)?.toInt() ?? 0;
          final met = d['goal_met'] == true;
          final h = scaleMax > 0 ? (m / scaleMax * 80).clamp(2.0, 80.0) : 2.0;
          final wd = (d['weekday'] as String? ?? '').substring(0, 1).toUpperCase();
          return Expanded(child: Padding(padding: const EdgeInsets.symmetric(horizontal: 2),
            child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
              Text('${m}m', style: TextStyle(color: m > 0 ? kInk : kMuted, fontSize: 9, fontWeight: FontWeight.w700)),
              const SizedBox(height: 2),
              Container(height: h.toDouble(),
                decoration: BoxDecoration(
                  color: met ? kAccent : (m > 0 ? kAccent.withValues(alpha: 0.4) : const Color(0xFFE2E8F0)),
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(4)))),
              const SizedBox(height: 4),
              Text(wd, style: const TextStyle(color: kMuted, fontSize: 11, fontWeight: FontWeight.w600)),
            ])));
        }).toList()),
      ),
      const SizedBox(height: 12),
      Row(children: [
        Expanded(child: _stat('${totals['minutes'] ?? 0}m', 'Minutes')),
        Expanded(child: _stat('${totals['exercises'] ?? 0}', 'Exercises')),
        Expanded(child: _stat('${totals['goal_met_days'] ?? 0}/7', 'Goal hit')),
      ]),
      if (best != null && (best['minutes'] as num?) != null && (best['minutes'] as num) > 0) ...[
        const SizedBox(height: 8),
        Center(child: Text('🏆 Best day: ${best['weekday']} (${best['minutes']}m)',
            style: const TextStyle(color: kMuted, fontSize: 12))),
      ],
    ]));
  }

  Widget _achCard() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        const Expanded(child: Text('Achievements', style: TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w800))),
        Text('${_ach.where((a) => a['unlocked'] == true).length} / ${_ach.length}',
          style: const TextStyle(color: kMuted, fontWeight: FontWeight.w700)),
      ]),
      const SizedBox(height: 12),
      ..._ach.map((a) {
        final unlocked = a['unlocked'] == true;
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: unlocked ? const Color(0xFFF1FAF8) : const Color(0xFFF8FAFC),
            borderRadius: BorderRadius.circular(12),
            border: unlocked ? const Border(left: BorderSide(color: kAccent, width: 3)) : null,
          ),
          child: Row(children: [
            Text(a['emoji'] as String, style: TextStyle(fontSize: 28, color: unlocked ? null : kMuted)),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(a['title'] as String, style: TextStyle(color: unlocked ? kInk : kMuted, fontWeight: FontWeight.w800, fontSize: 13)),
              Text(a['desc'] as String, style: TextStyle(color: unlocked ? kMuted : const Color(0xFFB7C6D6), fontSize: 11)),
            ])),
            if (unlocked) const Icon(Icons.check_circle, color: kAccent, size: 20),
          ]),
        );
      }),
    ]));
  }
}
