import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../bloc/onboarding_bloc.dart';
import '../pages/onboarding_main_page.dart';

class RegistrationScreen extends StatefulWidget {
  const RegistrationScreen({super.key});

  @override
  State<RegistrationScreen> createState() => _RegistrationScreenState();
}

class _RegistrationScreenState extends State<RegistrationScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  bool _isPasswordVisible = false;
  bool _isConfirmPasswordVisible = false;
  bool _isFormValid = false;

  @override
  void initState() {
    super.initState();

    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _animationController, curve: Curves.easeOut),
    );

    _slideAnimation =
        Tween<Offset>(begin: const Offset(0, 0.2), end: Offset.zero).animate(
          CurvedAnimation(
            parent: _animationController,
            curve: Curves.elasticOut,
          ),
        );

    _animationController.forward();

    // Add listeners to validate form
    _nameController.addListener(_validateForm);
    _emailController.addListener(_validateForm);
    _passwordController.addListener(_validateForm);
    _confirmPasswordController.addListener(_validateForm);
  }

  @override
  void dispose() {
    _animationController.dispose();
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  void _validateForm() {
    final isValid = _formKey.currentState?.validate() ?? false;
    if (_isFormValid != isValid) {
      setState(() {
        _isFormValid = isValid;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Create Account',
        onBackPressed: () => Navigator.of(context).pop(),
      ),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeAnimation,
          child: SlideTransition(
            position: _slideAnimation,
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Header
                    Text(
                      'Let\'s get you started! 🚀',
                      style: Theme.of(context).textTheme.headlineSmall
                          ?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Create your account to begin your personalized English learning journey.',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),

                    const SizedBox(height: 40),

                    // Name Field
                    _buildAnimatedTextField(
                      controller: _nameController,
                      label: 'Full Name',
                      hint: 'Enter your full name',
                      icon: Icons.person_outline,
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Please enter your name';
                        }
                        if (value.trim().length < 2) {
                          return 'Name must be at least 2 characters';
                        }
                        return null;
                      },
                      delay: 0,
                    ),

                    const SizedBox(height: 20),

                    // Email Field
                    _buildAnimatedTextField(
                      controller: _emailController,
                      label: 'Email Address',
                      hint: 'Enter your email address',
                      icon: Icons.email_outlined,
                      keyboardType: TextInputType.emailAddress,
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Please enter your email';
                        }
                        if (!RegExp(
                          r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$',
                        ).hasMatch(value)) {
                          return 'Please enter a valid email';
                        }
                        return null;
                      },
                      delay: 100,
                    ),

                    const SizedBox(height: 20),

                    // Password Field
                    _buildAnimatedTextField(
                      controller: _passwordController,
                      label: 'Password',
                      hint: 'Choose a strong password',
                      icon: Icons.lock_outline,
                      obscureText: !_isPasswordVisible,
                      suffixIcon: IconButton(
                        icon: Icon(
                          _isPasswordVisible
                              ? Icons.visibility_off
                              : Icons.visibility,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        onPressed: () {
                          setState(() {
                            _isPasswordVisible = !_isPasswordVisible;
                          });
                        },
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please enter a password';
                        }
                        if (value.length < 8) {
                          return 'Password must be at least 8 characters';
                        }
                        if (!value.contains(RegExp(r'[A-Z]'))) {
                          return 'Password must contain at least one uppercase letter';
                        }
                        if (!value.contains(RegExp(r'[a-z]'))) {
                          return 'Password must contain at least one lowercase letter';
                        }
                        if (!value.contains(RegExp(r'[0-9]'))) {
                          return 'Password must contain at least one number';
                        }
                        return null;
                      },
                      delay: 200,
                    ),

                    const SizedBox(height: 20),

                    // Confirm Password Field
                    _buildAnimatedTextField(
                      controller: _confirmPasswordController,
                      label: 'Confirm Password',
                      hint: 'Re-enter your password',
                      icon: Icons.lock_outline,
                      obscureText: !_isConfirmPasswordVisible,
                      suffixIcon: IconButton(
                        icon: Icon(
                          _isConfirmPasswordVisible
                              ? Icons.visibility_off
                              : Icons.visibility,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        onPressed: () {
                          setState(() {
                            _isConfirmPasswordVisible =
                                !_isConfirmPasswordVisible;
                          });
                        },
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return 'Please confirm your password';
                        }
                        if (value != _passwordController.text) {
                          return 'Passwords do not match';
                        }
                        return null;
                      },
                      delay: 300,
                    ),

                    const SizedBox(height: 32),

                    // Password Strength Indicator
                    _buildPasswordStrengthIndicator(),

                    const SizedBox(height: 40),

                    // Create Account Button
                    BlocBuilder<OnboardingBloc, OnboardingState>(
                      builder: (context, state) {
                        return AnimatedOnboardingButton(
                          text: 'Create Account',
                          icon: Icons.person_add,
                          isEnabled: _isFormValid,
                          isLoading: state is OnboardingLoadingState,
                          onPressed: _isFormValid ? _submitForm : null,
                        );
                      },
                    ),

                    const SizedBox(height: 24),

                    // Already have account
                    Center(
                      child: TextButton(
                        onPressed: () {
                          // Navigate to login (if implemented)
                        },
                        child: Text(
                          'Already have an account? Sign in',
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: Theme.of(context).colorScheme.primary,
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAnimatedTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    required String? Function(String?)? validator,
    required int delay,
    TextInputType? keyboardType,
    bool obscureText = false,
    Widget? suffixIcon,
  }) {
    return TweenAnimationBuilder<double>(
      duration: Duration(milliseconds: 600 + delay),
      tween: Tween<double>(begin: 0.0, end: 1.0),
      curve: Curves.elasticOut,
      builder: (context, value, child) {
        // Clamp value to ensure it stays within 0.0 to 1.0 range
        final clampedValue = value.clamp(0.0, 1.0);
        return Transform.translate(
          offset: Offset(0, 20 * (1 - clampedValue)),
          child: Opacity(opacity: clampedValue, child: child),
        );
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8),
          TextFormField(
            controller: controller,
            keyboardType: keyboardType,
            obscureText: obscureText,
            validator: validator,
            decoration: InputDecoration(
              hintText: hint,
              prefixIcon: Icon(icon),
              suffixIcon: suffixIcon,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(
                  color: Theme.of(context).colorScheme.outline,
                ),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(
                  color: Theme.of(
                    context,
                  ).colorScheme.outline.withValues(alpha: 0.5),
                ),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(
                  color: Theme.of(context).colorScheme.primary,
                  width: 2,
                ),
              ),
              errorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
              filled: true,
              fillColor: Theme.of(context).colorScheme.surface,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPasswordStrengthIndicator() {
    final password = _passwordController.text;
    int strength = 0;
    List<String> requirements = [];

    if (password.length >= 8) {
      strength++;
    } else {
      requirements.add('At least 8 characters');
    }

    if (password.contains(RegExp(r'[A-Z]'))) {
      strength++;
    } else {
      requirements.add('One uppercase letter');
    }

    if (password.contains(RegExp(r'[a-z]'))) {
      strength++;
    } else {
      requirements.add('One lowercase letter');
    }

    if (password.contains(RegExp(r'[0-9]'))) {
      strength++;
    } else {
      requirements.add('One number');
    }

    Color strengthColor;
    String strengthText;

    if (strength == 0) {
      strengthColor = Theme.of(context).colorScheme.outline;
      strengthText = '';
    } else if (strength <= 2) {
      strengthColor = Theme.of(context).colorScheme.error;
      strengthText = 'Weak';
    } else if (strength == 3) {
      strengthColor = Colors.orange;
      strengthText = 'Medium';
    } else {
      strengthColor = Colors.green;
      strengthText = 'Strong';
    }

    return AnimatedOpacity(
      opacity: password.isNotEmpty ? 1.0 : 0.0,
      duration: const Duration(milliseconds: 300),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: LinearProgressIndicator(
                  value: strength / 4,
                  backgroundColor: Theme.of(
                    context,
                  ).colorScheme.outline.withValues(alpha: 0.3),
                  valueColor: AlwaysStoppedAnimation<Color>(strengthColor),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                strengthText,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: strengthColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          if (requirements.isNotEmpty && password.isNotEmpty) ...[
            const SizedBox(height: 8),
            ...requirements.map(
              (req) => Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  children: [
                    Icon(
                      Icons.radio_button_unchecked,
                      size: 12,
                      color: Theme.of(context).colorScheme.outline,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      req,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  void _submitForm() {
    if (_formKey.currentState?.validate() == true) {
      context.read<OnboardingBloc>().add(
        RegisterUserEvent(
          name: _nameController.text.trim(),
          email: _emailController.text.trim(),
          password: _passwordController.text,
        ),
      );
    }
  }
}
