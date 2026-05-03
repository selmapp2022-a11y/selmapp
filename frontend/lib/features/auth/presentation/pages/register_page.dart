import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/services/auth_service.dart';
import '../../../../core/di/injection_container.dart' as di;

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  static const Color _bg = Color(0xFF0C1C2C);
  static const Color _accent = Color(0xFF2DD4BF);
  static const Color _inputFill = Color(0xFF132A40);
  static const Color _inputHint = Color(0xFF7A8FA3);

  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  bool _obscurePassword = true;

  late final AuthService _authService;

  @override
  void initState() {
    super.initState();
    _authService = di.sl<AuthService>();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    try {
      final isConnected = await _authService.testConnectivity();
      if (!isConnected) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
                content: Text(
                    'Cannot connect to server. Please check your internet connection.')),
          );
        }
        return;
      }
      final result = await _authService.register(
        email: _emailController.text.trim(),
        password: _passwordController.text,
        fullName: _nameController.text.trim(),
      );
      if (!mounted) return;
      if (result['success']) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Account created successfully!')),
        );
        context.go('/onboarding');
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppConstants.normalizeBrandingText(
                (result['message'] ?? 'Registration failed').toString())),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } catch (e) {
      if (kDebugMode) print('Register error: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppConstants.normalizeBrandingText(
                'Registration failed: ${e.toString()}')),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 16),
              _buildBrand(),
              const SizedBox(height: 24),
              _buildCard(),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBrand() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFF1A3346),
            borderRadius: BorderRadius.circular(10),
          ),
          alignment: Alignment.center,
          child: const Text(
            'S',
            style: TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w800,
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: const [
            Text('SELM',
                style: TextStyle(
                    color: _accent,
                    fontSize: 26,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5)),
            SizedBox(height: 2),
            Text('ENGLISH LEARNING APP',
                style: TextStyle(
                    color: Color(0xFFB7C6D6),
                    fontSize: 11,
                    letterSpacing: 2.0,
                    fontWeight: FontWeight.w500)),
          ],
        ),
      ],
    );
  }

  Widget _buildCard() {
    return Container(
      padding: const EdgeInsets.fromLTRB(22, 26, 22, 22),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Create your account',
                style: TextStyle(
                    color: _accent, fontSize: 26, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            const Text('Personal English coaching, powered by AI.',
                style: TextStyle(color: Color(0xFF6B7B8C), fontSize: 15)),
            const SizedBox(height: 22),
            _label('Full name'),
            const SizedBox(height: 8),
            _field(_nameController, 'Jane Doe',
                validator: (v) => (v == null || v.trim().isEmpty)
                    ? 'Please enter your name'
                    : null),
            const SizedBox(height: 16),
            _label('Email'),
            const SizedBox(height: 8),
            _field(_emailController, 'you@example.com',
                keyboardType: TextInputType.emailAddress, validator: (v) {
              if (v == null || v.isEmpty) return 'Please enter your email';
              if (!RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$').hasMatch(v)) {
                return 'Please enter a valid email';
              }
              return null;
            }),
            const SizedBox(height: 16),
            _label('Username'),
            const SizedBox(height: 8),
            _field(_usernameController, 'janedoe',
                validator: (v) => (v == null || v.trim().isEmpty)
                    ? 'Please choose a username'
                    : null),
            const SizedBox(height: 16),
            _label('Password'),
            const SizedBox(height: 8),
            TextFormField(
              controller: _passwordController,
              obscureText: _obscurePassword,
              textInputAction: TextInputAction.done,
              onFieldSubmitted: (_) => _handleRegister(),
              style: const TextStyle(color: Colors.white, fontSize: 15),
              decoration: _inputDecoration(
                hint: 'At least 8 characters',
                suffix: IconButton(
                  onPressed: () =>
                      setState(() => _obscurePassword = !_obscurePassword),
                  icon: Icon(
                    _obscurePassword
                        ? Icons.visibility_outlined
                        : Icons.visibility_off_outlined,
                    color: _inputHint,
                    size: 20,
                  ),
                ),
              ),
              validator: (v) {
                if (v == null || v.isEmpty) return 'Please enter a password';
                if (v.length < 8) return 'At least 8 characters';
                return null;
              },
            ),
            const SizedBox(height: 22),
            _buildSubmitButton(),
            const SizedBox(height: 16),
            _buildSignInLink(),
          ],
        ),
      ),
    );
  }

  Widget _field(TextEditingController c, String hint,
      {TextInputType? keyboardType, String? Function(String?)? validator}) {
    return TextFormField(
      controller: c,
      keyboardType: keyboardType,
      textInputAction: TextInputAction.next,
      style: const TextStyle(color: Colors.white, fontSize: 15),
      decoration: _inputDecoration(hint: hint),
      validator: validator,
    );
  }

  Widget _label(String text) => Text(text,
      style: const TextStyle(
          color: Color(0xFF8A99AC),
          fontSize: 13,
          fontWeight: FontWeight.w500));

  InputDecoration _inputDecoration({String? hint, Widget? suffix}) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: _inputHint, fontSize: 15),
      suffixIcon: suffix,
      filled: true,
      fillColor: _inputFill,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _accent, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppTheme.errorColor),
      ),
    );
  }

  Widget _buildSubmitButton() {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: _isLoading ? null : _handleRegister,
        style: ElevatedButton.styleFrom(
          backgroundColor: _bg,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12)),
        ),
        child: _isLoading
            ? const SizedBox(
                height: 22,
                width: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Text('Create account',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
      ),
    );
  }

  Widget _buildSignInLink() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text('Already have an account? ',
            style: TextStyle(color: Color(0xFF8A99AC), fontSize: 14)),
        GestureDetector(
          onTap: () => context.go('/welcome'),
          child: const Text('Sign in',
              style: TextStyle(
                  color: _accent,
                  fontSize: 14,
                  fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }
}
