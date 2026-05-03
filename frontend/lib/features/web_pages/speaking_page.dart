import 'package:flutter/material.dart';
import 'package:dio/dio.dart' as dio;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import '../../../core/network/api_client.dart';
import '../../../core/di/injection_container.dart' as di;
import '../../../core/services/progress_service.dart';
import '../../../core/services/tts_service.dart';
import '_shared.dart';

class SpeakingPage extends StatefulWidget {
  const SpeakingPage({super.key});
  @override
  State<SpeakingPage> createState() => _SpeakingPageState();
}

const List<String> _kPrompts = [
  'Describe your typical morning routine.',
  'Talk about a memorable trip you took.',
  'What is your favourite kind of food and why?',
  'Describe your job or studies.',
  'Talk about a film or book you enjoyed recently.',
  'Describe the city or town where you live.',
];

class _SpeakingPageState extends State<SpeakingPage> {
  late final ApiClient _api = di.sl<ApiClient>();
  final AudioRecorder _recorder = AudioRecorder();

  String _prompt = _kPrompts[0];
  bool _recording = false;
  bool _assessing = false;
  String? _error;
  String? _filePath;
  Map<String, dynamic>? _result;
  DateTime? _recordStart;
  int _recordSeconds = 0;

  @override
  void dispose() {
    _recorder.dispose();
    TtsService.instance.stop();
    super.dispose();
  }

  Future<void> _start() async {
    try {
      if (!await _recorder.hasPermission()) {
        setState(() => _error = 'Microphone permission required.');
        return;
      }
      final dir = await getTemporaryDirectory();
      final path = '${dir.path}/selm_rec_${DateTime.now().millisecondsSinceEpoch}.m4a';
      await _recorder.start(const RecordConfig(encoder: AudioEncoder.aacLc, bitRate: 128000, sampleRate: 44100), path: path);
      _recordStart = DateTime.now();
      setState(() { _recording = true; _error = null; _filePath = path; _result = null; _recordSeconds = 0; });
      _tick();
    } catch (e) {
      setState(() { _error = 'Could not start recording: $e'; _recording = false; });
    }
  }

  void _tick() async {
    while (mounted && _recording) {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted || !_recording) break;
      setState(() => _recordSeconds = DateTime.now().difference(_recordStart!).inSeconds);
    }
  }

  Future<void> _stopAndAssess() async {
    final path = await _recorder.stop();
    setState(() { _recording = false; _filePath = path ?? _filePath; });
    if ((path ?? _filePath) == null) return;
    await _assess(path ?? _filePath!);
  }

  Future<void> _assess(String path) async {
    setState(() { _assessing = true; _error = null; });
    try {
      final fd = dio.FormData.fromMap({
        'audio_data': await dio.MultipartFile.fromFile(path, filename: 'recording.m4a'),
      });
      final r = await _api.post('/speaking/real-time-assessment', data: fd);
      _result = _normalize(r.data);
      final overall = (_result!['overall'] as num?)?.toInt() ?? 0;
      setState(() => _assessing = false);
      await ProgressService.instance.record(skill: SkillKey.speaking, score: overall);
    } catch (e) {
      setState(() { _assessing = false; _error = 'Assessment failed. Try again.'; });
    }
  }

  Map<String, dynamic> _normalize(dynamic raw) {
    Map body = raw is Map ? Map.from(raw) : {};
    if (body['success'] == true && body['assessment'] is Map) body = Map.from(body['assessment']);
    if (body['success'] == true && body['result'] is Map) body = Map.from(body['result']);
    final c = body['content'];
    if (c is String && c.contains('```')) {
      final p = parseAIContent(body); if (p != null) body = p;
    }
    final sa = (body['speechace_response'] is Map ? (body['speechace_response'] as Map)['text_score'] : null)
        ?? body['text_score']
        ?? body;
    final saMap = sa is Map ? Map<String, dynamic>.from(sa) : <String, dynamic>{};
    final overall = body['overall_score'] ?? saMap['quality_score'] ?? 0;
    final fluencyMap = saMap['fluency'] is Map ? Map<String, dynamic>.from(saMap['fluency']) : <String, dynamic>{};
    final fluencyOM = fluencyMap['overall_metrics'] is Map ? Map<String, dynamic>.from(fluencyMap['overall_metrics']) : <String, dynamic>{};
    final fluency = body['fluency_score'] ?? fluencyOM['fluency_score'];
    final words = ((saMap['word_score_list'] ?? body['word_scores'] ?? []) as List).whereType<Map>().map((w) {
      final m = Map<String, dynamic>.from(w);
      return {
        'word': (m['word'] ?? '').toString(),
        'score': ((m['quality_score'] ?? m['score'] ?? 0) as num).round(),
      };
    }).toList();
    return {
      'overall': (overall as num).round(),
      'fluency': fluency is num ? fluency.round() : null,
      'words': words,
      'feedback': body['feedback']?.toString() ?? body['ai_feedback']?.toString(),
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBg,
      appBar: pageAppBar(context, 'Speaking'),
      body: SafeArea(child: SingleChildScrollView(padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('Speaking prompt', style: TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            Container(padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: const Color(0xFFF1FAF8), borderRadius: BorderRadius.circular(12),
                border: const Border(left: BorderSide(color: kAccent, width: 3))),
              child: Text(_prompt, style: const TextStyle(color: kInk, fontSize: 15, fontWeight: FontWeight.w600))),
            const SizedBox(height: 8),
            Row(children: [
              TextButton.icon(
                onPressed: () => TtsService.instance.speak(_prompt),
                icon: const Icon(Icons.volume_up, color: kAccent, size: 18),
                label: const Text('Listen', style: TextStyle(color: kAccent, fontWeight: FontWeight.w700)),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: () => setState(() => _prompt = (_kPrompts..shuffle()).first),
                icon: const Icon(Icons.refresh, color: kMuted, size: 18),
                label: const Text('Shuffle', style: TextStyle(color: kMuted, fontWeight: FontWeight.w700)),
              ),
            ]),
          ])),
          const SizedBox(height: 12),
          whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Center(child: Text('Tap to record your answer', style: TextStyle(color: kInk, fontSize: 14, fontWeight: FontWeight.w700))),
            const SizedBox(height: 14),
            Center(child: GestureDetector(
              onTap: _assessing ? null : (_recording ? _stopAndAssess : _start),
              child: Container(
                width: 100, height: 100,
                decoration: BoxDecoration(
                  color: _recording ? const Color(0xFFEF4444) : kAccent,
                  shape: BoxShape.circle,
                  boxShadow: [BoxShadow(color: (_recording ? const Color(0xFFEF4444) : kAccent).withValues(alpha: 0.3), blurRadius: 16, spreadRadius: 4)],
                ),
                child: Icon(_recording ? Icons.stop : Icons.mic, color: Colors.white, size: 44),
              ),
            )),
            const SizedBox(height: 12),
            Center(child: Text(
              _recording ? '${_recordSeconds.toString().padLeft(2, '0')}s — recording…' : (_assessing ? 'Assessing…' : 'Tap mic to start'),
              style: TextStyle(color: _recording ? const Color(0xFFEF4444) : kMuted, fontWeight: FontWeight.w700),
            )),
            if (_error != null) Padding(padding: const EdgeInsets.only(top: 10),
              child: Center(child: Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C), fontWeight: FontWeight.w600), textAlign: TextAlign.center))),
          ])),
          if (_assessing) const Padding(padding: EdgeInsets.symmetric(vertical: 18), child: Center(child: CircularProgressIndicator(color: kAccent))),
          if (_result != null) Padding(padding: const EdgeInsets.only(top: 12), child: _resultCard()),
        ]),
      )),
    );
  }

  Widget _resultCard() {
    final r = _result!;
    final overall = (r['overall'] as int);
    final words = (r['words'] as List).cast<Map<String, dynamic>>();
    return whiteCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Center(child: Container(padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        decoration: BoxDecoration(color: scoreBg(overall), borderRadius: BorderRadius.circular(20)),
        child: Text('Overall: $overall / 100', style: TextStyle(color: scoreFg(overall), fontWeight: FontWeight.w800, fontSize: 18)))),
      if (r['fluency'] != null) ...[
        const SizedBox(height: 8),
        Center(child: Text('Fluency: ${r['fluency']}', style: const TextStyle(color: kMuted, fontWeight: FontWeight.w700))),
      ],
      if (words.isNotEmpty) ...[
        const SizedBox(height: 14),
        const Text('Per-word pronunciation', style: TextStyle(color: kInk, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        Wrap(spacing: 6, runSpacing: 6, children: words.map((w) {
          final s = (w['score'] as int);
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(color: scoreBg(s), borderRadius: BorderRadius.circular(10)),
            child: Text('${w['word']} · $s', style: TextStyle(color: scoreFg(s), fontSize: 12, fontWeight: FontWeight.w700)),
          );
        }).toList()),
      ],
      if (r['feedback'] != null && (r['feedback'] as String).isNotEmpty) ...[
        const SizedBox(height: 12),
        Container(padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: const Color(0xFFF1FAF8), borderRadius: BorderRadius.circular(10)),
          child: Text(r['feedback'] as String, style: const TextStyle(color: kInk, fontSize: 13))),
      ],
      const SizedBox(height: 14),
      primaryButton(label: 'Try again', icon: Icons.refresh, onPressed: () => setState(() { _result = null; _filePath = null; })),
    ]));
  }
}

