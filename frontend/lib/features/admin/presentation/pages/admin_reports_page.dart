import 'package:flutter/material.dart';

import '/core/di/injection_container.dart' as di;
import '/core/theme/app_theme.dart';
import '../../data/models/admin_models.dart';
import '../../data/repositories/admin_repository.dart';

class AdminReportsPage extends StatefulWidget {
  const AdminReportsPage({super.key});

  @override
  State<AdminReportsPage> createState() => _AdminReportsPageState();
}

class _AdminReportsPageState extends State<AdminReportsPage> {
  final AdminRepository _repo = di.sl<AdminRepository>();
  List<UserActivityReport> _activities = [];
  // ignore: unused_field
  int _total = 0;
  final int _page = 1;
  final int _perPage = 20;
  bool _isLoading = true;
  String? _error;
  String _selectedPeriod = 'weekly';

  // System report data
  Map<String, dynamic>? _reportData;
  bool _isLoadingReport = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    await Future.wait([
      _loadActivityReports(),
      _loadSystemReport(),
    ]);
  }

  Future<void> _loadActivityReports() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final result = await _repo.getActivityReports(
        page: _page,
        perPage: _perPage,
      );
      if (mounted) {
        setState(() {
          _activities = result.activities;
          _total = result.total;
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

  Future<void> _loadSystemReport() async {
    setState(() => _isLoadingReport = true);
    try {
      final data = await _repo.getSystemReport(period: _selectedPeriod);
      if (mounted) {
        setState(() {
          _reportData = data;
          _isLoadingReport = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _isLoadingReport = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Reports'),
          backgroundColor: AppTheme.primaryColor,
          foregroundColor: Colors.white,
          bottom: const TabBar(
            indicatorColor: Colors.white,
            labelColor: Colors.white,
            unselectedLabelColor: Colors.white70,
            tabs: [
              Tab(text: 'System Report'),
              Tab(text: 'User Activity'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _buildSystemReport(),
            _buildUserActivity(),
          ],
        ),
      ),
    );
  }

  Widget _buildSystemReport() {
    return Column(
      children: [
        // Period selector
        Padding(
          padding: const EdgeInsets.all(16),
          child: SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'daily', label: Text('Daily')),
              ButtonSegment(value: 'weekly', label: Text('Weekly')),
              ButtonSegment(value: 'monthly', label: Text('Monthly')),
            ],
            selected: {_selectedPeriod},
            onSelectionChanged: (v) {
              setState(() => _selectedPeriod = v.first);
              _loadSystemReport();
            },
          ),
        ),
        Expanded(
          child: _isLoadingReport
              ? const Center(child: CircularProgressIndicator())
              : _reportData == null
                  ? const Center(child: Text('No report data'))
                  : SingleChildScrollView(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _reportCard('Generated At', _reportData!['generated_at'] ?? '-'),
                          _reportCard('Period', _reportData!['period'] ?? '-'),
                          if (_reportData!['stats'] != null) ...[
                            const SizedBox(height: 16),
                            Text('Stats', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            ..._buildStatsCards(_reportData!['stats']),
                          ],
                          if (_reportData!['daily_activity'] != null) ...[
                            const SizedBox(height: 16),
                            Text('Daily Activity', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            ...(_reportData!['daily_activity'] as List)
                                .map((d) => Card(
                                      margin: const EdgeInsets.only(bottom: 8),
                                      child: ListTile(
                                        title: Text(d['date'] ?? ''),
                                        subtitle: Text(
                                          'Active: ${d['active_users']} | New: ${d['new_registrations']} | Lessons: ${d['lessons_completed']} | Exercises: ${d['exercises_completed']}',
                                          style: const TextStyle(fontSize: 12),
                                        ),
                                      ),
                                    )),
                          ],
                        ],
                      ),
                    ),
        ),
      ],
    );
  }

  Widget _reportCard(String label, dynamic value) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Text(label),
        trailing: Text('$value', style: const TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }

  List<Widget> _buildStatsCards(Map<String, dynamic> stats) {
    return stats.entries
        .map((e) => Card(
              margin: const EdgeInsets.only(bottom: 4),
              child: ListTile(
                dense: true,
                title: Text(_formatKey(e.key)),
                trailing: Text(
                  '${e.value}',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ))
        .toList();
  }

  String _formatKey(String key) {
    return key
        .replaceAll('_', ' ')
        .split(' ')
        .map((w) => w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : '')
        .join(' ');
  }

  Widget _buildUserActivity() {
    if (_isLoading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('Error: $_error'),
            ElevatedButton(onPressed: _loadActivityReports, child: const Text('Retry')),
          ],
        ),
      );
    }
    if (_activities.isEmpty) return const Center(child: Text('No activity data'));

    return RefreshIndicator(
      onRefresh: _loadActivityReports,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _activities.length,
        itemBuilder: (context, index) {
          final a = _activities[index];
          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          a.username,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          a.currentLevel ?? '?',
                          style: TextStyle(color: Colors.blue.shade700, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(a.email, style: TextStyle(color: Colors.grey[600], fontSize: 12)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      _activityChip(Icons.timer, '${a.totalStudyTimeMinutes}m'),
                      _activityChip(Icons.check_circle, '${a.totalExercisesCompleted}'),
                      _activityChip(Icons.analytics, '${(a.averageAccuracy * 100).toStringAsFixed(0)}%'),
                      _activityChip(Icons.local_fire_department, '${a.currentStreakDays}d'),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _activityChip(IconData icon, String value) {
    return Padding(
      padding: const EdgeInsets.only(right: 12),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.grey[600]),
          const SizedBox(width: 2),
          Text(value, style: TextStyle(fontSize: 12, color: Colors.grey[700])),
        ],
      ),
    );
  }
}
