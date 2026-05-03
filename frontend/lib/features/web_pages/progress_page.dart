import 'package:flutter/material.dart';
import '../../../core/services/progress_service.dart';
import '_shared.dart';

class ProgressPageV2 extends StatefulWidget {
  const ProgressPageV2({super.key});
  @override
  State<ProgressPageV2> createState() => _ProgressPageV2State();
}

class _ProgressPageV2State extends State<ProgressPageV2> {
  ProgressSummary? _summary;
  List<Map<String, dynamic>> _ach = [];

  @override
  void initState() {
    super.initState();
    _load();
    ProgressService.instance.addListener(_onP);
  }

  @override
  void dispose() {
    ProgressService.instance.removeListener(_onP);
    super.dispose();
  }

  void _onP(_) => _load();

  Future<void> _load() async {
    final s = await ProgressService.instance.getSummary();
    final a = await ProgressService.instance.getAchievements();
    if (mounted) setState(() { _summary = s; _ach = a; });
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
