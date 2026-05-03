import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

enum SkillKey { listening, reading, speaking, writing, vocabulary }

String skillKeyToStr(SkillKey k) => k.name;
SkillKey? skillKeyFromStr(String s) {
  for (final k in SkillKey.values) {
    if (k.name == s) return k;
  }
  return null;
}

class ProgressEvent {
  final SkillKey skill;
  final String? topic;
  final int? score;
  final int? total;
  final int xp;
  final int ts;
  ProgressEvent({required this.skill, this.topic, this.score, this.total, required this.xp, required this.ts});
  Map<String, dynamic> toJson() => {
        'skill': skill.name,
        if (topic != null) 'topic': topic,
        if (score != null) 'score': score,
        if (total != null) 'total': total,
        'xp': xp,
        'ts': ts,
      };
  static ProgressEvent? fromJson(Map<String, dynamic> j) {
    final sk = skillKeyFromStr((j['skill'] ?? '').toString());
    if (sk == null) return null;
    return ProgressEvent(
      skill: sk,
      topic: j['topic']?.toString(),
      score: (j['score'] as num?)?.toInt(),
      total: (j['total'] as num?)?.toInt(),
      xp: (j['xp'] as num?)?.toInt() ?? 0,
      ts: (j['ts'] as num?)?.toInt() ?? 0,
    );
  }
}

class SkillStats {
  int count = 0;
  int xp = 0;
  int level = 1;
  int xpThisLevel = 0;
  int xpToNext = 120;
  double? bestPct;
  int? lastTs;
  String tier = 'Beginner';
}

class ProgressSummary {
  int totalXP = 0;
  int level = 1;
  int xpThisLevel = 0;
  int xpToNext = 200;
  int streak = 0;
  int longestStreak = 0;
  int totalExercises = 0;
  int perfectCount = 0;
  Map<SkillKey, SkillStats> bySkill = {
    for (final k in SkillKey.values) k: SkillStats(),
  };
}

class ProgressService {
  static const _key = 'selm_progress_v1';
  static const _achKey = 'selm_achievements_v1';
  static const _xpPerLevel = 200;
  static const _xpPerSkillLevel = 120;
  static const _tiers = ['Beginner','Apprentice','Learner','Practiced','Confident','Skilled','Advanced','Proficient','Expert','Master'];

  static final ProgressService instance = ProgressService._();
  ProgressService._();

  final List<void Function(ProgressEvent ev)> _listeners = [];
  void addListener(void Function(ProgressEvent ev) cb) => _listeners.add(cb);
  void removeListener(void Function(ProgressEvent ev) cb) => _listeners.remove(cb);

  Future<List<ProgressEvent>> _read() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_key);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list
          .whereType<Map>()
          .map((m) => ProgressEvent.fromJson(Map<String, dynamic>.from(m)))
          .whereType<ProgressEvent>()
          .toList();
    } catch (_) { return []; }
  }

  Future<void> _write(List<ProgressEvent> list) async {
    final p = await SharedPreferences.getInstance();
    if (list.length > 500) list = list.sublist(list.length - 500);
    await p.setString(_key, jsonEncode(list.map((e) => e.toJson()).toList()));
  }

  Future<Map<String, int>> _readAch() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_achKey);
    if (raw == null || raw.isEmpty) return {};
    try {
      final m = jsonDecode(raw) as Map;
      return m.map((k, v) => MapEntry(k.toString(), (v as num).toInt()));
    } catch (_) { return {}; }
  }

  Future<void> _writeAch(Map<String, int> m) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_achKey, jsonEncode(m));
  }

  int xpFor(SkillKey skill, {int? score, int? total}) {
    var xp = 20;
    if (score != null && total != null && total > 0) {
      xp += score * 6;
      if (score == total) xp += 20;
    } else if (score != null) {
      xp += (score * 0.5).round();
    }
    if (skill == SkillKey.speaking || skill == SkillKey.writing) xp += 10;
    return xp;
  }

  Future<ProgressEvent> record({required SkillKey skill, String? topic, int? score, int? total, int? xp}) async {
    final actualXp = xp ?? xpFor(skill, score: score, total: total);
    final ev = ProgressEvent(
      skill: skill, topic: topic, score: score, total: total,
      xp: actualXp, ts: DateTime.now().millisecondsSinceEpoch,
    );
    final list = await _read();
    list.add(ev);
    await _write(list);
    await evaluateAchievements();
    for (final cb in [..._listeners]) {
      try { cb(ev); } catch (_) {}
    }
    return ev;
  }

  Future<ProgressSummary> getSummary() async {
    final list = await _read();
    final sum = ProgressSummary();
    for (final e in list) {
      sum.totalXP += e.xp;
      final s = sum.bySkill[e.skill]!;
      s.count += 1;
      s.xp += e.xp;
      s.lastTs = e.ts;
      if (e.score != null && e.total != null && e.total! > 0) {
        final pct = (e.score! / e.total!) * 100;
        s.bestPct = (s.bestPct == null) ? pct : (pct > s.bestPct! ? pct : s.bestPct);
        if (e.score == e.total) sum.perfectCount += 1;
      } else if (e.score != null) {
        final v = e.score!.toDouble();
        s.bestPct = (s.bestPct == null) ? v : (v > s.bestPct! ? v : s.bestPct);
        if (e.score! >= 95) sum.perfectCount += 1;
      }
    }
    for (final s in sum.bySkill.values) {
      s.level = 1 + (s.xp ~/ _xpPerSkillLevel);
      s.xpThisLevel = s.xp - (s.level - 1) * _xpPerSkillLevel;
      s.xpToNext = _xpPerSkillLevel - s.xpThisLevel;
      final idx = (s.level - 1).clamp(0, _tiers.length - 1);
      s.tier = _tiers[idx];
    }
    sum.level = 1 + (sum.totalXP ~/ _xpPerLevel);
    sum.xpThisLevel = sum.totalXP - (sum.level - 1) * _xpPerLevel;
    sum.xpToNext = _xpPerLevel - sum.xpThisLevel;
    sum.totalExercises = list.length;

    final days = <String>{};
    for (final e in list) {
      final d = DateTime.fromMillisecondsSinceEpoch(e.ts);
      days.add('${d.year}-${d.month}-${d.day}');
    }
    var d = DateTime.now();
    String key(DateTime x) => '${x.year}-${x.month}-${x.day}';
    if (!days.contains(key(d))) d = d.subtract(const Duration(days: 1));
    var s = 0;
    while (days.contains(key(d))) { s++; d = d.subtract(const Duration(days: 1)); }
    sum.streak = s;
    final sorted = days.map((k) {
      final parts = k.split('-').map(int.parse).toList();
      return DateTime(parts[0], parts[1], parts[2]).millisecondsSinceEpoch;
    }).toList()
      ..sort();
    var longest = 0; var run = 0; var prev = 0;
    const oneDay = 86400000;
    for (final t in sorted) {
      if (prev != 0 && t - prev == oneDay) { run++; } else { run = 1; }
      if (run > longest) longest = run;
      prev = t;
    }
    sum.longestStreak = longest;
    return sum;
  }

  static const List<Map<String, dynamic>> achievementsDefs = [
    {'id': 'first_step', 'title': 'First Step', 'desc': 'Complete your first exercise', 'emoji': '🎯'},
    {'id': 'level_2', 'title': 'Rising Learner', 'desc': 'Reach overall level 2', 'emoji': '⭐'},
    {'id': 'level_5', 'title': 'Dedicated Student', 'desc': 'Reach overall level 5', 'emoji': '🌟'},
    {'id': 'level_10', 'title': 'English Champion', 'desc': 'Reach overall level 10', 'emoji': '🏆'},
    {'id': 'streak_3', 'title': '3-Day Streak', 'desc': 'Practice 3 days in a row', 'emoji': '🔥'},
    {'id': 'streak_7', 'title': 'Week Warrior', 'desc': 'Practice 7 days in a row', 'emoji': '🔥'},
    {'id': 'streak_30', 'title': 'Monthly Marathon', 'desc': 'Practice 30 days in a row', 'emoji': '💪'},
    {'id': 'sessions_10', 'title': 'Getting Serious', 'desc': 'Complete 10 exercises', 'emoji': '📚'},
    {'id': 'sessions_50', 'title': 'Half Century', 'desc': 'Complete 50 exercises', 'emoji': '🎓'},
    {'id': 'sessions_100', 'title': 'Century Club', 'desc': 'Complete 100 exercises', 'emoji': '💯'},
    {'id': 'perfect_1', 'title': 'Perfectionist', 'desc': 'Get a perfect score', 'emoji': '✨'},
    {'id': 'perfect_10', 'title': 'Flawless Ten', 'desc': 'Get 10 perfect scores', 'emoji': '👑'},
    {'id': 'speak_lv3', 'title': 'Speaking · Confident', 'desc': 'Reach Speaking level 3', 'emoji': '🎤'},
    {'id': 'listen_lv3', 'title': 'Listening · Confident', 'desc': 'Reach Listening level 3', 'emoji': '🎧'},
    {'id': 'read_lv3', 'title': 'Reading · Confident', 'desc': 'Reach Reading level 3', 'emoji': '📖'},
    {'id': 'write_lv3', 'title': 'Writing · Confident', 'desc': 'Reach Writing level 3', 'emoji': '✍️'},
    {'id': 'all_four', 'title': 'Well-Rounded', 'desc': 'Practice all 4 main skills', 'emoji': '🌈'},
    {'id': 'all_lv2', 'title': 'Balanced Learner', 'desc': 'Reach level 2 in every main skill', 'emoji': '⚖️'},
  ];

  bool _test(String id, ProgressSummary s) {
    switch (id) {
      case 'first_step': return s.totalExercises >= 1;
      case 'level_2': return s.level >= 2;
      case 'level_5': return s.level >= 5;
      case 'level_10': return s.level >= 10;
      case 'streak_3': return s.longestStreak >= 3 || s.streak >= 3;
      case 'streak_7': return s.longestStreak >= 7 || s.streak >= 7;
      case 'streak_30': return s.longestStreak >= 30 || s.streak >= 30;
      case 'sessions_10': return s.totalExercises >= 10;
      case 'sessions_50': return s.totalExercises >= 50;
      case 'sessions_100': return s.totalExercises >= 100;
      case 'perfect_1': return s.perfectCount >= 1;
      case 'perfect_10': return s.perfectCount >= 10;
      case 'speak_lv3': return s.bySkill[SkillKey.speaking]!.level >= 3;
      case 'listen_lv3': return s.bySkill[SkillKey.listening]!.level >= 3;
      case 'read_lv3': return s.bySkill[SkillKey.reading]!.level >= 3;
      case 'write_lv3': return s.bySkill[SkillKey.writing]!.level >= 3;
      case 'all_four':
        return [SkillKey.speaking, SkillKey.listening, SkillKey.reading, SkillKey.writing]
            .every((k) => s.bySkill[k]!.count >= 1);
      case 'all_lv2':
        return [SkillKey.speaking, SkillKey.listening, SkillKey.reading, SkillKey.writing]
            .every((k) => s.bySkill[k]!.level >= 2);
    }
    return false;
  }

  Future<List<Map<String, dynamic>>> getAchievements() async {
    final unlocked = await _readAch();
    final s = await getSummary();
    return achievementsDefs.map((a) {
      final id = a['id'] as String;
      return {
        ...a,
        'unlocked': unlocked.containsKey(id),
        'unlockedAt': unlocked[id],
        'eligible': _test(id, s),
      };
    }).toList();
  }

  Future<List<String>> evaluateAchievements() async {
    final unlocked = await _readAch();
    final s = await getSummary();
    final newly = <String>[];
    for (final a in achievementsDefs) {
      final id = a['id'] as String;
      if (!unlocked.containsKey(id) && _test(id, s)) {
        unlocked[id] = DateTime.now().millisecondsSinceEpoch;
        newly.add(id);
      }
    }
    if (newly.isNotEmpty) await _writeAch(unlocked);
    return newly;
  }
}
