import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import 'address_book.dart';
import 'orders_screen.dart';
import 'password_reset_screen.dart';

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
  final _mfa = TextEditingController();
  final _currentPassword = TextEditingController();
  final _newPassword = TextEditingController();
  bool _register = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _username.dispose();
    _password2.dispose();
    _mfa.dispose();
    _currentPassword.dispose();
    _newPassword.dispose();
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
          const SizedBox(height: 8),
          const _ProfileEditor(),
          const SizedBox(height: 16),
          const Text('Security', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  Row(
                    children: [
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Two-factor authentication',
                              style: TextStyle(fontWeight: FontWeight.w600),
                            ),
                            Text(
                              'Authenticator app',
                              style: TextStyle(color: NbColors.mute, fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                      session.mfaEnabled
                          ? OutlinedButton(
                              onPressed: _busy
                                  ? null
                                  : () => _run(
                                        () => ref.read(authStateProvider.notifier).disableMfa(),
                                      ),
                              child: const Text('Turn off'),
                            )
                          : FilledButton(
                              onPressed: _busy ? null : _setupMfa,
                              child: const Text('Turn on'),
                            ),
                    ],
                  ),
                  if (session.mfaEnabled) ...[
                    const Divider(),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            session.backupCodes.isEmpty
                                ? 'No backup codes yet'
                                : '${session.backupCodes.length} backup codes',
                          ),
                        ),
                        OutlinedButton(
                          onPressed: _busy
                              ? null
                              : () => _run(
                                    () => ref
                                        .read(authStateProvider.notifier)
                                        .generateBackupCodes(),
                                  ),
                          child: const Text('Generate'),
                        ),
                      ],
                    ),
                    if (session.backupCodes.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Wrap(
                          spacing: 12,
                          runSpacing: 6,
                          children: [
                            for (final code in session.backupCodes)
                              Text(code, style: const TextStyle(fontFamily: 'monospace')),
                          ],
                        ),
                      ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _currentPassword,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Current password'),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _newPassword,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'New password'),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton(
              onPressed: _busy ? null : _changePassword,
              child: const Text('Change password'),
            ),
          ),
          const SizedBox(height: 16),
          const AddressBookSection(),
          const SizedBox(height: 16),
          const _NotificationSection(),
          const SizedBox(height: 8),
          const _DeviceSection(),
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

  Future<void> _setupMfa() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final secret = await ref.read(authStateProvider.notifier).setupMfa();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Authenticator registered'),
          content: SelectableText(
            'Secret, shown once:\n$secret',
            style: const TextStyle(fontFamily: 'monospace'),
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Done'),
            ),
          ],
        ),
      );
    } catch (error) {
      if (mounted) {
        setState(() => _error = ref.read(apiProvider).errorMessage(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _orderCountLabel(WidgetRef ref) {
    final orders = ref.watch(ordersProvider);
    return orders.when(
      data: (rows) => '${rows.length} order${rows.length == 1 ? '' : 's'}',
      loading: () => 'Loading orders',
      error: (_, __) => 'Orders',
    );
  }

  Future<void> _changePassword() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(apiProvider);
    try {
      await api.dio.post(
        '/api/v1/auth/users/change_password/',
        data: {
          'current_password': _currentPassword.text,
          'new_password': _newPassword.text,
        },
      );
      _currentPassword.clear();
      _newPassword.clear();
      if (mounted) showAppMessage(context, 'Password updated');
    } catch (error) {
      if (mounted) setState(() => _error = api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
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

class _ProfileEditor extends ConsumerStatefulWidget {
  const _ProfileEditor();

  @override
  ConsumerState<_ProfileEditor> createState() => _ProfileEditorState();
}

class _ProfileEditorState extends ConsumerState<_ProfileEditor> {
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _address = TextEditingController();
  int? _loadedId;
  bool _busy = false;

  @override
  void dispose() {
    _first.dispose();
    _last.dispose();
    _address.dispose();
    super.dispose();
  }

  void _fill(UserProfile profile) {
    if (_loadedId == profile.id) return;
    _loadedId = profile.id;
    _first.text = profile.firstName;
    _last.text = profile.lastName;
    _address.text = profile.address;
  }

  Future<void> _save(UserProfile profile) async {
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    try {
      await api.dio.patch(
        '/api/v1/auth/profiles/${profile.id}/',
        data: {
          'first_name': _first.text.trim(),
          'last_name': _last.text.trim(),
          'address': _address.text.trim(),
        },
      );
      ref.invalidate(profileProvider);
      await ref.read(authStateProvider.notifier).refreshMe();
      if (mounted) showAppMessage(context, 'Profile saved');
    } catch (error) {
      if (mounted) showAppMessage(context, api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = ref.watch(profileProvider);
    return profile.when(
      loading: () => const LinearProgressIndicator(),
      error: (error, _) => Text('$error'),
      data: (row) {
        if (row == null) return const SizedBox.shrink();
        _fill(row);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Profile', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            TextField(controller: _first, decoration: const InputDecoration(labelText: 'First name')),
            TextField(controller: _last, decoration: const InputDecoration(labelText: 'Last name')),
            TextField(controller: _address, decoration: const InputDecoration(labelText: 'Address')),
            const SizedBox(height: 8),
            OutlinedButton(
              onPressed: _busy ? null : () => _save(row),
              child: const Text('Save profile'),
            ),
          ],
        );
      },
    );
  }
}

class _NotificationSection extends ConsumerWidget {
  const _NotificationSection();

  Future<void> _toggle(BuildContext context, WidgetRef ref, Map<String, dynamic> body) async {
    final api = ref.read(apiProvider);
    try {
      await api.dio.patch('/api/v1/notifications/preferences/', data: body);
      ref.invalidate(notificationPrefsProvider);
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final prefs = ref.watch(notificationPrefsProvider);
    return prefs.when(
      loading: () => const SizedBox.shrink(),
      error: (error, _) => Text('$error'),
      data: (row) {
        if (row == null) return const SizedBox.shrink();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Notifications', style: TextStyle(fontWeight: FontWeight.w700)),
            const SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('Order emails'),
              subtitle: Text('Required'),
              value: true,
              onChanged: null,
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Marketing email'),
              value: row.emailMarketing,
              onChanged: (value) => _toggle(context, ref, {'email_marketing': value}),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Order push'),
              value: row.pushOrderUpdates,
              onChanged: (value) => _toggle(context, ref, {'push_order_updates': value}),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Marketing push'),
              value: row.pushMarketing,
              onChanged: (value) => _toggle(context, ref, {'push_marketing': value}),
            ),
          ],
        );
      },
    );
  }
}

class _DeviceSection extends ConsumerWidget {
  const _DeviceSection();

  String get _platform {
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return 'android';
      case TargetPlatform.iOS:
        return 'ios';
      default:
        return 'web';
    }
  }

  Future<void> _register(WidgetRef ref) async {
    final api = ref.read(apiProvider);
    final prefs = await SharedPreferences.getInstance();
    var token = prefs.getString('nb_push_token');
    if (token == null || token.isEmpty) {
      token = const Uuid().v4();
      await prefs.setString('nb_push_token', token);
    }
    await api.dio.post(
      '/api/v1/notifications/devices/',
      data: {'token': token, 'platform': _platform},
    );
    ref.invalidate(devicesProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final devices = ref.watch(devicesProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('This device', style: TextStyle(fontWeight: FontWeight.w700)),
        devices.when(
          loading: () => const LinearProgressIndicator(),
          error: (error, _) => Text('$error'),
          data: (rows) => Column(
            children: [
              if (rows.isEmpty)
                const Text('Not registered for push.', style: TextStyle(color: NbColors.mute)),
              for (final device in rows)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(device.platform),
                  subtitle: Text(
                    device.token,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                  ),
                  trailing: IconButton(
                    tooltip: 'Remove',
                    onPressed: () async {
                      await ref.read(apiProvider).dio.delete(
                            '/api/v1/notifications/devices/${device.id}/',
                          );
                      ref.invalidate(devicesProvider);
                    },
                    icon: const Icon(Icons.delete_outline),
                  ),
                ),
            ],
          ),
        ),
        OutlinedButton(
          onPressed: () => _register(ref),
          child: const Text('Register this device'),
        ),
      ],
    );
  }
}
