import 'package:flutter/material.dart';
import '../../../core/network/api_client.dart';
import '../../../core/di/injection_container.dart' as di;
import '../../../core/services/progress_service.dart';
import '../../../core/services/tts_service.dart';
import '_shared.dart';

class ListeningPage extends StatefulWidget {
  const ListeningPage({super.key});
  @override
  State<ListeningPage> createState() => _ListeningPageState();
}

class _LQ {
  final String question;
  final List<String> options;
  final String correct;
  final String? explanation;
  _LQ(this.question, this.options, this.correct, this.explanation);
}

class _ListeningPageState extends State<ListeningPage> {
  late final ApiClient _api = di.sl<ApiClient>();
  String _level = 'B1';
  String? _topic;
  final _customTopic = TextEditingController();
  bool _loading = false;
  String? _error;
  String? _title;
  String _transcript = '';
  List<Map<String, String>> _lines = [];
  List<_LQ> _questions = [];
  Map<int, String> _answers = {};
  bool _showResults = false;
  bool _showTranscript = false;
  bool _playing = false;
  int _playIdx = -1;

  @override
  void dispose() {
    TtsService.instance.stop();
    _customTopic.dispose();
    super.dispose();
  }

  List<Map<String, String>> _parseDialogue(String raw) {
    if (raw.isEmpty) return [];
    final re = RegExp(r"(^|\n)\s*([A-Z][A-Za-z .'\-]{0,31}?):\s+", multiLine: true);
    final ms = re.allMatches(raw).toList();
    if (ms.length < 2) return [{'speaker': 'Narrator', 'text': raw}];
    final out = <Map<String, String>>[];
    for (var i = 0; i < ms.length; i++) {
      final m = ms[i];
      final next = i + 1 < ms.length ? ms[i + 1] : null;
      final speaker = m.group(2)!.trim();
      final body = raw.substring(m.end, next?.start ?? raw.length).trim();
      if (body.isNotEmpty) out.add({'speaker': speaker, 'text': body});
    }
    return out;
  }

  Future<void> _generate() async {
    final t = (_customTopic.text.trim().isEmpty ? _topic : _customTopic.text.trim()) ?? 'Travel';
    setState(() {
      _loading = true; _error = null; _title = null; _transcript = ''; _lines = [];
      _questions = []; _answers = {}; _showResults = false; _showTranscript = false;
    });
    try {
      final r = await _api.post('/listening/generate', data: {
        'difficulty_level': _level,
        'topic': t,
        'duration_seconds': 60,
        'question_count': 5,
        'include_transcript': true,
        'include_vocabulary': true,
      });
      final ex = (unwrapResp(r.data, 'exercise') ?? r.data) as Map;
      final transcript = (ex['transcript'] ?? ex['dialogue'] ?? ex['audio_text'] ?? '').toString();
      final qs = (ex['questions'] as List? ?? []).whereType<Map>().map((q) {
        final m = Map<String, dynamic>.from(q);
        return _LQ(
          (m['question'] ?? '').toString(),
          (m['options'] as List? ?? []).map((e) => e.toString()).toList(),
          (m['correct_answer'] ?? '').toString(),
          m['explanation']?.toString(),
        );
      }).toList();
      if (mounted) setState(() {
        _title = (ex['title'] ?? '$t — listening').toString();
        _transcript = transcript;
        _lines = _parseDialogue(transcript);
        _questions = qs;
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = 'Could not generate. Try again.'; });
    }
  }

  Future<void> _playAll() async {
    if (_playing) {
      await TtsService.instance.stop();
      if (mounted) setState(() { _playing = false; _playIdx = -1; });
      return;
    }
    if (_lines.isEmpty) return;
    setState(() { _playing = true; _playIdx = 0; });
    await TtsService.instance.speakSequence(_lines,
      onProgress: (i) { if (mounted) setState(() => _playIdx = i); },
      onDone: () { if (mounted) setState(() { _playing = false; _playIdx = -1; }); },
    );
  }

  void _submit() {
    var correct = 0;
    for (var i = 0; i < _questions.length; i++) {
      final ans = (_answers[i] ?? '').trim().toLowerCase();
      if (ans == _questions[i].correct.trim().toLowerCase()) correct++;
    }
    setState(() => _showResults = true);
    ProgressService.instance.record(skill: SkillKey.listening, topic: _title, score: correct, total: _questions.length);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBg,
      appBar: pageAppBar(context, 'Listening'),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (_questions.isEmpty) _setupCard(),
            if (_loading) const Padding(padding: EdgeInsets.symmetric(vertical: 40), child: Center(child: CircularProgressIndicator(color: kAccent))),
            if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: whiteCard(child: Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFB91C1C), fontWeight: FontWeight.w600)))),
            if (_questions.isNotEmpty && _title != null) ...[
              _playerCard(),
              const SizedBox(height: 12),
              _questionsCard(),
              const SizedBox(height: 12),
              if (_showResults) _resultsCard() else primaryButton(label: 'Submit answers', onPressed: _answers.length == _questions.length ? _submit : null),
              const SizedBox(height: 12),
              TextButton(onPressed: () => setState(() {
                _questions = []; _title = null; _showResults = false;
              }), child: const Text('Pick another topic', style: TextStyle(color: Colors.white))),
            ],
          ]),
        ),
      ),
    );
  }

  Widget _setupCard() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Pick a topic', style: TextStyle(color: kInk, fontSize: 18, fontWeight: FontWeight.w800)),
      const SizedBox(height: 4),
      const Text('Choose what you want to listen about.', style: TextStyle(color: kMuted, fontSize: 13)),
      const SizedBox(height: 14),
      topicChips(_topic, (t) => setState(() { _topic = t; _customTopic.clear(); })),
      const SizedBox(height: 14),
      TextField(
        controller: _customTopic,
        decoration: InputDecoration(
          hintText: 'or type your own topic…',
          filled: true, fillColor: const Color(0xFFF1F5F9),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        ),
        onChanged: (_) => setState(() { _topic = null; }),
      ),
      const SizedBox(height: 14),
      const Text('Level', style: TextStyle(color: kInk, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      levelChips(_level, (v) => setState(() => _level = v)),
      const SizedBox(height: 18),
      primaryButton(label: 'Generate listening', icon: Icons.headset, onPressed: _generate, loading: _loading),
    ]));
  }

  Widget _playerCard() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(_title!, style: const TextStyle(color: kInk, fontSize: 18, fontWeight: FontWeight.w800)),
      const SizedBox(height: 12),
      Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: kBg, borderRadius: BorderRadius.circular(12)),
        child: Row(children: [
          GestureDetector(
            onTap: _playAll,
            child: Container(
              width: 48, height: 48,
              decoration: const BoxDecoration(color: kAccent, shape: BoxShape.circle),
              child: Icon(_playing ? Icons.stop : Icons.play_arrow, color: Colors.white, size: 28),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(child: Text(
            _playing && _playIdx >= 0 && _playIdx < _lines.length
                ? '${_lines[_playIdx]['speaker']}: ${_lines[_playIdx]['text']}'
                : 'Tap play to hear the audio',
            style: const TextStyle(color: Colors.white, fontSize: 13), maxLines: 2, overflow: TextOverflow.ellipsis,
          )),
        ]),
      ),
      const SizedBox(height: 10),
      TextButton(
        onPressed: () => setState(() => _showTranscript = !_showTranscript),
        child: Text(_showTranscript ? 'Hide transcript' : 'Show transcript', style: const TextStyle(color: kAccent, fontWeight: FontWeight.w700)),
      ),
      if (_showTranscript) Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(10)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: _lines.map((l) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Text('${l['speaker']}: ${l['text']}', style: const TextStyle(color: kInk, fontSize: 13)),
        )).toList()),
      ),
    ]));
  }

  Widget _questionsCard() {
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Questions', style: TextStyle(color: kInk, fontSize: 16, fontWeight: FontWeight.w800)),
      const SizedBox(height: 12),
      ..._questions.asMap().entries.map((e) {
        final i = e.key; final q = e.value;
        return Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('${i + 1}. ${q.question}', style: const TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
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
              child: Text('💡 ${q.explanation!}', style: const TextStyle(color: kMuted, fontSize: 12, fontStyle: FontStyle.italic)),
            ),
          ]),
        );
      }),
    ]));
  }

  Widget _resultsCard() {
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
      const SizedBox(height: 8),
      Center(child: Text(pct >= 80 ? 'Excellent listening!' : pct >= 60 ? 'Good — keep practising.' : 'Try once more.',
        style: const TextStyle(color: kMuted))),
    ]));
  }
}
