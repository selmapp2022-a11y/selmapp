import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/di/injection_container.dart' as di;

class OnboardingAssessmentPage extends StatefulWidget {
  const OnboardingAssessmentPage({super.key});
  @override
  State<OnboardingAssessmentPage> createState() => _OnboardingAssessmentPageState();
}

class _Question {
  final int id;
  final String skill;
  final String level;
  final String type;
  final String? passage;
  final String? audioText;
  final String question;
  final List<String> options;
  final String correctAnswer;
  _Question({required this.id, required this.skill, required this.level, required this.type,
    this.passage, this.audioText, required this.question, required this.options, required this.correctAnswer});
  factory _Question.from(Map<String, dynamic> m) => _Question(
    id: (m['id'] as num).toInt(),
    skill: (m['skill'] ?? '').toString(),
    level: (m['difficulty_level'] ?? 'B1').toString(),
    type: (m['question_type'] ?? 'multiple_choice').toString(),
    passage: m['passage']?.toString(),
    audioText: m['audio_text']?.toString(),
    question: (m['question'] ?? '').toString(),
    options: (m['options'] is List) ? List<String>.from((m['options'] as List).map((x) => x.toString())) : <String>[],
    correctAnswer: (m['correct_answer'] ?? '').toString(),
  );
}

class _OnboardingAssessmentPageState extends State<OnboardingAssessmentPage> {
  static const Color _bg = Color(0xFF0C1C2C);
  static const Color _accent = Color(0xFF2DD4BF);
  static const Color _muted = Color(0xFF6B7B8C);
  static const _levels = ['A1','A2','B1','B2','C1','C2'];

  late final ApiClient _api = di.sl<ApiClient>();

  String _stage = 'starting'; // starting | asking | complete | error
  String _statusMsg = 'Preparing personalized questions…';
  double _progress = 0;
  List<_Question> _pool = [];
  final List<_Question> _asked = [];
  _Question? _current;
  String? _selected;
  bool _showFeedback = false;
  int _levelIdx = 2;
  int _correctStreak = 0;
  int _wrongStreak = 0;
  int _correct = 0;
  int _total = 0;
  String? _finalLevel;
  bool _started = false;

  @override
  void initState() {
    super.initState();
    _start();
  }

  _Question _pickAdaptive(List<_Question> remaining, int idx) {
    final target = _levels[idx];
    final sorted = [...remaining];
    sorted.sort((a, b) {
      final da = (_levels.indexOf(a.level) - _levels.indexOf(target)).abs();
      final db = (_levels.indexOf(b.level) - _levels.indexOf(target)).abs();
      return da.compareTo(db);
    });
    return sorted.first;
  }

  Future<void> _start() async {
    if (_started) return;
    _started = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      final demoStr = prefs.getString('selm_demographics') ?? '{}';
      final demo = jsonDecode(demoStr) as Map<String, dynamic>;
      final prefsList = <String>[
        ...((demo['interests'] as List?)?.map((e) => e.toString()) ?? const <String>[]),
        if ((demo['occupation'] ?? '').toString().isNotEmpty) demo['occupation'].toString(),
        if ((demo['goal'] ?? '').toString().isNotEmpty) demo['goal'].toString(),
      ];

      final startResp = await _api.post('/users/level-assessment/start', data: {
        'question_count': 12,
        'user_preferences': prefsList,
        'personalized': true,
      });
      final jobId = startResp.data['job_id']?.toString();
      if (jobId == null) throw Exception('No job_id');

      for (var i = 0; i < 60; i++) {
        await Future.delayed(const Duration(seconds: 2));
        final st = await _api.get('/users/level-assessment/job/$jobId');
        final data = st.data as Map<String, dynamic>;
        if (mounted) {
          setState(() {
            _progress = ((data['progress'] as num?)?.toDouble() ?? 0) / 100.0;
            _statusMsg = (data['message'] ?? 'Generating questions…').toString();
          });
        }
        final status = (data['status'] ?? '').toString();
        if (status == 'completed') {
          final qsRaw = (data['quiz_data']?['questions']
              ?? data['result']?['quiz_data']?['questions']
              ?? data['result']?['questions']
              ?? data['questions']) as List?;
          if (qsRaw == null || qsRaw.isEmpty) throw Exception('No questions returned. Please try again.');
          final qs = qsRaw.map((m) => _Question.from(Map<String, dynamic>.from(m as Map))).toList();
          if (!mounted) return;
          setState(() {
            _pool = qs;
            _stage = 'asking';
            _current = _pickAdaptive(qs, 2);
          });
          return;
        }
        if (status == 'failed') throw Exception(data['error'] ?? 'Assessment generation failed');
      }
      throw Exception('Timeout');
    } catch (e) {
      if (kDebugMode) print('Assessment start error: $e');
      if (mounted) setState(() { _stage = 'error'; _statusMsg = e.toString(); });
    }
  }

  void _answer(String opt) {
    if (_showFeedback || opt.trim().isEmpty || _current == null) return;
    final correct = opt.trim().toLowerCase() == _current!.correctAnswer.trim().toLowerCase();
    setState(() {
      _selected = opt;
      _showFeedback = true;
      _total++;
      if (correct) {
        _correct++;
        _correctStreak++;
        _wrongStreak = 0;
        if (_correctStreak >= 2 && _levelIdx < 5) _levelIdx++;
      } else {
        _wrongStreak++;
        _correctStreak = 0;
        if (_wrongStreak >= 2 && _levelIdx > 0) _levelIdx--;
      }
    });
  }

  Future<void> _nextQuestion() async {
    if (_current == null) return;
    final newAsked = [..._asked, _current!];
    final remaining = _pool.where((q) => !newAsked.any((a) => a.id == q.id)).toList();
    final stop = newAsked.length >= 8 || remaining.isEmpty;
    setState(() {
      _asked.add(_current!);
      _selected = null;
      _showFeedback = false;
    });
    if (stop) {
      if (mounted) setState(() => _stage = 'complete');
      try {
        final answers = newAsked.asMap().entries.map((e) => {
          'question_id': e.value.id,
          'user_answer': e.key == newAsked.length - 1 ? (_selected ?? 'submitted') : 'submitted',
        }).toList();
        final resp = await _api.post('/users/level-assessment/submit', data: {
          'answers': answers, 'time_taken_seconds': 0,
        });
        final data = resp.data as Map<String, dynamic>;
        if (mounted) setState(() => _finalLevel = (data['cefr_level'] ?? data['level'] ?? _levels[_levelIdx]).toString());
      } catch (e) {
        if (kDebugMode) print('submit error: $e');
        if (mounted) setState(() => _finalLevel = _levels[_levelIdx]);
      }
      return;
    }
    setState(() => _current = _pickAdaptive(remaining, _levelIdx));
  }

  @override
  Widget build(BuildContext context) {
    Widget body;
    if (_stage == 'starting') body = _buildLoading();
    else if (_stage == 'error') body = _buildError();
    else if (_stage == 'complete') body = _buildComplete();
    else body = _buildAsking();
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
        child: body,
      )),
    );
  }

  Widget _card({required Widget child}) => Container(
    padding: const EdgeInsets.all(24),
    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
    child: child,
  );

  Widget _buildLoading() {
    return _card(child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 8),
        const Center(child: SizedBox(width: 40, height: 40, child: CircularProgressIndicator(color: _accent, strokeWidth: 3))),
        const SizedBox(height: 16),
        const Text('Building your assessment',
            textAlign: TextAlign.center,
            style: TextStyle(color: Color(0xFF0C1C2C), fontSize: 22, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        Text(_statusMsg, textAlign: TextAlign.center, style: const TextStyle(color: _muted, fontSize: 14)),
        if (_progress > 0) ...[
          const SizedBox(height: 18),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: _progress, minHeight: 8,
              backgroundColor: const Color(0xFFE2E8F0),
              valueColor: const AlwaysStoppedAnimation<Color>(_accent),
            ),
          ),
        ],
      ],
    ));
  }

  Widget _buildError() {
    return _card(child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text("We couldn't build your assessment",
            textAlign: TextAlign.center,
            style: TextStyle(color: Color(0xFF0C1C2C), fontSize: 20, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        const Text('Sometimes the AI model takes a moment to warm up. Please try again — it usually works on the second try.',
            textAlign: TextAlign.center, style: TextStyle(color: _muted, fontSize: 14)),
        const SizedBox(height: 18),
        ElevatedButton(
          onPressed: () { setState(() { _stage = 'starting'; _started = false; }); _start(); },
          style: ElevatedButton.styleFrom(backgroundColor: _bg, foregroundColor: Colors.white, padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
          child: const Text('Try again', style: TextStyle(fontWeight: FontWeight.w600)),
        ),
        const SizedBox(height: 8),
        TextButton(onPressed: () => context.go('/home'),
            child: const Text('Skip for now', style: TextStyle(color: _muted, fontWeight: FontWeight.w600))),
      ],
    ));
  }

  Widget _buildComplete() {
    return _card(child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Center(child: Icon(Icons.check_circle, color: _accent, size: 64)),
        const SizedBox(height: 12),
        const Text('Assessment complete',
            textAlign: TextAlign.center,
            style: TextStyle(color: Color(0xFF0C1C2C), fontSize: 24, fontWeight: FontWeight.w800)),
        const SizedBox(height: 6),
        const Text('Based on your answers, your estimated level is:',
            textAlign: TextAlign.center, style: TextStyle(color: _muted, fontSize: 14)),
        const SizedBox(height: 16),
        Center(child: Text(_finalLevel ?? '…',
            style: const TextStyle(color: _accent, fontSize: 64, fontWeight: FontWeight.w900))),
        const SizedBox(height: 4),
        const Center(child: Text('CEFR LEVEL',
            style: TextStyle(color: _muted, fontSize: 12, letterSpacing: 2, fontWeight: FontWeight.w600))),
        const SizedBox(height: 16),
        Center(child: Text('You answered $_correct out of $_total questions correctly.',
            textAlign: TextAlign.center, style: const TextStyle(color: _muted, fontSize: 13))),
        const SizedBox(height: 18),
        ElevatedButton(
          onPressed: _finalLevel == null ? null : () => context.go('/home'),
          style: ElevatedButton.styleFrom(backgroundColor: _bg, foregroundColor: Colors.white, padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
          child: const Text('Continue to dashboard', style: TextStyle(fontWeight: FontWeight.w600)),
        ),
      ],
    ));
  }

  Widget _buildAsking() {
    final q = _current!;
    final qNum = _asked.length + 1;
    final progress = qNum / 10;
    final opts = q.options.isNotEmpty ? q.options : const ['True', 'False'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Question $qNum of ~10',
                style: const TextStyle(color: Color(0xFFB7C6D6), fontSize: 13, fontWeight: FontWeight.w600)),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: _accent.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(8)),
              child: Text('${q.skill} · ${q.level}',
                  style: const TextStyle(color: _accent, fontSize: 12, fontWeight: FontWeight.w700)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress.clamp(0.0, 1.0), minHeight: 8,
            backgroundColor: const Color(0xFF1A3346),
            valueColor: const AlwaysStoppedAnimation<Color>(_accent),
          ),
        ),
        const SizedBox(height: 16),
        _card(child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (q.passage != null && q.passage!.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFF1FAF8),
                  borderRadius: BorderRadius.circular(12),
                  border: const Border(left: BorderSide(color: _accent, width: 4)),
                ),
                child: Text(q.passage!, style: const TextStyle(color: Color(0xFF0C1C2C), fontSize: 14)),
              ),
              const SizedBox(height: 14),
            ],
            if (q.audioText != null && q.audioText!.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(12)),
                child: Text('🔊 "${q.audioText!}"',
                    style: const TextStyle(color: _muted, fontStyle: FontStyle.italic, fontSize: 14)),
              ),
              const SizedBox(height: 14),
            ],
            Text(q.question,
                style: const TextStyle(color: Color(0xFF0C1C2C), fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),
            ...opts.map((opt) {
              final isSel = _selected == opt;
              final isCorrect = opt.trim().toLowerCase() == q.correctAnswer.trim().toLowerCase();
              Color bg = Colors.white;
              Color border = const Color(0xFFE2E8F0);
              if (_showFeedback) {
                if (isCorrect) { bg = const Color(0xFFD1FAE5); border = const Color(0xFF10B981); }
                else if (isSel) { bg = const Color(0xFFFEE2E2); border = const Color(0xFFEF4444); }
              } else if (isSel) {
                bg = _accent.withValues(alpha: 0.1); border = _accent;
              }
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: GestureDetector(
                  onTap: () => _answer(opt),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(color: bg, border: Border.all(color: border, width: 2), borderRadius: BorderRadius.circular(12)),
                    child: Row(children: [
                      Expanded(child: Text(opt, style: const TextStyle(color: Color(0xFF0C1C2C), fontSize: 14, fontWeight: FontWeight.w500))),
                      if (_showFeedback && isCorrect) const Icon(Icons.check_circle, color: Color(0xFF10B981)),
                      if (_showFeedback && isSel && !isCorrect) const Icon(Icons.cancel, color: Color(0xFFEF4444)),
                    ]),
                  ),
                ),
              );
            }),
            if (_showFeedback) ...[
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: _nextQuestion,
                style: ElevatedButton.styleFrom(backgroundColor: _bg, foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                child: const Text('Next question', style: TextStyle(fontWeight: FontWeight.w600)),
              ),
            ],
          ],
        )),
      ],
    );
  }
}
