// IELTS Speaking Part 3 — multi-turn discussion screen.
//
// Flow: user enters/confirms the Part 2 topic → backend generates 4-5
// abstract follow-up questions → user answers each via mic (audio is
// transcribed by the existing /speech/evaluate ielts pipeline) → after
// the final turn, /speech/ielts/part3/score-discussion returns a
// holistic IELTS Speaking band breakdown.
//
// 2026-05-25 — finding #5 from the audit.

import 'dart:async';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../data/repositories/practice_repository.dart';

enum _Part3Step { enterTopic, loadingQuestions, answering, scoring, results }

class IeltsSpeakingPart3Page extends StatefulWidget {
  final String? initialTopic;
  const IeltsSpeakingPart3Page({super.key, this.initialTopic});

  @override
  State<IeltsSpeakingPart3Page> createState() => _IeltsSpeakingPart3PageState();
}

class _IeltsSpeakingPart3PageState extends State<IeltsSpeakingPart3Page> {
  late final PracticeRepositoryImpl _repo;
  late final ApiClient _apiClient;
  final AudioRecorder _recorder = AudioRecorder();
  final TextEditingController _topicController = TextEditingController();

  _Part3Step _step = _Part3Step.enterTopic;
  String _topic = '';
  List<String> _questions = [];
  int _currentIndex = 0;
  bool _isRecording = false;
  String? _currentRecordingPath;
  final List<Part3Turn> _turns = [];
  Part3DiscussionResult? _result;
  String? _error;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient(SecureStorage());
    _repo = PracticeRepositoryImpl(_apiClient);
    if (widget.initialTopic != null && widget.initialTopic!.isNotEmpty) {
      _topicController.text = widget.initialTopic!;
    }
  }

  /// Inlined transcription via /speech/evaluate (mode=ielts). Returns
  /// the transcript text, or null on failure. Uses the same Dio client
  /// the rest of the app uses so auth headers are already attached.
  Future<String?> _transcribe(String filePath, String prompt) async {
    try {
      final formData = FormData.fromMap({
        'reference_text': '', // empty → SpeechAce open-ended path
        'language': 'en-US',
        'mode': 'ielts',
        'prompt': prompt,
        'audio': await MultipartFile.fromFile(
          filePath,
          filename: 'answer.m4a',
          contentType: DioMediaType('audio', 'mp4'),
        ),
      });
      final resp = await _apiClient.post(
        '/speech/evaluate',
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
      );
      final data = resp.data as Map<String, dynamic>?;
      if (data == null) return null;
      final transcript = data['transcript'];
      if (transcript is Map && transcript['text'] is String) {
        return (transcript['text'] as String).trim();
      }
      return null;
    } catch (e) {
      if (kDebugMode) print('Part 3 transcribe failed: $e');
      return null;
    }
  }

  @override
  void dispose() {
    _topicController.dispose();
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _loadQuestions() async {
    final t = _topicController.text.trim();
    if (t.length < 5) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Type the Part 2 cue-card topic (a few words).'),
        ),
      );
      return;
    }
    setState(() {
      _topic = t;
      _step = _Part3Step.loadingQuestions;
      _error = null;
    });
    final qs = await _repo.generatePart3Questions(part2Topic: t, count: 5);
    if (!mounted) return;
    if (qs.isEmpty) {
      setState(() {
        _step = _Part3Step.enterTopic;
        _error = 'Could not load Part 3 questions. Please try again.';
      });
      return;
    }
    setState(() {
      _questions = qs;
      _currentIndex = 0;
      _turns.clear();
      _step = _Part3Step.answering;
    });
  }

  Future<void> _startRecording() async {
    final hasPerm = await _recorder.hasPermission();
    if (!hasPerm) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Microphone permission required.')),
      );
      return;
    }
    final path = await _getRecordingPath();
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.aacLc,
        bitRate: 128000,
        sampleRate: 44100,
      ),
      path: path,
    );
    setState(() {
      _isRecording = true;
      _currentRecordingPath = path;
    });
  }

  Future<String> _getRecordingPath() async {
    // Use the platform's app-temp directory so iOS recording works.
    final dir = await getTemporaryDirectory();
    final ts = DateTime.now().millisecondsSinceEpoch;
    return '${dir.path}/ielts_part3_$ts.m4a';
  }

  Future<void> _stopAndTranscribe() async {
    setState(() => _isRecording = false);
    final path = await _recorder.stop();
    if (path == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Recording was empty.')),
      );
      return;
    }
    if (!File(path).existsSync()) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Recording file not found.')),
      );
      return;
    }
    // Send to /speech/evaluate with mode=ielts to get a transcript.
    // The transcript is what we feed into the final scoring call.
    final transcript = await _transcribe(path, _questions[_currentIndex]);
    if (!mounted) return;
    if (transcript == null || transcript.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Could not transcribe — please try recording again.',
          ),
        ),
      );
      return;
    }
    setState(() {
      _turns.add(
        Part3Turn(question: _questions[_currentIndex], transcript: transcript),
      );
      if (_currentIndex < _questions.length - 1) {
        _currentIndex++;
      } else {
        _step = _Part3Step.scoring;
      }
    });
    if (_step == _Part3Step.scoring) {
      _scoreDiscussion();
    }
  }

  Future<void> _scoreDiscussion() async {
    final result = await _repo.scorePart3Discussion(
      part2Topic: _topic,
      turns: _turns,
    );
    if (!mounted) return;
    setState(() {
      _result = result;
      _step = _Part3Step.results;
    });
  }

  void _restart() {
    setState(() {
      _step = _Part3Step.enterTopic;
      _topic = '';
      _topicController.clear();
      _questions = [];
      _currentIndex = 0;
      _turns.clear();
      _result = null;
      _error = null;
      _isRecording = false;
      _currentRecordingPath = null;
    });
  }

  void _skipTurn() {
    // Allow user to move on even if they did not answer (transcript empty).
    setState(() {
      _turns.add(
        Part3Turn(question: _questions[_currentIndex], transcript: ''),
      );
      if (_currentIndex < _questions.length - 1) {
        _currentIndex++;
      } else {
        _step = _Part3Step.scoring;
        _scoreDiscussion();
      }
    });
  }

  // ─── colours ────────────────────────────────────────────────────
  Color _bandColor(double band) {
    if (band >= 7.0) return Colors.green;
    if (band >= 5.5) return Colors.orange;
    return Colors.red;
  }

  String _bandLabel(double band) {
    if (band >= 8.5) return 'Expert';
    if (band >= 7.0) return 'Good';
    if (band >= 6.0) return 'Competent';
    if (band >= 5.0) return 'Modest';
    if (band >= 4.0) return 'Limited';
    return 'Beginner';
  }

  String _formatBand(double? b) {
    if (b == null) return '–';
    return b.toStringAsFixed(1);
  }

  // ─── build ──────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: const Text('IELTS Speaking Part 3'),
        backgroundColor: Colors.red.shade700,
        foregroundColor: Colors.white,
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    switch (_step) {
      case _Part3Step.enterTopic:
        return _buildTopicScreen();
      case _Part3Step.loadingQuestions:
        return const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Generating Part 3 discussion questions…'),
            ],
          ),
        );
      case _Part3Step.answering:
        return _buildAnsweringScreen();
      case _Part3Step.scoring:
        return const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Scoring the discussion against IELTS bands…'),
            ],
          ),
        );
      case _Part3Step.results:
        return _buildResults();
    }
  }

  // ─── step 1: topic entry ─────────────────────────────────────────
  Widget _buildTopicScreen() {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Part 2 cue-card topic',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 6),
        const Text(
          'Type the topic you just spoke about in Part 2. Part 3 will '
          'explore that theme in more abstract terms.',
          style: TextStyle(fontSize: 14, color: Colors.black54),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _topicController,
          decoration: InputDecoration(
            hintText: 'e.g. "describe a memorable journey you have taken"',
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
          maxLines: 3,
        ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.red.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                const Icon(Icons.error_outline, color: Colors.red),
                const SizedBox(width: 8),
                Expanded(child: Text(_error!)),
              ],
            ),
          ),
        ],
        const SizedBox(height: 18),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.amber.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: Colors.amber.withValues(alpha: 0.3)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: const [
              Text(
                'What to expect',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              SizedBox(height: 6),
              Text(
                '• 5 abstract follow-up questions tied to your topic\n'
                '• ~30-60 seconds per answer\n'
                '• Aim to extend, justify and give examples\n'
                '• Scored on the four official IELTS Speaking bands',
                style: TextStyle(fontSize: 13, height: 1.45),
              ),
            ],
          ),
        ),
        const SizedBox(height: 22),
        ElevatedButton.icon(
          onPressed: _loadQuestions,
          icon: const Icon(Icons.play_arrow),
          label: const Text('Start Part 3'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.red.shade700,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 14),
            textStyle: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  // ─── step 2: answering each question ─────────────────────────────
  Widget _buildAnsweringScreen() {
    final q = _questions[_currentIndex];
    final total = _questions.length;
    final n = _currentIndex + 1;
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
          width: double.infinity,
          color: Colors.red.shade700,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Question $n of $total',
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
              const SizedBox(height: 4),
              LinearProgressIndicator(
                value: n / total,
                backgroundColor: Colors.white.withValues(alpha: 0.25),
                valueColor: const AlwaysStoppedAnimation(Colors.white),
              ),
            ],
          ),
        ),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Examiner:',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.black54,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.shade300),
                  ),
                  child: Text(
                    q,
                    style: const TextStyle(fontSize: 17, height: 1.4),
                  ),
                ),
                const SizedBox(height: 24),
                const Center(
                  child: Text(
                    'Tap to record your answer (~30-60 sec)',
                    style: TextStyle(fontSize: 13, color: Colors.black54),
                  ),
                ),
                const SizedBox(height: 24),
                Center(
                  child: GestureDetector(
                    onTap: _isRecording ? _stopAndTranscribe : _startRecording,
                    child: Container(
                      width: 96,
                      height: 96,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _isRecording
                            ? Colors.red.shade700
                            : Colors.red.shade100,
                        boxShadow: [
                          BoxShadow(
                            color: Colors.red.withValues(alpha: 0.25),
                            blurRadius: 16,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                      child: Icon(
                        _isRecording ? Icons.stop : Icons.mic,
                        color: _isRecording ? Colors.white : Colors.red.shade700,
                        size: 44,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Center(
                  child: Text(
                    _isRecording ? 'Recording… tap to stop' : 'Tap to record',
                    style: const TextStyle(
                      fontSize: 14,
                      color: Colors.black87,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                const Spacer(),
                Row(
                  children: [
                    Expanded(
                      child: TextButton.icon(
                        onPressed: _isRecording ? null : _skipTurn,
                        icon: const Icon(Icons.skip_next),
                        label: const Text('Skip question'),
                      ),
                    ),
                    Expanded(
                      child: TextButton.icon(
                        onPressed: _isRecording ? null : _restart,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Start over'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ─── step 3: results ─────────────────────────────────────────────
  Widget _buildResults() {
    final r = _result;
    if (r == null) {
      return const Center(child: Text('No result.'));
    }
    if (!r.success) {
      return Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, color: Colors.red, size: 48),
            const SizedBox(height: 12),
            Text(r.error ?? 'Scoring failed.'),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _restart,
              child: const Text('Try again'),
            ),
          ],
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (r.overallBand != null) _buildBandHero(r),
        const SizedBox(height: 20),
        // Four IELTS bands
        Row(
          children: [
            Expanded(
              child: _bandTile(
                'Fluency &\nCoherence',
                _band(r.fluencyCoherence),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _bandTile('Lexical\nResource', _band(r.lexicalResource)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _bandTile(
                'Grammar\nAccuracy',
                _band(r.grammarAccuracy),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _bandTile('Task\nResponse', _band(r.taskResponse)),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (r.tips.isNotEmpty)
          _bulletBox('Examiner tips', r.tips, Colors.indigo),
        if (r.turnFeedback.isNotEmpty) _turnFeedbackBox(r.turnFeedback),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _restart,
                icon: const Icon(Icons.refresh),
                label: const Text('Try another topic'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.check),
                label: const Text('Done'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red.shade700,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  double? _band(Map<String, dynamic>? d) {
    if (d == null) return null;
    final v = d['band'];
    if (v is num) return v.toDouble();
    return null;
  }

  Widget _buildBandHero(Part3DiscussionResult r) {
    final band = r.overallBand!;
    final c = _bandColor(band);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [c.withValues(alpha: 0.18), c.withValues(alpha: 0.05)],
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: c.withValues(alpha: 0.45), width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.workspace_premium, color: c, size: 24),
              const SizedBox(width: 8),
              const Text(
                'IELTS Speaking Part 3 Band',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                _formatBand(band),
                style: TextStyle(
                  fontSize: 56,
                  fontWeight: FontWeight.bold,
                  color: c,
                  height: 1.0,
                ),
              ),
              const SizedBox(width: 6),
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  '/ 9',
                  style: TextStyle(fontSize: 18, color: Colors.grey[700]),
                ),
              ),
              const Spacer(),
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  _bandLabel(band),
                  style: TextStyle(
                    fontSize: 15,
                    color: c,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          if (r.partTopic != null && r.partTopic!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              'Topic: ${r.partTopic}',
              style: const TextStyle(fontSize: 13, color: Colors.black54),
            ),
          ],
        ],
      ),
    );
  }

  Widget _bandTile(String label, double? band) {
    final c = band == null ? Colors.grey : _bandColor(band);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 12, color: Colors.black87),
          ),
          const SizedBox(height: 6),
          Text(
            _formatBand(band),
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: c,
            ),
          ),
        ],
      ),
    );
  }

  Widget _bulletBox(String title, List<String> items, Color colour) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colour.withValues(alpha: 0.22)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 14,
              color: colour,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('• ', style: TextStyle(color: colour, fontSize: 14)),
                  Expanded(
                    child: Text(
                      item,
                      style: const TextStyle(fontSize: 14, height: 1.4),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _turnFeedbackBox(List<Map<String, dynamic>> feedback) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.deepPurple.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.deepPurple.withValues(alpha: 0.22)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Per-question feedback',
            style: TextStyle(
              fontSize: 14,
              color: Colors.deepPurple,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          ...feedback.map((f) {
            final turn = f['turn'] ?? '?';
            final comment = f['comment']?.toString() ?? '';
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Question $turn',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.deepPurple,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    comment,
                    style: const TextStyle(fontSize: 13, height: 1.4),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}
