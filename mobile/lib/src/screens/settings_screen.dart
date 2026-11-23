import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import 'address_book.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _currentPassword = TextEditingController();
  final _newPassword = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _currentPassword.dispose();
    _newPassword.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
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
    if (!session.isSignedIn) {
      return const Scaffold(body: Center(child: Text('Sign in to change settings')));
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_error != null) _errorBox(_error!),
          const _ProfileEditor(),
          const SizedBox(height: 16),
          const Text('Security', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          _securityCard(session),
          const SizedBox(height: 12),
          TextField(
            key: const Key('settings-current-password'),
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
        ],
      ),
    );
  }

  Widget _securityCard(AuthSession session) {
    return Card(
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
                              () => ref.read(authStateProvider.notifier).generateBackupCodes(),
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
            FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Done')),
          ],
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = ref.read(apiProvider).errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
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
      margin: const EdgeInsets.only(bottom: 12),
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

class _ProfileEditor extends ConsumerStatefulWidget {
  const _ProfileEditor();

  @override
  ConsumerState<_ProfileEditor> createState() => _ProfileEditorState();
}

class _ProfileEditorState extends ConsumerState<_ProfileEditor> {
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _phone = TextEditingController();
  final _dob = TextEditingController();
  final _address = TextEditingController();
  int? _loadedId;
  bool _busy = false;

  @override
  void dispose() {
    _first.dispose();
    _last.dispose();
    _phone.dispose();
    _dob.dispose();
    _address.dispose();
    super.dispose();
  }

  void _fill(UserProfile profile) {
    if (_loadedId == profile.id) return;
    _loadedId = profile.id;
    _first.text = profile.firstName;
    _last.text = profile.lastName;
    _phone.text = profile.phoneNumber;
    _dob.text = profile.dateOfBirth;
    _address.text = profile.address;
  }

  Future<void> _save(UserProfile profile) async {
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    final dob = _dob.text.trim();
    try {
      await api.dio.patch(
        '/api/v1/auth/profiles/${profile.id}/',
        data: {
          'first_name': _first.text.trim(),
          'last_name': _last.text.trim(),
          'phone_number': _phone.text.trim(),
          'date_of_birth': dob.isEmpty ? null : dob,
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
            TextField(
              key: const Key('settings-phone'),
              controller: _phone,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Phone'),
            ),
            TextField(
              controller: _dob,
              decoration: const InputDecoration(
                labelText: 'Date of birth',
                hintText: 'YYYY-MM-DD',
              ),
            ),
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
