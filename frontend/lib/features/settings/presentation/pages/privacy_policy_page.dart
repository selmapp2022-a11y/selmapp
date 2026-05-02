import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_theme.dart';

/// In-app Privacy Policy page that displays the full privacy policy
/// This allows users to view the privacy policy without leaving the app
class PrivacyPolicyPage extends StatelessWidget {
  const PrivacyPolicyPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      appBar: AppBar(
        title: const Text('Privacy Policy'),
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
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Icon(
                      Icons.privacy_tip,
                      size: 48,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Privacy Policy',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimaryColor,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Last Updated: December 28, 2024',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppTheme.textSecondaryColor,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Introduction
            _buildSection(
              context,
              null,
              'Welcome to Selm. This Privacy Policy explains how we collect, use, '
              'disclose, and safeguard your information when you use our mobile '
              'application Selm, an intelligent English language learning application.\n\n'
              'Please read this Privacy Policy carefully. By using the App, you agree '
              'to the collection and use of information in accordance with this policy.',
            ),

            // Section 1: Information We Collect
            _buildSectionTitle(context, '1. Information We Collect'),
            
            _buildSubsection(
              context,
              '1.1 Personal Information',
              'When you register for an account, we may collect:',
            ),
            _buildBulletList([
              'Account Information: Email address, username, and password',
              'Profile Information: Full name, current English proficiency level, and learning preferences',
              'Learning Data: Your progress, completed lessons, quiz scores, and study statistics',
            ]),

            _buildSubsection(
              context,
              '1.2 Audio Recordings',
              null,
            ),
            _buildHighlightBox(
              context,
              'Microphone Access',
              'Our App uses your device\'s microphone to record audio for speaking '
              'exercises and pronunciation practice. These recordings are:',
              [
                'Used solely to evaluate your pronunciation and provide feedback',
                'Processed to improve your speaking skills',
                'Not shared with third parties for marketing purposes',
                'You can deny microphone permission, but speaking exercises will not be available',
              ],
            ),

            _buildSubsection(
              context,
              '1.3 Automatically Collected Information',
              'When you use our App, we may automatically collect:',
            ),
            _buildBulletList([
              'Device Information: Device type, operating system, and unique device identifiers',
              'Usage Data: App features used, time spent learning, and interaction patterns',
              'Network Information: Internet connection status for offline/online functionality',
            ]),

            // Section 2: How We Use Your Information
            _buildSectionTitle(context, '2. How We Use Your Information'),
            _buildSection(
              context,
              null,
              'We use the collected information for the following purposes:',
            ),
            _buildBulletList([
              'Provide Services: To deliver personalized English learning content and track your progress',
              'Improve Learning Experience: To analyze your pronunciation through audio recordings and provide feedback',
              'Personalization: To customize lessons based on your proficiency level and learning goals',
              'Communication: To send you updates about your learning progress and app features',
              'App Improvement: To analyze usage patterns and improve our educational content',
              'Security: To protect against unauthorized access and ensure app security',
            ]),

            // Section 3: Data Storage and Security
            _buildSectionTitle(context, '3. Data Storage and Security'),
            _buildSection(
              context,
              null,
              'We implement appropriate technical and organizational security measures to protect your personal information:',
            ),
            _buildBulletList([
              'Secure Storage: Authentication tokens and sensitive data are stored using encrypted secure storage on your device',
              'Encrypted Transmission: All data transmitted between the App and our servers uses HTTPS encryption',
              'Access Controls: We limit access to personal information to authorized personnel only',
              'Local Caching: Some learning content and audio files may be cached locally on your device for offline access',
            ]),

            // Section 4: Data Sharing and Disclosure
            _buildSectionTitle(context, '4. Data Sharing and Disclosure'),
            _buildSection(
              context,
              null,
              'We do not sell, trade, or rent your personal information to third parties. '
              'We may share your information only in the following circumstances:',
            ),
            _buildBulletList([
              'Service Providers: With trusted third-party services that help us operate the App (e.g., cloud hosting, analytics)',
              'Legal Requirements: When required by law or to respond to legal processes',
              'Protection: To protect our rights, privacy, safety, or property',
              'Business Transfers: In connection with a merger, acquisition, or sale of assets',
            ]),

            // Section 5: Your Rights and Choices
            _buildSectionTitle(context, '5. Your Rights and Choices'),
            _buildSection(
              context,
              null,
              'You have the following rights regarding your personal information:',
            ),
            _buildBulletList([
              'Access: You can access your profile information within the App',
              'Update: You can update your profile and learning preferences at any time',
              'Delete: You can request deletion of your account and associated data by contacting us',
              'Permissions: You can manage app permissions (microphone, storage) through your device settings',
              'Opt-out: You can disable optional features that require specific permissions',
            ]),

            // Section 6: Children's Privacy
            _buildSectionTitle(context, '6. Children\'s Privacy'),
            _buildSection(
              context,
              null,
              'Our App is designed for general audiences learning English. We do not '
              'knowingly collect personal information from children under 13 years of age. '
              'If you are a parent or guardian and believe your child has provided us with '
              'personal information, please contact us so we can delete such information.',
            ),

            // Section 7: Data Retention
            _buildSectionTitle(context, '7. Data Retention'),
            _buildSection(
              context,
              null,
              'We retain your personal information for as long as your account is active '
              'or as needed to provide you services. You can request deletion of your data '
              'at any time. After account deletion, we may retain certain information as '
              'required by law or for legitimate business purposes.',
            ),

            // Section 8: International Data Transfers
            _buildSectionTitle(context, '8. International Data Transfers'),
            _buildSection(
              context,
              null,
              'Your information may be transferred to and processed in countries other '
              'than your country of residence. We ensure appropriate safeguards are in '
              'place to protect your information in accordance with this Privacy Policy.',
            ),

            // Section 9: Changes to This Privacy Policy
            _buildSectionTitle(context, '9. Changes to This Privacy Policy'),
            _buildSection(
              context,
              null,
              'We may update this Privacy Policy from time to time. We will notify you '
              'of any changes by posting the new Privacy Policy on this page and updating '
              'the "Last Updated" date. You are advised to review this Privacy Policy '
              'periodically for any changes.',
            ),

            // Section 10: Contact Us
            _buildSectionTitle(context, '10. Contact Us'),
            _buildSection(
              context,
              null,
              'If you have any questions about this Privacy Policy or our data practices, please contact us:',
            ),
            _buildContactInfo(context),

            // Section 11: Permissions Summary
            _buildSectionTitle(context, '11. Permissions Summary'),
            _buildSection(
              context,
              null,
              'Our App requests the following permissions:',
            ),
            _buildPermissionsTable(context),

            const SizedBox(height: 32),

            // Footer
            Center(
              child: Column(
                children: [
                  const Divider(),
                  const SizedBox(height: 16),
                  Text(
                    '© 2024 Selm. All rights reserved.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondaryColor,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'SELM MOBILE APPLICATION INC.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTheme.textSecondaryColor,
                      fontWeight: FontWeight.w500,
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

  Widget _buildSectionTitle(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.only(top: 24, bottom: 12),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleLarge?.copyWith(
          fontWeight: FontWeight.bold,
          color: AppTheme.primaryColor,
        ),
      ),
    );
  }

  Widget _buildSection(BuildContext context, String? title, String content) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (title != null) ...[
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimaryColor,
            ),
          ),
          const SizedBox(height: 8),
        ],
        Text(
          content,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: AppTheme.textPrimaryColor,
            height: 1.6,
          ),
        ),
      ],
    );
  }

  Widget _buildSubsection(BuildContext context, String title, String? content) {
    return Padding(
      padding: const EdgeInsets.only(top: 16, bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppTheme.textPrimaryColor,
            ),
          ),
          if (content != null) ...[
            const SizedBox(height: 8),
            Text(
              content,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTheme.textPrimaryColor,
                height: 1.6,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildBulletList(List<String> items) {
    return Padding(
      padding: const EdgeInsets.only(left: 16, top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: items.map((item) {
          final parts = item.split(':');
          if (parts.length > 1) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('• ', style: TextStyle(fontSize: 16)),
                  Expanded(
                    child: RichText(
                      text: TextSpan(
                        style: const TextStyle(
                          color: AppTheme.textPrimaryColor,
                          height: 1.5,
                        ),
                        children: [
                          TextSpan(
                            text: '${parts[0]}:',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          TextSpan(text: parts.sublist(1).join(':')),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            );
          }
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('• ', style: TextStyle(fontSize: 16)),
                Expanded(
                  child: Text(
                    item,
                    style: const TextStyle(
                      color: AppTheme.textPrimaryColor,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildHighlightBox(
    BuildContext context,
    String title,
    String description,
    List<String> items,
  ) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.primaryColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: AppTheme.primaryColor.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.mic, color: AppTheme.primaryColor, size: 20),
              const SizedBox(width: 8),
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryColor,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            description,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTheme.textPrimaryColor,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 12),
          ...items.map((item) => Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.check_circle,
                  size: 16,
                  color: AppTheme.primaryColor,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    item,
                    style: const TextStyle(
                      color: AppTheme.textPrimaryColor,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildContactInfo(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          _buildContactRow(Icons.email, 'Email', 'selmapp2022@gmail.com'),
          const Divider(height: 24),
          _buildContactRow(Icons.phone, 'Phone', '+1 (604) 717-8543'),
          const Divider(height: 24),
          _buildContactRow(Icons.business, 'Company', 'SELM MOBILE APPLICATION INC.'),
          const Divider(height: 24),
          _buildContactRow(
            Icons.location_on,
            'Address',
            '1188 West Pender, Vancouver, BC, Canada V6E 0A2',
          ),
        ],
      ),
    );
  }

  Widget _buildContactRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: AppTheme.primaryColor),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textSecondaryColor,
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                value,
                style: const TextStyle(
                  color: AppTheme.textPrimaryColor,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPermissionsTable(BuildContext context) {
    final permissions = [
      {'permission': 'Internet', 'purpose': 'To sync your learning progress and download content'},
      {'permission': 'Microphone', 'purpose': 'To record audio for speaking exercises and pronunciation practice'},
      {'permission': 'Network State', 'purpose': 'To check connectivity and enable offline mode'},
      {'permission': 'Storage (Android 12 and below)', 'purpose': 'To cache audio files for offline learning'},
    ];

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey.shade300),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(11)),
            ),
            child: const Row(
              children: [
                Expanded(
                  flex: 2,
                  child: Text(
                    'Permission',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                Expanded(
                  flex: 3,
                  child: Text(
                    'Purpose',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
          ...permissions.asMap().entries.map((entry) {
            final isLast = entry.key == permissions.length - 1;
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                border: isLast
                    ? null
                    : Border(bottom: BorderSide(color: Colors.grey.shade300)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    flex: 2,
                    child: Text(
                      entry.value['permission']!,
                      style: const TextStyle(fontWeight: FontWeight.w500),
                    ),
                  ),
                  Expanded(
                    flex: 3,
                    child: Text(entry.value['purpose']!),
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




