import 'package:flutter/material.dart';
import '../../../core/network/api_client.dart';
import '../../../core/di/injection_container.dart' as di;
import '../../../core/services/progress_service.dart';
import '_shared.dart';

class ReadingPage extends StatefulWidget {
  const ReadingPage({super.key});
  @override
  State<ReadingPage> createState() => _ReadingPageState();
}

class _RQ {
  final String question;
  final List<String> options;
  final String correct;
  final String? explanation;
  _RQ(this.question, this.options, this.correct, this.explanation);
}

class _Vocab {
  final String word;
  final String definition;
  final String? example;
  _Vocab(this.word, this.definition, this.example);
}

class _ReadingPageState extends State<ReadingPage> {
  late final ApiClient _api = di.sl<ApiClient>();
  String _level = 'B1';
  String? _topic;
  final _customTopic = TextEditingController();
  bool _loading = false;
  String? _error;
  String? _title;
  String _content = '';
  List<_Vocab> _vocab = [];
  List<_RQ> _questions = [];
  Map<int, String> _answers = {};
  bool _showResults = false;
  _Vocab? _hoverVocab;

  @override
  void dispose() { _customTopic.dispose(); super.dispose(); }

  Future<void> _generate() async {
    final t = (_customTopic.text.trim().isEmpty ? _topic : _customTopic.text.trim()) ?? 'Travel';
    setState(() {
      _loading = true; _error = null; _title = null; _content = ''; _vocab = [];
      _questions = []; _answers = {}; _showResults = false; _hoverVocab = null;
    });
    try {
      final r = await _api.post('/ai/reading/generate-text', data: {
        'topic': t, 'level': _level, 'text_type': 'article',
        'word_count': 250, 'vocabulary_count': 8, 'include_questions': true,
      });
      _normalize(r.data, t);
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = 'Could not generate. Try again.'; });
    }
  }

  void _normalize(dynamic raw, String topic) {
    Map body = raw is Map ? Map.from(raw) : {};
    if (body['reading_text'] is Map) body = Map.from(body['reading_text']);
    else if (body['text'] is Map) body = Map.from(body['text']);
    final c = body['content'];
    if (c is String && c.contains('```')) {
      final p = parseAIContent(body); if (p != null) body = p;
    }
    final content = (body['text_content'] ?? body['text'] ?? body['content'] ?? body['passage'] ?? body['body'] ?? '').toString();
    var title = (body['title'] ?? body['topic'] ?? '').toString();
    if (title.isEmpty) {
      final m = RegExp(r'^\s*#{1,6}\s*(.+?)\s*$', multiLine: true).firstMatch(content);
      title = m?.group(1) ?? 'Reading passage';
    }
    final vocab = ((body['vocabulary_used'] ?? body['vocabulary'] ?? body['key_words'] ?? []) as List).whereType<Object>().map((v) {
      if (v is String) return _Vocab(v, '', null);
      if (v is Map) {
        final m = Map<String, dynamic>.from(v);
        return _Vocab((m['word'] ?? m['term'] ?? '').toString(), (m['definition'] ?? m['meaning'] ?? '').toString(), m['example']?.toString());
      }
      return _Vocab(v.toString(), '', null);
    }).where((v) => v.word.isNotEmpty).toList();
    final qs = ((body['comprehension_questions'] ?? body['questions'] ?? []) as List).whereType<Map>().map((q) {
      final m = Map<String, dynamic>.from(q);
      return _RQ(
        (m['question'] ?? m['text'] ?? '').toString(),
        ((m['options'] ?? m['choices'] ?? []) as List).map((e) => e.toString()).toList(),
        (m['correct_answer'] ?? m['answer'] ?? '').toString(),
        m['explanation']?.toString(),
      );
    }).toList();
    if (mounted) setState(() {
      _title = title.isNotEmpty ? title : '$topic — reading';
      _content = content;
      _vocab = vocab;
      _questions = qs;
      _loading = false;
    });
  }

  void _submit() {
    var correct = 0;
    for (var i = 0; i < _questions.length; i++) {
      if ((_answers[i] ?? '').trim().toLowerCase() == _questions[i].correct.trim().toLowerCase()) correct++;
    }
    setState(() => _showResults = true);
    ProgressService.instance.record(skill: SkillKey.reading, topic: _title, score: correct, total: _questions.length);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBg,
      appBar: pageAppBar(context, 'Reading'),
      body: SafeArea(child: SingleChildScrollView(padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (_questions.isEmpty && _content.isEmpty) _setup(),
          if (_loading) const Padding(padding: EdgeInsets.symmetric(vertical: 40), child: Center(child: CircularProgressIndicator(color: kAccent))),
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: whiteCard(child: Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFB91C1C), fontWeight: FontWeight.w600)))),
          if (_content.isNotEmpty) ...[
            _passageCard(),
            const SizedBox(height: 12),
            if (_vocab.isNotEmpty) _vocabCard(),
            if (_vocab.isNotEmpty) const SizedBox(height: 12),
            if (_questions.isNotEmpty) _questionsCard(),
            if (_questions.isNotEmpty) const SizedBox(height: 12),
            if (_questions.isNotEmpty && !_showResults) primaryButton(label: 'Submit answers', onPressed: _answers.length == _questions.length ? _submit : null),
            if (_showResults) _results(),
            const SizedBox(height: 12),
            TextButton(onPressed: () => setState(() { _content = ''; _questions = []; _vocab = []; }), child: const Text('Pick another topic', style: TextStyle(color: Colors.white))),
          ],
        ]),
      )),
    );
  }

  Widget _setup() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Pick a topic', style: TextStyle(color: kInk, fontSize: 18, fontWeight: FontWeight.w800)),
      const SizedBox(height: 14),
      topicChips(_topic, (t) => setState(() { _topic = t; _customTopic.clear(); })),
      const SizedBox(height: 14),
      TextField(controller: _customTopic,
        decoration: InputDecoration(hintText: 'or type your own topic…',
          filled: true, fillColor: const Color(0xFFF1F5F9),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12)),
        onChanged: (_) => setState(() { _topic = null; })),
      const SizedBox(height: 14),
      const Text('Level', style: TextStyle(color: kInk, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      levelChips(_level, (v) => setState(() => _level = v)),
      const SizedBox(height: 18),
      primaryButton(label: 'Generate text', icon: Icons.menu_book, onPressed: _generate, loading: _loading),
    ]));
  }

  Widget _passageCard() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(_title ?? '', style: const TextStyle(color: kInk, fontSize: 20, fontWeight: FontWeight.w800)),
      const SizedBox(height: 12),
      Text(_content, style: const TextStyle(color: kInk, fontSize: 15, height: 1.55)),
    ]));
  }

  Widget _vocabCard() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Key vocabulary', style: TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w800)),
      const SizedBox(height: 12),
      Wrap(spacing: 8, runSpacing: 8, children: _vocab.map((v) {
        final sel = _hoverVocab == v;
        return GestureDetector(
          onTap: () => setState(() => _hoverVocab = sel ? null : v),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(color: sel ? kAccent : kAccent.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(16)),
            child: Text(v.word, style: TextStyle(color: sel ? Colors.white : kAccent, fontWeight: FontWeight.w700, fontSize: 13)),
          ),
        );
      }).toList()),
      if (_hoverVocab != null) ...[
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: const Color(0xFFF1FAF8), borderRadius: BorderRadius.circular(10)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(_hoverVocab!.word, style: const TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w800)),
            if (_hoverVocab!.definition.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(_hoverVocab!.definition, style: const TextStyle(color: kInk, fontSize: 13)),
            ],
            if (_hoverVocab!.example != null && _hoverVocab!.example!.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('"${_hoverVocab!.example!}"', style: const TextStyle(color: kMuted, fontSize: 12, fontStyle: FontStyle.italic)),
            ],
          ]),
        ),
      ],
    ]));
  }

  Widget _questionsCard() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Comprehension', style: TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w800)),
      const SizedBox(height: 12),
      ..._questions.asMap().entries.map((e) {
        final i = e.key; final q = e.value;
        return Padding(padding: const EdgeInsets.only(bottom: 16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('${i + 1}. ${q.question}', style: const TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            if (q.options.isEmpty) TextField(
              decoration: InputDecoration(filled: true, fillColor: const Color(0xFFF1F5F9),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                hintText: 'Type your answer'),
              enabled: !_showResults,
              onChanged: (v) => _answers[i] = v,
            ),
            ...q.options.map((opt) {
              final sel = _answers[i] == opt;
              final isC = opt.trim().toLowerCase() == q.correct.trim().toLowerCase();
              Color bg = Colors.white, border = const Color(0xFFE2E8F0);
              if (_showResults) {
                if (isC) { bg = const Color(0xFFD1FAE5); border = const Color(0xFF10B981); }
                else if (sel) { bg = const Color(0xFFFEE2E2); border = const Color(0xFFEF4444); }
              } else if (sel) { bg = kAccent.withValues(alpha: 0.1); border = kAccent; }
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: GestureDetector(
                  onTap: _showResults ? null : () => setState(() => _answers[i] = opt),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: bg, border: Border.all(color: border, width: 2), borderRadius: BorderRadius.circular(10)),
                    child: Text(opt, style: const TextStyle(color: kInk, fontSize: 13, fontWeight: FontWeight.w500)),
                  ),
                ),
              );
            }),
            if (_showResults && q.explanation != null && q.explanation!.isNotEmpty) Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text('💡 ${q.explanation!}', style: const TextStyle(color: kMuted, fontSize: 12, fontStyle: FontStyle.italic))),
          ]));
      }),
    ]));
  }

  Widget _results() {
    var correct = 0;
    for (var i = 0; i < _questions.length; i++) {
      if ((_answers[i] ?? '').trim().toLowerCase() == _questions[i].correct.trim().toLowerCase()) correct++;
    }
    final pct = _questions.isEmpty ? 0 : (correct * 100 ~/ _questions.length);
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Center(child: Container(padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        decoration: BoxDecoration(color: scoreBg(pct), borderRadius: BorderRadius.circular(20)),
        child: Text('$correct / ${_questions.length}  ($pct%)',
          style: TextStyle(color: scoreFg(pct), fontWeight: FontWeight.w800, fontSize: 18)))),
    ]));
  }
}
