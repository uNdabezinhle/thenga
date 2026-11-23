import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import 'orders_screen.dart';
import 'password_reset_screen.dart';
import 'settings_screen.dart';

class AccountScreen extends ConsumerStatefulWidget {
  const AccountScreen({super.key});

  @override
  ConsumerState<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends ConsumerState<AccountScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _username = TextEditingController();
  final _password2 = TextEditingController();
  final _referral = TextEditingController();
  final _mfa = TextEditingController();
  bool _register = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _username.dispose();
    _password2.dispose();
    _referral.dispose();
    _mfa.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action, {bool land = false}) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
      final user = ref.read(authStateProvider).valueOrNull?.user;
      if (user != null && land) {
        ref.invalidate(ordersProvider);
        ref.invalidate(savedProvider);
        await ref.read(cartProvider.notifier).refresh();
        if (user.isStaffOps) {
          ref.read(shellTabProvider.notifier).state = NbTab.staff;
        } else {
          ref.read(shellTabProvider.notifier).state = NbTab.shop;
        }
      }
    } catch (error) {
      if (mounted) {
        setState(() => _error = ref.read(apiProvider).errorMessage(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(authStateProvider).valueOrNull ?? const AuthSession();
    if (session.mfaPending) return _mfaForm(session);
    if (session.user != null) return _profile(session);
    return _credentials();
  }

  Widget _mfaForm(AuthSession session) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () {
            ref.read(authStateProvider.notifier).cancelChallenge();
          },
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Icon(Icons.shield_outlined, size: 36, color: NbColors.forest),
          const SizedBox(height: 12),
          const Text(
            'Enter your code',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 8),
          const Text(
            'Six digits from your authenticator. In DEBUG any six digits work except 000000.',
            style: TextStyle(color: NbColors.mute),
          ),
          if (_error != null) _errorBox(_error!),
          const SizedBox(height: 16),
          TextField(
            key: const Key('mfa-code'),
            controller: _mfa,
            keyboardType: TextInputType.text,
            decoration: const InputDecoration(labelText: 'Verification code'),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy
                ? null
                : () => _run(
                      () => ref.read(authStateProvider.notifier).verifyMfa(_mfa.text),
                      land: true,
                    ),
            child: Text(_busy ? 'Verifying' : 'Verify and sign in'),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: _busy
                ? null
                : () => _run(
                      () => ref
                          .read(authStateProvider.notifier)
                          .verifyMfa(_mfa.text, backup: true),
                      land: true,
                    ),
            child: const Text('Use a backup code instead'),
          ),
        ],
      ),
    );
  }

  Widget _credentials() {
    return Scaffold(
      appBar: AppBar(title: Text(_register ? 'Create account' : 'Sign in')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            _register ? 'Takes about thirty seconds' : 'Welcome back',
            style: const TextStyle(color: NbColors.mute),
          ),
          if (_error != null) _errorBox(_error!),
          const SizedBox(height: 16),
          if (_register)
            TextField(
              controller: _username,
              decoration: const InputDecoration(labelText: 'Username'),
            ),
          if (_register) const SizedBox(height: 12),
          TextField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'Email'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _password,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Password'),
          ),
          if (_register) ...[
            const SizedBox(height: 12),
            TextField(
              controller: _password2,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Confirm password'),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('register-referral'),
              controller: _referral,
              decoration: const InputDecoration(
                labelText: "Friend's referral code (optional)",
              ),
            ),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy
                ? null
                : () => _run(() {
                      final auth = ref.read(authStateProvider.notifier);
                      if (_register) {
                        return auth.register(
                          email: _email.text.trim(),
                          username: _username.text.trim(),
                          password: _password.text,
                          password2: _password2.text,
                          referralCode: _referral.text,
                        );
                      }
                      return auth.login(_email.text.trim(), _password.text);
                    }, land: true),
            child: Text(
              _busy ? 'Working' : (_register ? 'Create account' : 'Sign in'),
            ),
          ),
          const SizedBox(height: 16),
          const Text('OR', textAlign: TextAlign.center, style: TextStyle(color: NbColors.mute)),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: _busy
                ? null
                : () => _run(
                      () => ref.read(authStateProvider.notifier).social('google'),
                      land: true,
                    ),
            child: const Text('Continue with Google'),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: _busy
                ? null
                : () => _run(
                      () => ref.read(authStateProvider.notifier).social('facebook'),
                      land: true,
                    ),
            child: const Text('Continue with Facebook'),
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: () => setState(() {
              _register = !_register;
              _error = null;
            }),
            child: Text(_register ? 'Already have an account? Sign in' : 'New here? Create one'),
          ),
          const SizedBox(height: 8),
          Builder(
            builder: (context) {
              final guestItems = ref.watch(cartProvider).valueOrNull?.totalItems ?? 0;
              if (guestItems <= 0) return const SizedBox.shrink();
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  '$guestItems guest cart item${guestItems == 1 ? '' : 's'} will merge when you sign in.',
                  style: const TextStyle(color: NbColors.forest, fontWeight: FontWeight.w600),
                ),
              );
            },
          ),
          TextButton(
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const PasswordResetScreen()),
              );
            },
            child: const Text('Forgot password?'),
          ),
          const SizedBox(height: 8),
          const Text(
            'Demo customer: jordan@northbound.test / correct-horse-42\n'
            'MFA: any 6 digits except 000000\n'
            'Staff: staff@northbound.test / staff-ops-42',
            style: TextStyle(fontSize: 12, color: NbColors.mute, height: 1.45),
          ),
          const SizedBox(height: 16),
          const _SessionCard(),
        ],
      ),
    );
  }

  Widget _profile(AuthSession session) {
    final user = session.user!;
    final initial = user.name.isEmpty ? '?' : user.name[0].toUpperCase();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Account'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: () async {
              await ref.read(authStateProvider.notifier).logout();
              ref.invalidate(ordersProvider);
              ref.invalidate(savedProvider);
              await ref.read(cartProvider.notifier).refresh();
            },
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_error != null) _errorBox(_error!),
          Card(
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: NbColors.forest,
                foregroundColor: NbColors.lime,
                child: Text(initial),
              ),
              title: Text(user.name, style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text(user.email),
            ),
          ),
          ListTile(
            title: const Text('Email'),
            trailing: Text(
              user.emailVerified ? 'Verified' : 'Pending',
              style: TextStyle(
                color: user.emailVerified ? const Color(0xFF2F7A4F) : Colors.orange,
              ),
            ),
          ),
          const _SessionCard(),
          ListTile(
            key: const Key('open-settings'),
            contentPadding: EdgeInsets.zero,
            title: const Text('Settings'),
            subtitle: const Text('Profile, security, addresses, notifications'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SettingsScreen()),
              );
            },
          ),
          const _InboxSection(),
          const SizedBox(height: 8),
          ListTile(
            title: const Text('Order history'),
            subtitle: Text(_orderCountLabel(ref)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const OrdersScreen()),
              );
            },
          ),
          if (user.isStaffOps)
            ListTile(
              title: const Text('Staff console'),
              subtitle: const Text('Orders, refunds, reconciliation'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () {
                ref.read(shellTabProvider.notifier).state = NbTab.staff;
              },
            ),
        ],
      ),
    );
  }

  String _orderCountLabel(WidgetRef ref) {
    final orders = ref.watch(ordersProvider);
    return orders.when(
      data: (rows) => '${rows.length} order${rows.length == 1 ? '' : 's'}',
      loading: () => 'Loading orders',
      error: (_, __) => 'Orders',
    );
  }

  Widget _errorBox(String message) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFDECE7),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFF5C4B6)),
      ),
      child: Text(message, style: const TextStyle(color: Color(0xFF9B3B1E))),
    );
  }
}

class _SessionCard extends ConsumerWidget {
  const _SessionCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final debug = ref.watch(sessionDebugProvider);
    return debug.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (info) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Session', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text('API  ${info.apiBase}', style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
              Text('Token  ${info.tokenPrefix}', style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
              Text(
                'MFA verified  ${info.mfaVerified ?? '—'}',
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
              Text('Cart  ${info.cartSession}', style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
            ],
          ),
        ),
      ),
    );
  }
}

class _InboxSection extends ConsumerWidget {
  const _InboxSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final inbox = ref.watch(inboxProvider);
    return inbox.when(
      loading: () => const SizedBox.shrink(),
      error: (error, _) => Text('$error'),
      data: (notes) {
        if (notes.isEmpty) {
          return const Text(
            'No messages yet',
            style: TextStyle(color: NbColors.mute, fontSize: 12),
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final note in notes)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(note.title),
                subtitle: Text(note.body),
                trailing: note.read
                    ? null
                    : const Icon(Icons.circle, size: 10, color: NbColors.forest),
                onTap: note.read
                    ? null
                    : () async {
                        final api = ref.read(apiProvider);
                        try {
                          await api.dio.post('/api/v1/notifications/inbox/${note.id}/read/');
                          ref.invalidate(inboxProvider);
                        } catch (error) {
                          if (context.mounted) {
                            showAppMessage(context, api.errorMessage(error));
                          }
                        }
                      },
              ),
          ],
        );
      },
    );
  }
}
