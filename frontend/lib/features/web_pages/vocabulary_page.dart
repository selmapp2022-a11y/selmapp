import 'package:flutter/material.dart';
import '../../../core/network/api_client.dart';
import '../../../core/di/injection_container.dart' as di;
import '../../../core/services/progress_service.dart';
import '_shared.dart';

class VocabularyPage extends StatefulWidget {
  const VocabularyPage({super.key});
  @override
  State<VocabularyPage> createState() => _VocabularyPageState();
}

class _VocabWord {
  final int id;
  final String word;
  final String definition;
  final String? example;
  final String? pronunciation;
  final String? pos;
  _VocabWord({required this.id, required this.word, required this.definition, this.example, this.pronunciation, this.pos});
  factory _VocabWord.from(Map<String, dynamic> m) => _VocabWord(
        id: ((m['id'] ?? m['vocabulary_id']) as num?)?.toInt() ?? 0,
        word: (m['word'] ?? m['term'] ?? '').toString(),
        definition: (m['definition'] ?? m['meaning'] ?? '').toString(),
        example: (m['example'] ?? m['sentence'])?.toString(),
        pronunciation: (m['pronunciation'] ?? m['ipa'])?.toString(),
        pos: (m['part_of_speech'] ?? m['pos'])?.toString(),
      );
}

class _VocabularyPageState extends State<VocabularyPage> {
  late final ApiClient _api = di.sl<ApiClient>();
  bool _loading = true;
  String? _error;
  List<_VocabWord> _words = [];
  int _idx = 0;
  bool _flipped = false;
  int _correct = 0;
  int _seen = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final r = await _api.get('/vocabulary/my/review');
      final d = r.data;
      final raw = (d is Map) ? (d['words_to_review'] ?? d['words'] ?? []) : (d is List ? d : []);
      final list = (raw as List).whereType<Map>().map((m) => _VocabWord.from(Map<String, dynamic>.from(m))).where((w) => w.word.isNotEmpty).toList();
      if (mounted) {
        setState(() {
          _words = list;
          _idx = 0;
          _flipped = false;
          _correct = 0;
          _seen = 0;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() { _error = 'Could not load words.'; _loading = false; });
    }
  }

  Future<void> _grade(int q) async {
    final cur = _words[_idx];
    try { await _api.post('/vocabulary/my/words/${cur.id}/progress', data: {'quality_score': q, 'reviewed_at': DateTime.now().toUtc().toIso8601String()}); } catch (_) {}
    setState(() {
      _seen++;
      if (q >= 4) _correct++;
    });
    if (_idx + 1 >= _words.length) {
      await ProgressService.instance.record(skill: SkillKey.vocabulary, score: _correct, total: _seen);
      if (mounted) setState(() => _idx = _words.length);
    } else {
      setState(() { _idx++; _flipped = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBg,
      appBar: pageAppBar(context, 'Vocabulary'),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: _body(),
        ),
      ),
    );
  }

  Widget _body() {
    if (_loading) return const Padding(padding: EdgeInsets.symmetric(vertical: 80), child: Center(child: CircularProgressIndicator(color: kAccent)));
    if (_error != null) return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(_error!, style: const TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w700), textAlign: TextAlign.center),
      const SizedBox(height: 12),
      primaryButton(label: 'Retry', onPressed: _load),
    ]));
    if (_words.isEmpty) return whiteCard(child: const Padding(padding: EdgeInsets.symmetric(vertical: 24),
      child: Column(children: [
        Text('🎉', style: TextStyle(fontSize: 48)),
        SizedBox(height: 8),
        Text('No words due right now.', style: TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w700)),
        SizedBox(height: 4),
        Text('Come back later — your spaced-repetition queue is empty.', style: TextStyle(color: kMuted, fontSize: 13), textAlign: TextAlign.center),
      ]),
    ));
    if (_idx >= _words.length) return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Center(child: Text('🎉', style: TextStyle(fontSize: 56))),
      const SizedBox(height: 8),
      const Center(child: Text('Session complete', style: TextStyle(color: kInk, fontSize: 22, fontWeight: FontWeight.w800))),
      const SizedBox(height: 6),
      Center(child: Text('You remembered $_correct of $_seen', style: const TextStyle(color: kMuted, fontSize: 14))),
      const SizedBox(height: 18),
      primaryButton(label: 'Refresh queue', onPressed: _load),
    ]));

    final cur = _words[_idx];
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text('Word ${_idx + 1} / ${_words.length}', style: const TextStyle(color: Color(0xFFB7C6D6), fontSize: 13, fontWeight: FontWeight.w600)),
        Text('$_correct correct', style: const TextStyle(color: kAccent, fontSize: 13, fontWeight: FontWeight.w700)),
      ]),
      const SizedBox(height: 12),
      ClipRRect(borderRadius: BorderRadius.circular(4), child: LinearProgressIndicator(
        value: (_idx + 1) / _words.length, minHeight: 6,
        backgroundColor: const Color(0xFF1A3346), valueColor: const AlwaysStoppedAnimation(kAccent),
      )),
      const SizedBox(height: 16),
      GestureDetector(
        onTap: () => setState(() => _flipped = !_flipped),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.all(28),
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
          constraints: const BoxConstraints(minHeight: 220),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (!_flipped) ...[
              Center(child: Text(cur.word, style: const TextStyle(color: kInk, fontSize: 34, fontWeight: FontWeight.w800))),
              if (cur.pronunciation != null && cur.pronunciation!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Center(child: Text(cur.pronunciation!, style: const TextStyle(color: kMuted, fontSize: 16, fontStyle: FontStyle.italic))),
              ],
              if (cur.pos != null && cur.pos!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Center(child: Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(12)),
                  child: Text(cur.pos!, style: const TextStyle(color: kMuted, fontSize: 12, fontWeight: FontWeight.w700)),
                )),
              ],
              const SizedBox(height: 16),
              const Center(child: Text('Tap to reveal meaning', style: TextStyle(color: kMuted, fontSize: 12))),
            ] else ...[
              Text(cur.definition, style: const TextStyle(color: kInk, fontSize: 18, fontWeight: FontWeight.w600)),
              if (cur.example != null && cur.example!.isNotEmpty) ...[
                const SizedBox(height: 14),
                Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0xFFF1FAF8), borderRadius: BorderRadius.circular(10),
                  border: const Border(left: BorderSide(color: kAccent, width: 3))),
                  child: Text('"${cur.example!}"', style: const TextStyle(color: kInk, fontSize: 14, fontStyle: FontStyle.italic))),
              ],
            ],
          ]),
        ),
      ),
      const SizedBox(height: 16),
      if (_flipped) ...[
        Row(children: [
          Expanded(child: _gradeBtn('Again', const Color(0xFFEF4444), () => _grade(0))),
          const SizedBox(width: 8),
          Expanded(child: _gradeBtn('Hard', const Color(0xFFF59E0B), () => _grade(2))),
          const SizedBox(width: 8),
          Expanded(child: _gradeBtn('Good', kAccent, () => _grade(4))),
          const SizedBox(width: 8),
          Expanded(child: _gradeBtn('Easy', const Color(0xFF10B981), () => _grade(5))),
        ]),
      ] else
        primaryButton(label: 'Reveal', icon: Icons.visibility, onPressed: () => setState(() => _flipped = true)),
    ]);
  }

  Widget _gradeBtn(String label, Color color, VoidCallback onTap) => GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(12)),
      child: Center(child: Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13))),
    ),
  );
}
