import 'package:flutter/material.dart';

import '/core/di/injection_container.dart' as di;
import '/core/theme/app_theme.dart';
import '../../data/models/admin_models.dart';
import '../../data/repositories/admin_repository.dart';
import '../widgets/admin_stat_card.dart';
import '../widgets/admin_activity_chart.dart';
import '../widgets/admin_recent_users_list.dart';

class AdminDashboardPage extends StatefulWidget {
  const AdminDashboardPage({super.key});

  @override
  State<AdminDashboardPage> createState() => _AdminDashboardPageState();
}

class _AdminDashboardPageState extends State<AdminDashboardPage> {
  final AdminRepository _repo = di.sl<AdminRepository>();
  AdminDashboard? _dashboard;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<void> _loadDashboard() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final dashboard = await _repo.getDashboard();
      if (mounted) {
        setState(() {
          _dashboard = dashboard;
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
        title: const Text('Admin Dashboard'),
        backgroundColor: AppTheme.primaryColor,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadDashboard,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildContent(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 16),
            Text(
              'Failed to load dashboard',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadDashboard,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    final stats = _dashboard!.systemStats;
    return RefreshIndicator(
      onRefresh: _loadDashboard,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Overview Cards ────────────────────────────────
            Text(
              'Overview',
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.5,
              children: [
                AdminStatCard(
                  title: 'Total Users',
                  value: '${stats.totalUsers}',
                  icon: Icons.people,
                  color: Colors.blue,
                ),
                AdminStatCard(
                  title: 'Active (30d)',
                  value: '${stats.activeUsers}',
                  icon: Icons.trending_up,
                  color: Colors.green,
                ),
                AdminStatCard(
                  title: 'Premium',
                  value: '${stats.premiumUsers}',
                  icon: Icons.star,
                  color: Colors.amber,
                ),
                AdminStatCard(
                  title: 'New Today',
                  value: '${stats.newUsersToday}',
                  icon: Icons.person_add,
                  color: Colors.purple,
                ),
              ],
            ),

            const SizedBox(height: 12),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.5,
              children: [
                AdminStatCard(
                  title: 'Lessons',
                  value: '${stats.totalLessonsGenerated}',
                  icon: Icons.book,
                  color: Colors.teal,
                ),
                AdminStatCard(
                  title: 'Exercises',
                  value: '${stats.totalExercisesCompleted}',
                  icon: Icons.check_circle,
                  color: Colors.orange,
                ),
                AdminStatCard(
                  title: 'Avg Accuracy',
                  value: '${(stats.averageAccuracy * 100).toStringAsFixed(1)}%',
                  icon: Icons.analytics,
                  color: Colors.indigo,
                ),
                AdminStatCard(
                  title: 'New This Week',
                  value: '${stats.newUsersThisWeek}',
                  icon: Icons.calendar_today,
                  color: Colors.cyan,
                ),
              ],
            ),

            const SizedBox(height: 24),

            // ── Daily Activity ───────────────────────────────
            if (_dashboard!.dailyActivity.isNotEmpty) ...[
              Text(
                'Daily Activity (Last 7 Days)',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              AdminActivityChart(activity: _dashboard!.dailyActivity),
              const SizedBox(height: 24),
            ],

            // ── Recent Users ─────────────────────────────────
            if (_dashboard!.recentUsers.isNotEmpty) ...[
              Text(
                'Recent Users',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              AdminRecentUsersList(users: _dashboard!.recentUsers),
            ],
          ],
        ),
      ),
    );
  }
}
