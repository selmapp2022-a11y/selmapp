import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_theme.dart';

/// In-app Terms of Service page that displays the full terms and conditions
/// This allows users to view the terms without leaving the app
class TermsOfServicePage extends StatelessWidget {
  const TermsOfServicePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.backgroundColor,
      appBar: AppBar(
        title: const Text('Terms of Service'),
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
                      Icons.description,
                      size: 48,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Terms of Service',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimaryColor,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Last Updated: January 1, 2025',
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
              'Welcome to Selm. These Terms of Service ("Terms") govern your use of the Selm '
              'mobile application ("App") operated by SELM MOBILE APPLICATION INC. ("we", "us", or "our").\n\n'
              'By accessing or using our App, you agree to be bound by these Terms. If you disagree '
              'with any part of these terms, you may not access the App.',
            ),

            // Section 1: Acceptance of Terms
            _buildSectionTitle(context, '1. Acceptance of Terms'),
            _buildSection(
              context,
              null,
              'By creating an account or using the Selm App, you acknowledge that you have read, '
              'understood, and agree to be bound by these Terms of Service and our Privacy Policy. '
              'If you are using the App on behalf of an organization, you agree to these Terms on '
              'behalf of that organization.',
            ),

            // Section 2: Description of Service
            _buildSectionTitle(context, '2. Description of Service'),
            _buildSection(
              context,
              null,
              'Selm is an intelligent English language learning application that provides:',
            ),
            _buildBulletList([
              'Personalized learning paths based on your proficiency level',
              'Interactive exercises for grammar, vocabulary, reading, listening, speaking, and writing',
              'AI-powered feedback and assessment',
              'Progress tracking and performance analytics',
              'Speech recognition for pronunciation practice',
              'Daily learning goals and streak tracking',
            ]),

            // Section 3: User Accounts
            _buildSectionTitle(context, '3. User Accounts'),
            _buildSubsection(
              context,
              '3.1 Account Registration',
              'To use certain features of the App, you must register for an account. You agree to:',
            ),
            _buildBulletList([
              'Provide accurate, current, and complete information',
              'Maintain and promptly update your account information',
              'Keep your password secure and confidential',
              'Notify us immediately of any unauthorized access',
              'Accept responsibility for all activities under your account',
            ]),

            _buildSubsection(
              context,
              '3.2 Age Requirements',
              'You must be at least 13 years old to use the App. If you are under 18, you represent '
              'that your parent or legal guardian has reviewed and agreed to these Terms.',
            ),

            // Section 4: User Conduct
            _buildSectionTitle(context, '4. User Conduct'),
            _buildSection(
              context,
              null,
              'You agree not to use the App to:',
            ),
            _buildBulletList([
              'Violate any applicable laws or regulations',
              'Infringe on intellectual property rights of others',
              'Transmit harmful, offensive, or inappropriate content',
              'Attempt to gain unauthorized access to the App or its systems',
              'Interfere with or disrupt the App or servers',
              'Use automated means to access the App without permission',
              'Collect user information without consent',
              'Engage in any activity that could harm other users',
            ]),

            // Section 5: Intellectual Property
            _buildSectionTitle(context, '5. Intellectual Property'),
            _buildSection(
              context,
              null,
              'The App and its original content, features, and functionality are owned by '
              'SELM MOBILE APPLICATION INC. and are protected by international copyright, trademark, '
              'patent, trade secret, and other intellectual property laws.\n\n'
              'You are granted a limited, non-exclusive, non-transferable license to use the App '
              'for personal, non-commercial educational purposes.',
            ),

            // Section 6: User Content
            _buildSectionTitle(context, '6. User Content'),
            _buildSection(
              context,
              null,
              'When you submit content to the App (such as written responses, audio recordings, or feedback):',
            ),
            _buildBulletList([
              'You retain ownership of your content',
              'You grant us a license to use, store, and process your content for service delivery',
              'You represent that you have the right to submit such content',
              'You understand that audio recordings are used for pronunciation assessment',
            ]),

            // Section 7: Subscription and Payments
            _buildSectionTitle(context, '7. Subscription and Payments'),
            _buildSubsection(
              context,
              '7.1 Free and Premium Features',
              'Selm offers both free and premium features. Premium subscriptions may be required '
              'for access to advanced content and features.',
            ),
            _buildSubsection(
              context,
              '7.2 Payment Terms',
              'If you purchase a subscription:',
            ),
            _buildBulletList([
              'Payment is processed through the App Store or Google Play',
              'Subscriptions automatically renew unless cancelled',
              'Refunds are subject to the policies of the respective app store',
              'Prices may change with reasonable notice',
            ]),

            // Section 8: Disclaimers
            _buildSectionTitle(context, '8. Disclaimers'),
            _buildHighlightBox(
              context,
              'Important Notice',
              'The App is provided "AS IS" and "AS AVAILABLE" without warranties of any kind. We do not guarantee:',
              [
                'Uninterrupted or error-free service',
                'Accuracy of AI-generated feedback or assessments',
                'Specific learning outcomes or language proficiency improvements',
                'Compatibility with all devices or operating systems',
              ],
            ),

            // Section 9: Limitation of Liability
            _buildSectionTitle(context, '9. Limitation of Liability'),
            _buildSection(
              context,
              null,
              'To the maximum extent permitted by law, SELM MOBILE APPLICATION INC. shall not be '
              'liable for any indirect, incidental, special, consequential, or punitive damages, '
              'including but not limited to loss of profits, data, or other intangible losses, '
              'resulting from your use of the App.',
            ),

            // Section 10: Termination
            _buildSectionTitle(context, '10. Termination'),
            _buildSection(
              context,
              null,
              'We may terminate or suspend your account and access to the App immediately, without '
              'prior notice or liability, for any reason, including breach of these Terms.\n\n'
              'Upon termination, your right to use the App will cease immediately. You may also '
              'delete your account at any time through the App settings.',
            ),

            // Section 11: Changes to Terms
            _buildSectionTitle(context, '11. Changes to Terms'),
            _buildSection(
              context,
              null,
              'We reserve the right to modify these Terms at any time. We will notify users of '
              'significant changes through the App or via email. Your continued use of the App '
              'after such modifications constitutes acceptance of the updated Terms.',
            ),

            // Section 12: Governing Law
            _buildSectionTitle(context, '12. Governing Law'),
            _buildSection(
              context,
              null,
              'These Terms shall be governed by and construed in accordance with the laws of '
              'British Columbia, Canada, without regard to its conflict of law provisions. Any '
              'disputes arising from these Terms shall be resolved in the courts of British Columbia.',
            ),

            // Section 13: Contact Information
            _buildSectionTitle(context, '13. Contact Us'),
            _buildSection(
              context,
              null,
              'If you have any questions about these Terms of Service, please contact us:',
            ),
            _buildContactInfo(context),

            const SizedBox(height: 32),

            // Footer
            Center(
              child: Column(
                children: [
                  const Divider(),
                  const SizedBox(height: 16),
                  Text(
                    '© 2025 Selm. All rights reserved.',
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
        color: Colors.orange.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.orange.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.warning_amber, color: Colors.orange[700], size: 20),
              const SizedBox(width: 8),
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: Colors.orange[700],
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
                  Icons.info_outline,
                  size: 16,
                  color: Colors.orange[700],
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
}

