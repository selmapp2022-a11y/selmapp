import 'dart:async';
import 'package:flutter/material.dart';
import '../../../core/network/api_client.dart';
import '../../../core/di/injection_container.dart' as di;
import '../../../core/services/progress_service.dart';
import '_shared.dart';

class WritingPage extends StatefulWidget {
  const WritingPage({super.key});
  @override
  State<WritingPage> createState() => _WritingPageState();
}

class _GErr {
  final String type, text, suggestion;
  final String? explanation;
  _GErr(this.type, this.text, this.suggestion, this.explanation);
}

class _WritingPageState extends State<WritingPage> {
  late final ApiClient _api = di.sl<ApiClient>();
  final _ctrl = TextEditingController();
  final _promptCtrl = TextEditingController();
  Timer? _debounce;
  List<_GErr> _errors = [];
  bool _checking = false;
  bool _assessing = false;
  Map<String, dynamic>? _assessment;
  String? _error;

  @override
  void dispose() {
    _debounce?.cancel();
    _ctrl.dispose();
    _promptCtrl.dispose();
    super.dispose();
  }

  void _onChanged(String v) {
    _debounce?.cancel();
    if (v.trim().split(RegExp(r'\s+')).length < 5) {
      setState(() => _errors = []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 1200), _checkGrammar);
  }

  Future<void> _checkGrammar() async {
    final text = _ctrl.text.trim();
    if (text.isEmpty) return;
    setState(() => _checking = true);
    try {
      final r = await _api.post('/ai/grammar-check', data: {'text': text});
      final p = parseAIContent(r.data) ?? {};
      final list = ((p['errors'] ?? []) as List).whereType<Map>().map((e) {
        final m = Map<String, dynamic>.from(e);
        return _GErr(
          (m['type'] ?? 'grammar').toString(),
          (m['error'] ?? m['original'] ?? m['text'] ?? '').toString(),
          (m['correction'] ?? m['suggestion'] ?? m['replacement'] ?? '').toString(),
          m['explanation']?.toString(),
        );
      }).toList();
      if (mounted) setState(() { _errors = list; _checking = false; });
    } catch (_) {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _assess() async {
    final text = _ctrl.text.trim();
    if (text.split(RegExp(r'\s+')).length < 30) {
      setState(() => _error = 'Write at least 30 words for a useful assessment.');
      return;
    }
    setState(() { _assessing = true; _error = null; _assessment = null; });
    try {
      final r = await _api.post('/writing/assess', data: {
        'text': text, 'prompt': _promptCtrl.text.trim(), 'assessment_type': 'comprehensive',
      });
      final a = unwrapResp(r.data, 'assessment');
      final aMap = (a is Map ? Map<String, dynamic>.from(a) : <String, dynamic>{});
      final scores = (aMap['scores'] is Map ? Map<String, dynamic>.from(aMap['scores']) : <String, dynamic>{});
      final overall = ((scores['overall'] ?? aMap['overall_score'] ?? 0) as num).round();
      final result = {
        'overall': overall,
        'grammar': (scores['grammar'] ?? aMap['grammar_score']) as num?,
        'vocabulary': (scores['vocabulary'] ?? aMap['vocabulary_score']) as num?,
        'coherence': (scores['coherence'] ?? aMap['coherence_score']) as num?,
        'task': (scores['task_achievement'] ?? scores['task_response'] ?? aMap['task_response_score']) as num?,
        'feedback': aMap['feedback']?.toString(),
        'strengths': (aMap['strengths'] as List?)?.map((e) => e.toString()).toList() ?? <String>[],
        'weaknesses': (aMap['weaknesses'] as List?)?.map((e) => e.toString()).toList() ?? <String>[],
      };
      if (mounted) setState(() { _assessment = result; _assessing = false; });
      await ProgressService.instance.record(skill: SkillKey.writing, score: overall);
    } catch (e) {
      if (mounted) setState(() { _assessing = false; _error = 'Could not assess. Try again.'; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final wc = _ctrl.text.trim().isEmpty ? 0 : _ctrl.text.trim().split(RegExp(r'\s+')).length;
    return Scaffold(
      backgroundColor: kBg,
      appBar: pageAppBar(context, 'Writing'),
      body: SafeArea(child: SingleChildScrollView(padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('Optional prompt', style: TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            TextField(controller: _promptCtrl, maxLines: 2,
              decoration: InputDecoration(hintText: 'e.g. Describe your favourite city',
                filled: true, fillColor: const Color(0xFFF1F5F9),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10))),
            const SizedBox(height: 14),
            Row(children: [
              const Expanded(child: Text('Your writing', style: TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w700))),
              if (_checking) const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: kAccent)),
              if (_checking) const SizedBox(width: 6),
              Text('$wc words', style: const TextStyle(color: kMuted, fontSize: 12)),
            ]),
            const SizedBox(height: 8),
            TextField(controller: _ctrl, maxLines: 8, onChanged: _onChanged,
              decoration: InputDecoration(hintText: 'Write at least 30 words…',
                filled: true, fillColor: const Color(0xFFF8FAFC),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                contentPadding: const EdgeInsets.all(12))),
            const SizedBox(height: 14),
            primaryButton(label: 'Assess writing', icon: Icons.fact_check_outlined, onPressed: _assess, loading: _assessing),
          ])),
          if (_errors.isNotEmpty) ...[
            const SizedBox(height: 12),
            whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Live grammar suggestions', style: TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w800)),
              const SizedBox(height: 10),
              ..._errors.map((e) => Padding(padding: const EdgeInsets.only(bottom: 10),
                child: Container(padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(color: const Color(0xFFFEF3C7), borderRadius: BorderRadius.circular(10),
                    border: const Border(left: BorderSide(color: Color(0xFFF59E0B), width: 3))),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Container(padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(color: const Color(0xFFF59E0B), borderRadius: BorderRadius.circular(4)),
                        child: Text(e.type.toUpperCase(), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w800))),
                      const SizedBox(width: 8),
                      Expanded(child: Text(e.text, style: const TextStyle(color: kInk, fontSize: 13, decoration: TextDecoration.lineThrough))),
                    ]),
                    if (e.suggestion.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4),
                      child: Text('→ ${e.suggestion}', style: const TextStyle(color: Color(0xFF047857), fontSize: 13, fontWeight: FontWeight.w700))),
                    if (e.explanation != null && e.explanation!.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4),
                      child: Text(e.explanation!, style: const TextStyle(color: kMuted, fontSize: 12))),
                  ])))),
            ])),
          ],
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 12),
            child: whiteCard(child: Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFB91C1C), fontWeight: FontWeight.w600)))),
          if (_assessment != null) Padding(padding: const EdgeInsets.only(top: 12), child: _assessmentCard()),
        ]),
      )),
    );
  }

  Widget _assessmentCard() {
    final a = _assessment!;
    final overall = a['overall'] as int;
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Center(child: Container(padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        decoration: BoxDecoration(color: scoreBg(overall), borderRadius: BorderRadius.circular(20)),
        child: Text('Overall: $overall / 100',
          style: TextStyle(color: scoreFg(overall), fontWeight: FontWeight.w800, fontSize: 18)))),
      const SizedBox(height: 14),
      Wrap(spacing: 8, runSpacing: 8, children: [
        if (a['grammar'] != null) _scoreBox('Grammar', (a['grammar'] as num).round()),
        if (a['vocabulary'] != null) _scoreBox('Vocabulary', (a['vocabulary'] as num).round()),
        if (a['coherence'] != null) _scoreBox('Coherence', (a['coherence'] as num).round()),
        if (a['task'] != null) _scoreBox('Task', (a['task'] as num).round()),
      ]),
      if (a['feedback'] != null && (a['feedback'] as String).isNotEmpty) ...[
        const SizedBox(height: 12),
        Container(padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: const Color(0xFFF1FAF8), borderRadius: BorderRadius.circular(10)),
          child: Text(a['feedback'] as String, style: const TextStyle(color: kInk, fontSize: 13))),
      ],
      if ((a['strengths'] as List).isNotEmpty) ...[
        const SizedBox(height: 12),
        const Text('Strengths', style: TextStyle(color: kInk, fontWeight: FontWeight.w800)),
        ...(a['strengths'] as List).map((s) => Padding(padding: const EdgeInsets.only(top: 4),
          child: Text('✓ $s', style: const TextStyle(color: Color(0xFF047857), fontSize: 13)))),
      ],
      if ((a['weaknesses'] as List).isNotEmpty) ...[
        const SizedBox(height: 12),
        const Text('To improve', style: TextStyle(color: kInk, fontWeight: FontWeight.w800)),
        ...(a['weaknesses'] as List).map((s) => Padding(padding: const EdgeInsets.only(top: 4),
          child: Text('• $s', style: const TextStyle(color: Color(0xFFB45309), fontSize: 13)))),
      ],
    ]));
  }

  Widget _scoreBox(String label, int score) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    decoration: BoxDecoration(color: scoreBg(score), borderRadius: BorderRadius.circular(10)),
    child: Column(children: [
      Text('$score', style: TextStyle(color: scoreFg(score), fontWeight: FontWeight.w800, fontSize: 18)),
      Text(label, style: TextStyle(color: scoreFg(score), fontSize: 11, fontWeight: FontWeight.w600)),
    ]),
  );
}
