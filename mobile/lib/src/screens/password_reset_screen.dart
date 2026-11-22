import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';
import '../theme.dart';

class PasswordResetScreen extends ConsumerStatefulWidget {
  const PasswordResetScreen({super.key});

  @override
  ConsumerState<PasswordResetScreen> createState() => _PasswordResetScreenState();
}

class _PasswordResetScreenState extends ConsumerState<PasswordResetScreen> {
  final _email = TextEditingController();
  final _token = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _asked = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _token.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _request() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(apiProvider);
    try {
      final res = await api.dio.post(
        '/api/v1/auth/password-reset/',
        data: {'email': _email.text.trim()},
      );
      final data = res.data is Map ? Map<String, dynamic>.from(res.data as Map) : const {};
      final dev = data['dev_token'];
      if (dev is String && dev.isNotEmpty) _token.text = dev;
      if (!mounted) return;
      setState(() => _asked = true);
      showAppMessage(
        context,
        'If that account exists, a reset token was issued.',
      );
    } catch (error) {
      if (mounted) setState(() => _error = api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirm() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(apiProvider);
    try {
      await api.dio.post(
        '/api/v1/auth/password-reset/confirm/',
        data: {
          'token': _token.text.trim(),
          'new_password': _password.text,
        },
      );
      if (!mounted) return;
      showAppMessage(context, 'Password reset. Sign in with the new password.');
      Navigator.of(context).pop();
    } catch (error) {
      if (mounted) setState(() => _error = api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reset password')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'We will not say whether the email is registered.',
            style: TextStyle(color: NbColors.mute),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Color(0xFF9B3B1E))),
          ],
          const SizedBox(height: 16),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'Email'),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _busy ? null : _request,
            child: const Text('Send reset'),
          ),
          if (_asked) ...[
            const SizedBox(height: 20),
            TextField(
              controller: _token,
              decoration: const InputDecoration(
                labelText: 'Reset token',
                helperText: 'Filled automatically when the API is in DEBUG',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'New password'),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: _busy ? null : _confirm,
              child: const Text('Set new password'),
            ),
          ],
        ],
      ),
    );
  }
}
