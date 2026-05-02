import 'package:flutter/material.dart';

import '/core/di/injection_container.dart' as di;
import '/core/theme/app_theme.dart';
import '../../data/repositories/admin_repository.dart';

class AdminSettingsPage extends StatefulWidget {
  const AdminSettingsPage({super.key});

  @override
  State<AdminSettingsPage> createState() => _AdminSettingsPageState();
}

class _AdminSettingsPageState extends State<AdminSettingsPage> {
  final AdminRepository _repo = di.sl<AdminRepository>();
  final TextEditingController _freeCefrLevelsController = TextEditingController();
  final TextEditingController _freeModulesController = TextEditingController();
  final TextEditingController _freeLessonsQuotaController = TextEditingController();
  Map<String, dynamic>? _settings;
  bool _isLoading = true;
  String? _error;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  @override
  void dispose() {
    _freeCefrLevelsController.dispose();
    _freeModulesController.dispose();
    _freeLessonsQuotaController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final settings = await _repo.getAllSettings();
      final payment = settings['payment'] as Map<String, dynamic>? ?? {};
      final freeLevels = (payment['free_cefr_levels'] as List<dynamic>? ?? const [])
          .map((e) => e.toString())
          .toList();
      final freeModules = (payment['free_modules'] as List<dynamic>? ?? const [])
          .map((e) => e.toString())
          .toList();
      final quota = payment['free_lessons_quota'];

      _freeCefrLevelsController.text = freeLevels.isNotEmpty ? freeLevels.join(', ') : 'A1';
      _freeModulesController.text = freeModules.isNotEmpty ? freeModules.join(', ') : 'reading';
      _freeLessonsQuotaController.text = (quota ?? 7).toString();

      if (mounted) {
        setState(() {
          _settings = settings;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('App Settings'),
        backgroundColor: AppTheme.primaryColor,
        foregroundColor: Colors.white,
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadSettings),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text('Error: $_error'),
                      const SizedBox(height: 8),
                      ElevatedButton(onPressed: _loadSettings, child: const Text('Retry')),
                    ],
                  ),
                )
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    final payment = _settings?['payment'] as Map<String, dynamic>? ?? {};
    final content = _settings?['content'] as Map<String, dynamic>? ?? {};
    final features = _settings?['features'] as Map<String, dynamic>? ?? {};

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Payment Settings ──────────────────────────────
          _sectionHeader('Payment'),
          _switchTile(
            'Payment Enabled',
            'Enable the payment system',
            payment['payment_enabled'] ?? false,
            (val) => _updatePayment({'payment_enabled': val}),
          ),
          _switchTile(
            'Content Lock',
            'Lock content behind payment',
            payment['content_lock_enabled'] ?? false,
            (val) => _updatePayment({'content_lock_enabled': val}),
          ),
          _textSettingTile(
            title: 'Free CEFR Levels',
            subtitle: 'Comma separated (e.g. A1, A2)',
            controller: _freeCefrLevelsController,
            onSave: () {
              final values = _freeCefrLevelsController.text
                  .split(',')
                  .map((e) => e.trim().toUpperCase())
                  .where((e) => e.isNotEmpty)
                  .toList();
              _updatePayment({'free_cefr_levels': values});
            },
          ),
          _textSettingTile(
            title: 'Free Modules',
            subtitle: 'Comma separated (e.g. reading, grammar)',
            controller: _freeModulesController,
            onSave: () {
              final values = _freeModulesController.text
                  .split(',')
                  .map((e) => e.trim().toLowerCase())
                  .where((e) => e.isNotEmpty)
                  .toList();
              _updatePayment({'free_modules': values});
            },
          ),
          _textSettingTile(
            title: 'Free Lessons Quota',
            subtitle: 'Completed free lessons before payment is required',
            controller: _freeLessonsQuotaController,
            keyboardType: TextInputType.number,
            onSave: () {
              final parsed = int.tryParse(_freeLessonsQuotaController.text.trim());
              if (parsed == null || parsed < 0) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Please enter a valid non-negative number')),
                );
                return;
              }
              _updatePayment({'free_lessons_quota': parsed});
            },
          ),

          const SizedBox(height: 24),

          // ── Content Settings ──────────────────────────────
          _sectionHeader('Content'),
          _infoTile('Max Daily Exercises', '${content['max_daily_exercises'] ?? 50}'),
          _switchTile(
            'AI Feedback',
            'Enable AI-powered feedback',
            content['ai_feedback_enabled'] ?? true,
            (val) => _updateContent({'ai_feedback_enabled': val}),
          ),

          const SizedBox(height: 24),

          // ── Feature Settings ──────────────────────────────
          _sectionHeader('Features'),
          _switchTile(
            'Speech Recognition',
            'Enable speech recognition features',
            features['speech_recognition_enabled'] ?? true,
            (val) => _updateFeatures({'speech_recognition_enabled': val}),
          ),
          _switchTile(
            'Gamification',
            'Enable gamification features',
            features['gamification_enabled'] ?? true,
            (val) => _updateFeatures({'gamification_enabled': val}),
          ),

          if (_isSaving)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            ),
        ],
      ),
    );
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _switchTile(String title, String subtitle, bool value, ValueChanged<bool> onChanged) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: SwitchListTile(
        title: Text(title),
        subtitle: Text(subtitle),
        value: value,
        onChanged: _isSaving ? null : onChanged,
      ),
    );
  }

  Widget _infoTile(String title, String value) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        title: Text(title),
        trailing: Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _textSettingTile({
    required String title,
    required String subtitle,
    required TextEditingController controller,
    required VoidCallback onSave,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 2),
            Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: controller,
                    keyboardType: keyboardType,
                    enabled: !_isSaving,
                    decoration: const InputDecoration(
                      isDense: true,
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                IconButton(
                  onPressed: _isSaving ? null : onSave,
                  icon: const Icon(Icons.save),
                  tooltip: 'Save',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _updatePayment(Map<String, dynamic> data) async {
    setState(() => _isSaving = true);
    try {
      await _repo.updatePaymentSettings(data);
      await _loadSettings();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Payment settings updated')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e')),
        );
      }
    }
    if (mounted) setState(() => _isSaving = false);
  }

  Future<void> _updateContent(Map<String, dynamic> data) async {
    setState(() => _isSaving = true);
    try {
      await _repo.updateContentSettings(data);
      await _loadSettings();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Content settings updated')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e')),
        );
      }
    }
    if (mounted) setState(() => _isSaving = false);
  }

  Future<void> _updateFeatures(Map<String, dynamic> data) async {
    setState(() => _isSaving = true);
    try {
      await _repo.updateFeatureSettings(data);
      await _loadSettings();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Feature settings updated')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e')),
        );
      }
    }
    if (mounted) setState(() => _isSaving = false);
  }
}
