// IELTS Writing practice screen — Task 1 (letter / chart) + Task 2 (essay).
//
// Flow: task type select → backend generates prompt → user writes →
// /writing/assess with task_type returns IELTS band scoring.
//
// 2026-05-25 — finding #4 from the audit (dedicated IELTS Writing UI).

import 'dart:async';
import 'package:flutter/material.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../../data/repositories/practice_repository.dart';

enum _IeltsWritingStep { selectTask, loadingTask, writing, scoring, results }

class IeltsWritingPage extends StatefulWidget {
  const IeltsWritingPage({super.key});

  @override
  State<IeltsWritingPage> createState() => _IeltsWritingPageState();
}

class _IeltsWritingPageState extends State<IeltsWritingPage> {
  late final PracticeRepositoryImpl _repo;
  final TextEditingController _writingController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  _IeltsWritingStep _step = _IeltsWritingStep.selectTask;
  String? _taskType;
  IeltsWritingTask? _task;
  WritingAssessmentResult? _result;
  String? _error;

  Timer? _countdown;
  int _remainingSeconds = 0;

  @override
  void initState() {
    super.initState();
    _repo = PracticeRepositoryImpl(ApiClient(SecureStorage()));
    _writingController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _countdown?.cancel();
    _writingController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  int get _wordCount {
    final t = _writingController.text.trim();
    if (t.isEmpty) return 0;
    return t.split(RegExp(r'\s+')).length;
  }

  int _minWordCount() {
    if (_taskType == 'ielts_task2') return 250;
    return 150;
  }

  Future<void> _selectTask(String taskType) async {
    setState(() {
      _taskType = taskType;
      _step = _IeltsWritingStep.loadingTask;
      _error = null;
    });
    final task = await _repo.generateIeltsWritingTask(taskType: taskType);
    if (!mounted) return;
    if (task == null) {
      setState(() {
        _step = _IeltsWritingStep.selectTask;
        _error = 'Could not load the task prompt. Please try again.';
      });
      return;
    }
    setState(() {
      _task = task;
      _step = _IeltsWritingStep.writing;
      _remainingSeconds = task.timeLimitMinutes * 60;
    });
    _startCountdown();
  }

  void _startCountdown() {
    _countdown?.cancel();
    _countdown = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      if (_remainingSeconds <= 0) {
        t.cancel();
        return;
      }
      setState(() => _remainingSeconds--);
    });
  }

  Future<void> _submitForScoring() async {
    if (_writingController.text.trim().length < 30) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please write at least a few sentences first.'),
        ),
      );
      return;
    }
    _countdown?.cancel();
    setState(() {
      _step = _IeltsWritingStep.scoring;
      _error = null;
    });
    final result = await _repo.assessWriting(
      text: _writingController.text,
      writingType: 'essay',
      taskType: _taskType,
      prompt: _task?.promptText,
    );
    if (!mounted) return;
    setState(() {
      _result = result;
      _step = _IeltsWritingStep.results;
    });
  }

  void _startOver() {
    _countdown?.cancel();
    setState(() {
      _step = _IeltsWritingStep.selectTask;
      _taskType = null;
      _task = null;
      _result = null;
      _error = null;
      _writingController.clear();
      _remainingSeconds = 0;
    });
  }

  String _formatRemaining() {
    final m = _remainingSeconds ~/ 60;
    final s = _remainingSeconds % 60;
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }

  // ─── colour helpers ─────────────────────────────────────────────
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
        title: const Text('IELTS Writing Practice'),
        backgroundColor: Colors.teal,
        foregroundColor: Colors.white,
        actions: [
          if (_step == _IeltsWritingStep.writing && _remainingSeconds > 0)
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.timer, color: Colors.white, size: 16),
                      const SizedBox(width: 4),
                      Text(
                        _formatRemaining(),
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
      body: SafeArea(child: _buildBody()),
    );
  }

  Widget _buildBody() {
    switch (_step) {
      case _IeltsWritingStep.selectTask:
        return _buildTaskSelector();
      case _IeltsWritingStep.loadingTask:
        return const Center(child: CircularProgressIndicator());
      case _IeltsWritingStep.writing:
        return _buildWritingScreen();
      case _IeltsWritingStep.scoring:
        return const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Scoring against IELTS band descriptors…'),
            ],
          ),
        );
      case _IeltsWritingStep.results:
        return _buildResults();
    }
  }

  // ─── step 1: task selector ────────────────────────────────────────
  Widget _buildTaskSelector() {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Choose a task',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 6),
        const Text(
          'Each task mirrors a real IELTS Writing exam question.',
          style: TextStyle(fontSize: 14, color: Colors.black54),
        ),
        const SizedBox(height: 20),
        _taskCard(
          taskType: 'ielts_task1_letter',
          icon: Icons.mail_outline,
          title: 'General Task 1 — Letter',
          subtitle: '150 words · 20 min · 33% of the band',
          description:
              'Write a formal, semi-formal or informal letter that addresses three bullet-point requirements.',
          colour: Colors.indigo,
        ),
        const SizedBox(height: 12),
        _taskCard(
          taskType: 'ielts_task1_chart',
          icon: Icons.bar_chart,
          title: 'Academic Task 1 — Chart',
          subtitle: '150 words · 20 min · 33% of the band',
          description:
              'Summarise a chart, graph, table, map or diagram. Report the main features and key comparisons.',
          colour: Colors.deepPurple,
        ),
        const SizedBox(height: 12),
        _taskCard(
          taskType: 'ielts_task2',
          icon: Icons.edit_note,
          title: 'Task 2 — Essay',
          subtitle: '250 words · 40 min · 67% of the band',
          description:
              'Discuss an opinion, both views, problem-solution, or advantages-disadvantages. Use examples.',
          colour: Colors.teal,
        ),
        if (_error != null) ...[
          const SizedBox(height: 16),
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
      ],
    );
  }

  Widget _taskCard({
    required String taskType,
    required IconData icon,
    required String title,
    required String subtitle,
    required String description,
    required Color colour,
  }) {
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: () => _selectTask(taskType),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: colour.withValues(alpha: 0.4), width: 1.2),
          boxShadow: [
            BoxShadow(
              color: colour.withValues(alpha: 0.08),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: colour.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: colour, size: 26),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(fontSize: 12, color: colour),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    description,
                    style: const TextStyle(
                      fontSize: 13,
                      color: Colors.black54,
                      height: 1.35,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: Colors.black38),
          ],
        ),
      ),
    );
  }

  // ─── step 2: writing screen ───────────────────────────────────────
  Widget _buildWritingScreen() {
    final task = _task!;
    final wc = _wordCount;
    final min = _minWordCount();
    return Column(
      children: [
        Expanded(
          child: ListView(
            controller: _scrollController,
            padding: const EdgeInsets.all(16),
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.teal.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Colors.teal.withValues(alpha: 0.25),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      task.taskName,
                      style: const TextStyle(
                        fontSize: 14,
                        color: Colors.teal,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      task.promptText,
                      style: const TextStyle(
                        fontSize: 15,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        task.instructions,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.black87,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _writingController,
                maxLines: 16,
                minLines: 12,
                decoration: InputDecoration(
                  hintText: 'Begin writing your response here…',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide(color: Colors.grey.shade300),
                  ),
                ),
                style: const TextStyle(fontSize: 15, height: 1.45),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Words: $wc / $min target',
                    style: TextStyle(
                      fontSize: 13,
                      color: wc >= min ? Colors.green : Colors.black54,
                      fontWeight:
                          wc >= min ? FontWeight.w600 : FontWeight.normal,
                    ),
                  ),
                  TextButton(
                    onPressed: _startOver,
                    child: const Text('Change task'),
                  ),
                ],
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _submitForScoring,
              icon: const Icon(Icons.send),
              label: const Text('Submit for IELTS scoring'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.teal,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                textStyle: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ─── step 3: results screen ───────────────────────────────────────
  Widget _buildResults() {
    final r = _result;
    if (r == null) return const Center(child: Text('No result.'));
    final band = r.ieltsBand;
    final breakdown = r.ieltsBreakdown ?? const <String, double?>{};
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (band != null) ...[
          _buildBandHero(band, breakdown),
          const SizedBox(height: 20),
        ],
        // Scores 0-100 grid
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.grey.shade300),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Detailed scores',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 10),
              _scoreRow('Overall', r.scores.overall),
              _scoreRow('Grammar', r.scores.grammar),
              _scoreRow('Vocabulary', r.scores.vocabulary),
              _scoreRow('Coherence', r.scores.coherence),
              _scoreRow('Task achievement', r.scores.taskAchievement),
            ],
          ),
        ),
        const SizedBox(height: 16),
        if (r.feedback.isNotEmpty)
          _feedbackBox('Examiner notes', r.feedback, Colors.blue),
        if (r.strengths.isNotEmpty)
          _bulletBox('Strengths', r.strengths, Colors.green),
        if (r.weaknesses.isNotEmpty)
          _bulletBox('Areas to improve', r.weaknesses, Colors.orange),
        if (r.suggestions.isNotEmpty)
          _bulletBox('Suggestions', r.suggestions, Colors.indigo),
        if (r.correctedVersion != null && r.correctedVersion!.isNotEmpty)
          _feedbackBox(
            'Corrected version',
            r.correctedVersion!,
            Colors.deepPurple,
          ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _startOver,
                icon: const Icon(Icons.refresh),
                label: const Text('Try another task'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.check),
                label: const Text('Done'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.teal,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildBandHero(double band, Map<String, double?> breakdown) {
    final c = _bandColor(band);
    final criteriaLabels = const {
      'task_response': 'Task Response',
      'coherence_cohesion': 'Coherence',
      'lexical_resource': 'Lexical',
      'grammar_accuracy': 'Grammar',
    };
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
                'IELTS Writing Band',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
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
          if (breakdown.values.any((v) => v != null)) ...[
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: criteriaLabels.entries.map((kv) {
                final b = breakdown[kv.key];
                final cc = b == null ? Colors.grey : _bandColor(b);
                return Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: cc.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: cc.withValues(alpha: 0.35)),
                  ),
                  child: Text(
                    '${kv.value}: ${_formatBand(b)}',
                    style: TextStyle(
                      fontSize: 13,
                      color: cc,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _scoreRow(String label, int score) {
    final c = score >= 85
        ? Colors.green
        : score >= 70
            ? Colors.orange
            : Colors.red;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(fontSize: 14),
            ),
          ),
          SizedBox(
            width: 130,
            child: LinearProgressIndicator(
              value: (score / 100).clamp(0.0, 1.0),
              backgroundColor: Colors.grey.shade200,
              valueColor: AlwaysStoppedAnimation(c),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 42,
            child: Text(
              '$score',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: c,
              ),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }

  Widget _feedbackBox(String title, String body, Color colour) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colour.withValues(alpha: 0.25)),
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
          const SizedBox(height: 6),
          Text(body, style: const TextStyle(fontSize: 14, height: 1.45)),
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
                  Text(
                    '• ',
                    style: TextStyle(color: colour, fontSize: 14),
                  ),
                  Expanded(
                    child: Text(
                      item,
                      style: const TextStyle(
                        fontSize: 14,
                        height: 1.4,
                      ),
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
}
