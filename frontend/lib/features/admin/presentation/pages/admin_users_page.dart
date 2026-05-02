import 'package:flutter/material.dart';

import '/core/di/injection_container.dart' as di;
import '/core/theme/app_theme.dart';
import '../../data/models/admin_models.dart';
import '../../data/repositories/admin_repository.dart';

class AdminUsersPage extends StatefulWidget {
  const AdminUsersPage({super.key});

  @override
  State<AdminUsersPage> createState() => _AdminUsersPageState();
}

class _AdminUsersPageState extends State<AdminUsersPage> {
  final AdminRepository _repo = di.sl<AdminRepository>();
  List<AdminUserListItem> _users = [];
  int _total = 0;
  int _page = 1;
  final int _perPage = 20;
  bool _isLoading = true;
  String? _error;

  final _searchController = TextEditingController();
  String _sortBy = 'created_at';
  String _sortOrder = 'desc';

  @override
  void initState() {
    super.initState();
    _loadUsers();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadUsers() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final result = await _repo.getUsers(
        page: _page,
        perPage: _perPage,
        search: _searchController.text.isEmpty ? null : _searchController.text,
        sortBy: _sortBy,
        sortOrder: _sortOrder,
      );
      if (mounted) {
        setState(() {
          _users = result.users;
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

  void _onSearch() {
    _page = 1;
    _loadUsers();
  }

  int get _totalPages => (_total / _perPage).ceil().clamp(1, 9999);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('User Management'),
        backgroundColor: AppTheme.primaryColor,
        foregroundColor: Colors.white,
      ),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    decoration: InputDecoration(
                      hintText: 'Search by email, username, or name...',
                      prefixIcon: const Icon(Icons.search),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
                    ),
                    onSubmitted: (_) => _onSearch(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.search),
                  onPressed: _onSearch,
                ),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.sort),
                  tooltip: 'Sort by',
                  onSelected: (value) {
                    setState(() {
                      if (_sortBy == value) {
                        _sortOrder = _sortOrder == 'asc' ? 'desc' : 'asc';
                      } else {
                        _sortBy = value;
                        _sortOrder = 'desc';
                      }
                    });
                    _loadUsers();
                  },
                  itemBuilder: (context) => [
                    const PopupMenuItem(value: 'created_at', child: Text('Join Date')),
                    const PopupMenuItem(value: 'last_login', child: Text('Last Login')),
                    const PopupMenuItem(value: 'email', child: Text('Email')),
                    const PopupMenuItem(value: 'username', child: Text('Username')),
                  ],
                ),
              ],
            ),
          ),

          // Content
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text('Error: $_error'),
                            const SizedBox(height: 8),
                            ElevatedButton(
                              onPressed: _loadUsers,
                              child: const Text('Retry'),
                            ),
                          ],
                        ),
                      )
                    : _users.isEmpty
                        ? const Center(child: Text('No users found'))
                        : ListView.builder(
                            itemCount: _users.length,
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemBuilder: (context, index) =>
                                _buildUserTile(_users[index]),
                          ),
          ),

          // Pagination
          if (!_isLoading && _total > _perPage)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(
                    icon: const Icon(Icons.chevron_left),
                    onPressed: _page > 1
                        ? () {
                            setState(() => _page--);
                            _loadUsers();
                          }
                        : null,
                  ),
                  Text('Page $_page of $_totalPages'),
                  IconButton(
                    icon: const Icon(Icons.chevron_right),
                    onPressed: _page < _totalPages
                        ? () {
                            setState(() => _page++);
                            _loadUsers();
                          }
                        : null,
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildUserTile(AdminUserListItem user) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: user.isActive
              ? AppTheme.primaryColor.withValues(alpha: 0.15)
              : Colors.grey.withValues(alpha: 0.15),
          child: Text(
            (user.fullName ?? user.username).isNotEmpty
                ? (user.fullName ?? user.username)[0].toUpperCase()
                : '?',
            style: TextStyle(
              color: user.isActive ? AppTheme.primaryColor : Colors.grey,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        title: Row(
          children: [
            Expanded(
              child: Text(
                user.fullName ?? user.username,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (user.isAdmin)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  user.adminRole ?? 'Admin',
                  style: TextStyle(fontSize: 10, color: Colors.red.shade700),
                ),
              ),
            if (user.isPremium)
              Padding(
                padding: const EdgeInsets.only(left: 4),
                child: Icon(Icons.star, size: 16, color: Colors.amber.shade700),
              ),
          ],
        ),
        subtitle: Text(
          '${user.email}  |  ${user.currentLevel ?? "?"}  |  ${user.isActive ? "Active" : "Inactive"}',
          style: const TextStyle(fontSize: 12),
        ),
        trailing: PopupMenuButton<String>(
          onSelected: (action) => _handleUserAction(action, user),
          itemBuilder: (context) => [
            const PopupMenuItem(value: 'view', child: Text('View Details')),
            if (user.isActive)
              const PopupMenuItem(
                value: 'deactivate',
                child: Text('Deactivate', style: TextStyle(color: Colors.orange)),
              )
            else
              const PopupMenuItem(
                value: 'activate',
                child: Text('Activate', style: TextStyle(color: Colors.green)),
              ),
          ],
        ),
        onTap: () => _showUserDetail(user.id),
      ),
    );
  }

  Future<void> _handleUserAction(String action, AdminUserListItem user) async {
    if (action == 'view') {
      _showUserDetail(user.id);
    } else if (action == 'deactivate') {
      final confirm = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Deactivate User?'),
          content: Text('Deactivate ${user.email}?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              style: TextButton.styleFrom(foregroundColor: Colors.orange),
              child: const Text('Deactivate'),
            ),
          ],
        ),
      );
      if (confirm == true) {
        try {
          await _repo.deactivateUser(user.id);
          _loadUsers();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('User deactivated')),
            );
          }
        } catch (e) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Failed: $e')),
            );
          }
        }
      }
    } else if (action == 'activate') {
      try {
        await _repo.activateUser(user.id);
        _loadUsers();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('User activated')),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed: $e')),
          );
        }
      }
    }
  }

  Future<void> _showUserDetail(int userId) async {
    try {
      final detail = await _repo.getUserDetail(userId);
      if (!mounted) return;
      showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        builder: (ctx) => DraggableScrollableSheet(
          initialChildSize: 0.7,
          minChildSize: 0.4,
          maxChildSize: 0.9,
          expand: false,
          builder: (_, controller) => SingleChildScrollView(
            controller: controller,
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.grey[300],
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  detail.fullName ?? detail.username,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                Text(detail.email, style: TextStyle(color: Colors.grey[600])),
                const Divider(height: 32),
                _detailRow('Username', detail.username),
                _detailRow('Level', detail.currentLevel ?? '?'),
                _detailRow('Active', detail.isActive ? 'Yes' : 'No'),
                _detailRow('Premium', detail.isPremium ? 'Yes' : 'No'),
                _detailRow('Admin', detail.isAdmin ? (detail.adminRole ?? 'Yes') : 'No'),
                _detailRow('Onboarding', detail.onboardingCompleted ? 'Completed' : 'Pending'),
                _detailRow('Study Time', '${detail.totalStudyTimeMinutes} min'),
                _detailRow('Exercises', '${detail.totalExercisesCompleted}'),
                _detailRow('Accuracy', '${(detail.averageAccuracy * 100).toStringAsFixed(1)}%'),
                _detailRow('Streak', '${detail.currentStreakDays} days'),
                _detailRow('Daily Goal', '${detail.dailyGoalMinutes} min'),
                if (detail.lastLogin != null)
                  _detailRow('Last Login', _formatDate(detail.lastLogin!)),
                if (detail.createdAt != null)
                  _detailRow('Joined', _formatDate(detail.createdAt!)),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load user detail: $e')),
        );
      }
    }
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
          Text(value),
        ],
      ),
    );
  }

  String _formatDate(String dateStr) {
    try {
      final dt = DateTime.parse(dateStr).toLocal();
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return dateStr;
    }
  }
}
