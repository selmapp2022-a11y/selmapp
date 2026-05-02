import 'package:flutter/material.dart';

class ErrorDialog extends StatelessWidget {
  final String title;
  final String message;
  final String primaryButtonText;
  final VoidCallback? onPrimaryPressed;
  final String? secondaryButtonText;
  final VoidCallback? onSecondaryPressed;
  final IconData? icon;

  const ErrorDialog({
    super.key,
    required this.title,
    required this.message,
    this.primaryButtonText = 'OK',
    this.onPrimaryPressed,
    this.secondaryButtonText,
    this.onSecondaryPressed,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      title: Row(
        children: [
          if (icon != null) ...[
            Icon(
              icon,
              color: Theme.of(context).colorScheme.error,
              size: 28,
            ),
            const SizedBox(width: 12),
          ] else ...[
            Icon(
              Icons.error_outline,
              color: Theme.of(context).colorScheme.error,
              size: 28,
            ),
            const SizedBox(width: 12),
          ],
          Expanded(
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            message,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              height: 1.5,
            ),
          ),
        ],
      ),
      actions: [
        if (secondaryButtonText != null)
          TextButton(
            onPressed: onSecondaryPressed ?? () => Navigator.of(context).pop(),
            child: Text(
              secondaryButtonText!,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ElevatedButton(
          onPressed: onPrimaryPressed ?? () => Navigator.of(context).pop(),
          style: ElevatedButton.styleFrom(
            backgroundColor: Theme.of(context).colorScheme.error,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          child: Text(primaryButtonText),
        ),
      ],
    );
  }
}
