import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '/core/constants/app_constants.dart';
import '/core/di/injection_container.dart' as di;
import '/core/network/api_client.dart';
import '/core/services/auth_service.dart';
import '/core/storage/secure_storage.dart';
import '/core/theme/app_theme.dart';
import '/core/widgets/app_bottom_nav_bar.dart';
import '/core/widgets/error_dialog.dart';
import '/core/widgets/loading_overlay.dart';

void showErrorDialog(
  BuildContext context, {
  required String title,
  required String message,
}) {
  showDialog(
    context: context,
    builder: (context) => ErrorDialog(title: title, message: message),
  );
}

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage>
    with TickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  late ApiClient _apiClient;

  final AuthService _authService = di.sl<AuthService>();
  Map<String, dynamic>? _userData;
  Map<String, dynamic>? _statistics;
  bool _isLoading = true;
  bool _isLoggingOut = false;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient(SecureStorage());

    _animationController = AnimationController(
      duration: AppConstants.longAnimation,
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeInOut),
    );

    _slideAnimation =
        Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero).animate(
          CurvedAnimation(
            parent: _animationController,
            curve: Curves.easeOutCubic,
          ),
        );

    _animationController.forward();
    _loadUserData();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  Future<void> _loadUserData() async {
    try {
      setState(() => _isLoading = true);
      final userData = await _authService.getUserData();

      // Also fetch statistics
      Map<String, dynamic>? stats;
      try {
        final response = await _apiClient.get('/users/profile/statistics');
        if (response.statusCode == 200) {
          stats = response.data;
        }
      } catch (e) {
        if (kDebugMode) {
          print('Failed to load statistics: $e');
        }
      }

      setState(() {
        _userData = userData;
        _statistics = stats;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        showErrorDialog(
          context,
          title: 'Error Loading Profile',
          message: 'Failed to load user data. Please try again.',
        );
      }
    }
  }

  Future<void> _handleLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Logout'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      setState(() => _isLoggingOut = true);

      try {
        await _authService.logout();
        if (mounted) {
          context.go('/welcome');
        }
      } catch (e) {
        setState(() => _isLoggingOut = false);
        if (mounted) {
          showErrorDialog(
            context,
            title: 'Logout Error',
            message: 'Failed to logout. Please try again.',
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      bottomNavigationBar: const AppBottomNavBar(
        currentIndex: 2,
        useDarkTheme: false,
      ),
      body: Stack(
        children: [
          FadeTransition(
            opacity: _fadeAnimation,
            child: SlideTransition(
              position: _slideAnimation,
              child: CustomScrollView(
                slivers: [
                  SliverAppBar(
                    expandedHeight: 200,
                    floating: false,
                    pinned: true,
                    flexibleSpace: FlexibleSpaceBar(
                      background: Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              AppTheme.primaryColor,
                              AppTheme.primaryColor.withValues(alpha: 0.8),
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.person,
                            size: 80,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                    title: const Text('Profile'),
                    centerTitle: true,
                  ),
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_isLoading)
                            const Center(child: CircularProgressIndicator())
                          else if (_userData != null)
                            _buildProfileContent()
                          else
                            _buildErrorContent(),

                          const SizedBox(height: 32),
                          _buildSettingsSection(),

                          const SizedBox(height: 32),
                          _buildLogoutSection(),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (_isLoggingOut) LoadingOverlay(message: 'Logging out...'),
        ],
      ),
    );
  }

  Widget _buildProfileContent() {
    final user = _userData!;
    final fullName = user['full_name'] ?? user['fullName'] ?? 'User';
    final email = user['email'] ?? '';
    final username = user['username'] ?? '';
    final currentLevel = user['current_level'] ?? user['currentLevel'] ?? 'A1';
    final joinDate = user['created_at'] ?? user['createdAt'];

    // Get statistics data
    final overallProgress = _statistics?['overall_progress'] ?? {};
    final totalStudyTime = overallProgress['total_study_time_minutes'] ?? 0;
    final totalExercises = overallProgress['total_exercises_completed'] ?? 0;
    final currentStreak = overallProgress['current_streak_days'] ?? 0;
    final totalPoints = overallProgress['total_points_earned'] ?? 0;

    return Column(
      children: [
        Card(
          elevation: 4,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    CircleAvatar(
                      radius: 40,
                      backgroundColor: AppTheme.primaryColor.withValues(
                        alpha: 0.1,
                      ),
                      child: Text(
                        fullName.isNotEmpty ? fullName[0].toUpperCase() : 'U',
                        style: TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.primaryColor,
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            fullName,
                            style: Theme.of(context).textTheme.headlineSmall
                                ?.copyWith(fontWeight: FontWeight.bold),
                          ),
                          Text(
                            email,
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(color: Colors.grey[600]),
                          ),
                          if (username.isNotEmpty)
                            Text(
                              '@$username',
                              style: Theme.of(context).textTheme.bodySmall
                                  ?.copyWith(color: Colors.grey[500]),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                _buildProfileItem(
                  icon: Icons.school,
                  label: 'Current Level',
                  value: currentLevel.toString().toUpperCase(),
                ),
                if (joinDate != null) ...[
                  const SizedBox(height: 16),
                  _buildProfileItem(
                    icon: Icons.calendar_today,
                    label: 'Member Since',
                    value: _formatDate(joinDate),
                  ),
                ],
              ],
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Statistics Cards
        if (_statistics != null) ...[
          Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  icon: Icons.local_fire_department,
                  iconColor: Colors.orange,
                  value: '$currentStreak',
                  label: 'Day Streak',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  icon: Icons.timer,
                  iconColor: Colors.blue,
                  value: _formatMinutes(totalStudyTime),
                  label: 'Study Time',
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _buildStatCard(
                  icon: Icons.check_circle,
                  iconColor: Colors.green,
                  value: '$totalExercises',
                  label: 'Exercises',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildStatCard(
                  icon: Icons.star,
                  iconColor: Colors.amber,
                  value: '$totalPoints',
                  label: 'Total Points',
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  String _formatMinutes(int minutes) {
    if (minutes < 60) return '${minutes}m';
    final hours = minutes ~/ 60;
    final mins = minutes % 60;
    if (mins == 0) return '${hours}h';
    return '${hours}h ${mins}m';
  }

  Widget _buildStatCard({
    required IconData icon,
    required Color iconColor,
    required String value,
    required String label,
  }) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: iconColor, size: 28),
            const SizedBox(height: 8),
            Text(
              value,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProfileItem({
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Row(
      children: [
        Icon(icon, size: 20, color: AppTheme.primaryColor),
        const SizedBox(width: 12),
        Text(
          '$label:',
          style: Theme.of(
            context,
          ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
        ),
        const SizedBox(width: 8),
        Text(value, style: Theme.of(context).textTheme.bodyMedium),
      ],
    );
  }

  Widget _buildErrorContent() {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.orange),
            const SizedBox(height: 16),
            Text(
              'Unable to load profile data',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Please check your connection and try again.',
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadUserData,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSettingsSection() {
    final bool isAdmin = _userData?['is_admin'] == true;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Admin Panel (visible only to admin users) ────────
        if (isAdmin) ...[
          Text(
            'Admin',
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 16),
          _buildSettingsItem(
            icon: Icons.workspace_premium,
            iconColor: const Color(0xFF5EEAD4),
            title: 'Upgrade to SELM Pro',
            subtitle: 'Unlimited practice • 7-day free trial • Cancel anytime',
            onTap: () => context.push('/paywall'),
          ),
          _buildSettingsItem(
            icon: Icons.admin_panel_settings,
            title: 'Admin Panel',
            subtitle: 'Manage users, reports and app settings',
            onTap: () {
              context.push('/admin');
            },
            iconColor: Colors.red,
          ),
          const SizedBox(height: 24),
        ],

        Text(
          'Learning',
          style: Theme.of(
            context,
          ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        _buildSettingsItem(
          icon: Icons.quiz,
          title: 'Take Assessment',
          subtitle: 'Evaluate your English level with our AI assessment',
          onTap: () {
            context.go('/onboarding');
          },
          iconColor: Colors.orange,
        ),
        _buildSettingsItem(
          icon: Icons.route,
          title: 'Learning Journey',
          subtitle: 'View your personalized learning path',
          onTap: () {
            context.go('/journey');
          },
          iconColor: Colors.green,
        ),
        const SizedBox(height: 24),
        Text(
          'Settings',
          style: Theme.of(
            context,
          ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        _buildSettingsItem(
          icon: Icons.notifications,
          title: 'Notifications',
          subtitle: 'Manage your notification preferences',
          onTap: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Notifications settings coming soon!'),
              ),
            );
          },
        ),
        _buildSettingsItem(
          icon: Icons.language,
          title: 'Language',
          subtitle: 'Change app language',
          onTap: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Language settings coming soon!')),
            );
          },
        ),
        _buildSettingsItem(
          icon: Icons.help_outline,
          title: 'Help & Support',
          subtitle: 'Get help and contact support',
          onTap: () {
            context.push('/contact-support');
          },
          iconColor: Colors.blue,
        ),
        const SizedBox(height: 24),
        Text(
          'Legal',
          style: Theme.of(
            context,
          ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        _buildSettingsItem(
          icon: Icons.privacy_tip,
          title: 'Privacy Policy',
          subtitle: 'View our privacy policy',
          onTap: () {
            context.push('/privacy-policy');
          },
          iconColor: Colors.teal,
        ),
        _buildSettingsItem(
          icon: Icons.description,
          title: 'Terms of Service',
          subtitle: 'View terms and conditions',
          onTap: () {
            context.push('/terms-of-service');
          },
          iconColor: Colors.indigo,
        ),
      ],
    );
  }

  Widget _buildSettingsItem({
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
    Color? iconColor,
  }) {
    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: Icon(icon, color: iconColor ?? AppTheme.primaryColor),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Widget _buildLogoutSection() {
    return Column(
      children: [
        Card(
          elevation: 2,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          child: ListTile(
            leading: const Icon(Icons.logout, color: Colors.red),
            title: const Text('Logout', style: TextStyle(color: Colors.red)),
            subtitle: const Text('Sign out of your account'),
            trailing: const Icon(Icons.chevron_right, color: Colors.red),
            onTap: _handleLogout,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        const SizedBox(height: 16),
        Card(
          elevation: 2,
          color: Colors.red.shade50,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          child: ListTile(
            leading: Icon(Icons.delete_forever, color: Colors.red.shade700),
            title: Text(
              'Delete Account',
              style: TextStyle(color: Colors.red.shade700),
            ),
            subtitle: Text(
              'Permanently delete your account and data',
              style: TextStyle(color: Colors.red.shade400),
            ),
            trailing: Icon(Icons.chevron_right, color: Colors.red.shade700),
            onTap: _handleDeleteAccount,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
      ],
    );
  }

  Future<void> _handleDeleteAccount() async {
    // First confirmation dialog
    final firstConfirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 28),
            SizedBox(width: 12),
            Text('Delete Account?'),
          ],
        ),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'This action will permanently delete your account and all associated data.',
              style: TextStyle(fontSize: 16),
            ),
            SizedBox(height: 16),
            Text(
              'What will be deleted:',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 8),
            Text('• Your profile and settings'),
            Text('• Learning progress and statistics'),
            Text('• Achievements and streaks'),
            Text('• All personal data'),
            SizedBox(height: 16),
            Text(
              'You can register again with the same email address.',
              style: TextStyle(color: Colors.green, fontStyle: FontStyle.italic),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('Continue'),
          ),
        ],
      ),
    );

    if (firstConfirm != true || !mounted) return;

    // Second confirmation dialog - more serious
    final finalConfirm = await showDialog<bool>(
      // ignore: use_build_context_synchronously
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Colors.red.shade50,
        title: Row(
          children: [
            Icon(Icons.delete_forever, color: Colors.red.shade700, size: 28),
            const SizedBox(width: 12),
            Text(
              'Final Confirmation',
              style: TextStyle(color: Colors.red.shade700),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Are you absolutely sure?',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: Colors.red.shade700,
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'This cannot be undone. All your data will be permanently removed.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('No, Keep My Account'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red.shade700,
              foregroundColor: Colors.white,
            ),
            child: const Text('Yes, Delete Forever'),
          ),
        ],
      ),
    );

    if (finalConfirm != true) return;

    // Perform deletion
    setState(() => _isLoggingOut = true);

    try {
      final response = await _apiClient.delete(
        '/users/account',
        queryParameters: {'confirm_deletion': 'true'},
      );

      if (response.statusCode == 200) {
        // Clear local data and logout
        await _authService.logout();
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Your account has been deleted. You can register again anytime.'),
              backgroundColor: Colors.green,
              duration: Duration(seconds: 3),
            ),
          );
          context.go('/welcome');
        }
      } else {
        throw Exception('Failed to delete account');
      }
    } catch (e) {
      setState(() => _isLoggingOut = false);
      if (mounted) {
        showErrorDialog(
          context,
          title: 'Delete Failed',
          message: 'Failed to delete your account. Please try again or contact support.',
        );
      }
    }
  }

  String _formatDate(dynamic date) {
    if (date == null) return 'Unknown';

    try {
      if (date is String) {
        final parsed = DateTime.parse(date).toLocal();
        return '${parsed.day}/${parsed.month}/${parsed.year}';
      }
    } catch (e) {
      // Ignore parsing errors
    }

    return 'Unknown';
  }
}
