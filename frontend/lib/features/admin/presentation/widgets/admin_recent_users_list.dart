import 'package:flutter/material.dart';

import '/core/theme/app_theme.dart';
import '../../data/models/admin_models.dart';

/// Displays the most recently registered users in a compact list.
/// Used on the admin dashboard page.
class AdminRecentUsersList extends StatelessWidget {
  final List<AdminUserListItem> users;

  const AdminRecentUsersList({super.key, required this.users});

  @override
  Widget build(BuildContext context) {
    if (users.isEmpty) {
      return const SizedBox.shrink();
    }

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: ListView.separated(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: users.length,
        separatorBuilder: (_, a) => const Divider(height: 1),
        itemBuilder: (context, index) => _buildUserTile(context, users[index]),
      ),
    );
  }

  Widget _buildUserTile(BuildContext context, AdminUserListItem user) {
    final displayName = (user.fullName != null && user.fullName!.isNotEmpty)
        ? user.fullName!
        : user.username;
    final initial =
        displayName.isNotEmpty ? displayName[0].toUpperCase() : '?';

    String subtitle = user.email;
    if (user.createdAt != null) {
      try {
        final dt = DateTime.parse(user.createdAt!).toLocal();
        subtitle += '  |  ${dt.day}/${dt.month}/${dt.year}';
      } catch (_) {}
    }

    return ListTile(
      dense: true,
      leading: CircleAvatar(
        radius: 18,
        backgroundColor: AppTheme.primaryColor.withValues(alpha: 0.12),
        child: Text(
          initial,
          style: TextStyle(
            color: AppTheme.primaryColor,
            fontWeight: FontWeight.bold,
            fontSize: 14,
          ),
        ),
      ),
      title: Row(
        children: [
          Expanded(
            child: Text(
              displayName,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
            ),
          ),
          if (user.isPremium)
            Padding(
              padding: const EdgeInsets.only(left: 4),
              child: Icon(Icons.star, size: 14, color: Colors.amber.shade700),
            ),
          if (!user.isActive)
            Padding(
              padding: const EdgeInsets.only(left: 4),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  'Inactive',
                  style:
                      TextStyle(fontSize: 9, color: Colors.red.shade700),
                ),
              ),
            ),
        ],
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(fontSize: 11, color: Colors.grey[600]),
        overflow: TextOverflow.ellipsis,
      ),
      trailing: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: Colors.blue.shade50,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          user.currentLevel ?? '?',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: Colors.blue.shade700,
          ),
        ),
      ),
    );
  }
}
