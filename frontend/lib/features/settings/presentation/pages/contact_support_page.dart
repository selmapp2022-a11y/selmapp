import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../../core/theme/app_theme.dart';

/// Contact and Support page with comprehensive contact information and support options
class ContactSupportPage extends StatelessWidget {
  const ContactSupportPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      appBar: AppBar(
        title: const Text('Help & Support'),
        backgroundColor: AppTheme.primaryColor,
        foregroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Center(
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      borderRadius: BorderRadius.circular(24),
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.primaryColor.withValues(alpha: 0.3),
                          blurRadius: 20,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.support_agent,
                      size: 56,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'How can we help you?',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimaryColor,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'We\'re here to help you succeed in your English learning journey',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppTheme.textSecondaryColor,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Quick Actions
            Text(
              'Quick Actions',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            const SizedBox(height: 16),
            
            _buildQuickActionCard(
              context,
              icon: Icons.email_outlined,
              title: 'Email Support',
              subtitle: 'Get help via email within 24 hours',
              color: Colors.blue,
              onTap: () => _launchEmail(context),
            ),
            const SizedBox(height: 12),
            
            _buildQuickActionCard(
              context,
              icon: Icons.phone_outlined,
              title: 'Call Us',
              subtitle: 'Speak with our support team',
              color: Colors.green,
              onTap: () => _launchPhone(context),
            ),
            const SizedBox(height: 12),
            
            _buildQuickActionCard(
              context,
              icon: Icons.quiz_outlined,
              title: 'FAQs',
              subtitle: 'Find answers to common questions',
              color: Colors.orange,
              onTap: () => _showFAQs(context),
            ),

            const SizedBox(height: 32),

            // Contact Information
            Text(
              'Contact Information',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            const SizedBox(height: 16),
            
            _buildContactCard(context),

            const SizedBox(height: 32),

            // Support Hours
            Text(
              'Support Hours',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            const SizedBox(height: 16),
            
            _buildSupportHoursCard(context),

            const SizedBox(height: 32),

            // Legal Links
            Text(
              'Legal',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimaryColor,
              ),
            ),
            const SizedBox(height: 16),
            
            _buildLegalCard(context),

            const SizedBox(height: 32),

            // App Info
            Center(
              child: Column(
                children: [
                  Text(
                    'Selm - Learn English Smartly',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textPrimaryColor,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Version 1.0.0',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondaryColor,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '© 2025 SELM MOBILE APPLICATION INC.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondaryColor,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildQuickActionCard(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTheme.textSecondaryColor,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right,
                color: Colors.grey[400],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContactCard(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            _buildContactItem(
              context,
              icon: Icons.email,
              label: 'Email',
              value: 'selmapp2022@gmail.com',
              onTap: () => _launchEmail(context),
              onLongPress: () => _copyToClipboard(context, 'selmapp2022@gmail.com'),
            ),
            const Divider(height: 24),
            _buildContactItem(
              context,
              icon: Icons.phone,
              label: 'Phone',
              value: '+1 (604) 717-8543',
              onTap: () => _launchPhone(context),
              onLongPress: () => _copyToClipboard(context, '+16047178543'),
            ),
            const Divider(height: 24),
            _buildContactItem(
              context,
              icon: Icons.business,
              label: 'Company',
              value: 'SELM MOBILE APPLICATION INC.',
            ),
            const Divider(height: 24),
            _buildContactItem(
              context,
              icon: Icons.location_on,
              label: 'Address',
              value: '1188 West Pender\nVancouver, BC, Canada\nV6E 0A2',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContactItem(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String value,
    VoidCallback? onTap,
    VoidCallback? onLongPress,
  }) {
    final content = Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppTheme.primaryColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, size: 20, color: AppTheme.primaryColor),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textSecondaryColor,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                value,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: onTap != null ? AppTheme.primaryColor : AppTheme.textPrimaryColor,
                  fontWeight: onTap != null ? FontWeight.w500 : null,
                ),
              ),
            ],
          ),
        ),
        if (onTap != null)
          Icon(
            Icons.open_in_new,
            size: 18,
            color: AppTheme.primaryColor,
          ),
      ],
    );

    if (onTap != null || onLongPress != null) {
      return InkWell(
        onTap: onTap,
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(8),
        child: content,
      );
    }
    return content;
  }

  Widget _buildSupportHoursCard(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            _buildHoursRow(context, 'Monday - Friday', '9:00 AM - 6:00 PM PST'),
            const SizedBox(height: 12),
            _buildHoursRow(context, 'Saturday', '10:00 AM - 4:00 PM PST'),
            const SizedBox(height: 12),
            _buildHoursRow(context, 'Sunday', 'Closed'),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, color: Colors.blue, size: 20),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Email support is available 24/7. We typically respond within 24 hours.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.blue[700],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHoursRow(BuildContext context, String day, String hours) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          day,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w500,
          ),
        ),
        Text(
          hours,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: hours == 'Closed' ? Colors.red : AppTheme.textSecondaryColor,
          ),
        ),
      ],
    );
  }

  Widget _buildLegalCard(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          ListTile(
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.teal.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.privacy_tip, color: Colors.teal, size: 20),
            ),
            title: const Text('Privacy Policy'),
            subtitle: const Text('How we handle your data'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/privacy-policy'),
          ),
          const Divider(height: 1, indent: 72),
          ListTile(
            leading: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.indigo.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.description, color: Colors.indigo, size: 20),
            ),
            title: const Text('Terms of Service'),
            subtitle: const Text('Terms and conditions'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push('/terms-of-service'),
          ),
        ],
      ),
    );
  }

  Future<void> _launchEmail(BuildContext context) async {
    // Capture messenger before async gap to avoid context issues
    final messenger = ScaffoldMessenger.of(context);
    
    final Uri emailUri = Uri(
      scheme: 'mailto',
      path: 'selmapp2022@gmail.com',
      queryParameters: {
        'subject': 'Selm App Support Request',
      },
    );
    
    try {
      if (await canLaunchUrl(emailUri)) {
        await launchUrl(emailUri);
      } else {
        _copyToClipboardWithMessenger(messenger, 'selmapp2022@gmail.com');
      }
    } catch (e) {
      _copyToClipboardWithMessenger(messenger, 'selmapp2022@gmail.com');
    }
  }

  Future<void> _launchPhone(BuildContext context) async {
    // Capture messenger before async gap to avoid context issues
    final messenger = ScaffoldMessenger.of(context);
    
    final Uri phoneUri = Uri(
      scheme: 'tel',
      path: '+16047178543',
    );
    
    try {
      if (await canLaunchUrl(phoneUri)) {
        await launchUrl(phoneUri);
      } else {
        _copyToClipboardWithMessenger(messenger, '+1 (604) 717-8543');
      }
    } catch (e) {
      _copyToClipboardWithMessenger(messenger, '+1 (604) 717-8543');
    }
  }

  void _copyToClipboard(BuildContext context, String text) {
    _copyToClipboardWithMessenger(ScaffoldMessenger.of(context), text);
  }

  void _copyToClipboardWithMessenger(ScaffoldMessengerState messenger, String text) {
    Clipboard.setData(ClipboardData(text: text));
    messenger.showSnackBar(
      SnackBar(
        content: Text('Copied to clipboard: $text'),
        duration: const Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _showFAQs(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (context, scrollController) => Padding(
          padding: const EdgeInsets.all(20),
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
              const SizedBox(height: 20),
              Text(
                'Frequently Asked Questions',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 20),
              Expanded(
                child: ListView(
                  controller: scrollController,
                  children: [
                    _buildFAQItem(
                      context,
                      'How do I reset my password?',
                      'Go to the login screen and tap "Forgot Password". Enter your email address and we\'ll send you a reset link.',
                    ),
                    _buildFAQItem(
                      context,
                      'How can I change my proficiency level?',
                      'Go to Profile > Take Assessment to retake the level assessment. Your learning path will be updated based on your new results.',
                    ),
                    _buildFAQItem(
                      context,
                      'Why isn\'t my audio working?',
                      'Make sure your device is not on silent mode and the volume is up. Also check that Selm has microphone permissions in your device settings.',
                    ),
                    _buildFAQItem(
                      context,
                      'How do I delete my account?',
                      'Go to Profile > scroll down to "Delete Account". This will permanently remove all your data. You can always create a new account with the same email.',
                    ),
                    _buildFAQItem(
                      context,
                      'How are points calculated?',
                      'You earn points for completing exercises correctly. The number of points depends on the difficulty level and exercise type. Points contribute to your overall progress.',
                    ),
                    _buildFAQItem(
                      context,
                      'Can I use Selm offline?',
                      'Some content is cached for offline use, but for the full experience including speaking exercises and AI feedback, an internet connection is required.',
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFAQItem(BuildContext context, String question, String answer) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ExpansionTile(
        title: Text(
          question,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        children: [
          Text(
            answer,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTheme.textSecondaryColor,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}

