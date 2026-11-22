import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';

class AddressBookSection extends ConsumerWidget {
  const AddressBookSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final addresses = ref.watch(addressesProvider);
    return addresses.when(
      loading: () => const LinearProgressIndicator(),
      error: (error, _) => Text('$error'),
      data: (rows) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Addresses', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          if (rows.isEmpty)
            const Text(
              'No saved addresses yet.',
              style: TextStyle(color: NbColors.mute),
            ),
          for (final entry in rows)
            Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: ListTile(
                title: Text(entry.label.isEmpty ? 'Saved address' : entry.label),
                subtitle: Text(
                  [
                    entry.singleLine,
                    if (entry.isDefaultShipping) 'Default',
                  ].join('\n'),
                ),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      tooltip: 'Edit',
                      onPressed: () => editAddressEntry(context, ref, entry),
                      icon: const Icon(Icons.edit_outlined),
                    ),
                    IconButton(
                      tooltip: 'Delete',
                      onPressed: () => deleteAddressEntry(context, ref, entry),
                      icon: const Icon(Icons.delete_outline),
                    ),
                  ],
                ),
              ),
            ),
          OutlinedButton(
            onPressed: () => editAddressEntry(context, ref, null),
            child: const Text('Add address'),
          ),
        ],
      ),
    );
  }
}

Future<AddressBookEntry?> editAddressEntry(
  BuildContext context,
  WidgetRef ref,
  AddressBookEntry? existing,
) async {
  final saved = await showDialog<AddressBookEntry>(
    context: context,
    builder: (context) => _AddressDialog(existing: existing),
  );
  if (saved == null) return null;
  final api = ref.read(apiProvider);
  try {
    final response = existing == null
        ? await api.dio.post('/api/v1/orders/addresses/', data: saved.toJson())
        : await api.dio.patch(
            '/api/v1/orders/addresses/${existing.id}/',
            data: saved.toJson(),
          );
    ref.invalidate(addressesProvider);
    final entry = AddressBookEntry.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
    if (context.mounted) {
      showAppMessage(context, existing == null ? 'Address saved' : 'Address updated');
    }
    return entry;
  } catch (error) {
    if (context.mounted) showAppMessage(context, api.errorMessage(error));
    return null;
  }
}

Future<bool> deleteAddressEntry(
  BuildContext context,
  WidgetRef ref,
  AddressBookEntry entry,
) async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Delete this address?'),
      content: Text(entry.singleLine),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Keep'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Delete'),
        ),
      ],
    ),
  );
  if (confirmed != true) return false;
  final api = ref.read(apiProvider);
  try {
    await api.dio.delete('/api/v1/orders/addresses/${entry.id}/');
    ref.invalidate(addressesProvider);
    if (context.mounted) showAppMessage(context, 'Address deleted');
    return true;
  } catch (error) {
    if (context.mounted) showAppMessage(context, api.errorMessage(error));
    return false;
  }
}

class _AddressDialog extends StatefulWidget {
  const _AddressDialog({required this.existing});

  final AddressBookEntry? existing;

  @override
  State<_AddressDialog> createState() => _AddressDialogState();
}

class _AddressDialogState extends State<_AddressDialog> {
  late final TextEditingController _label;
  late final TextEditingController _recipient;
  late final TextEditingController _phone;
  late final TextEditingController _line1;
  late final TextEditingController _line2;
  late final TextEditingController _suburb;
  late final TextEditingController _city;
  late final TextEditingController _province;
  late final TextEditingController _postal;
  late bool _defaultShipping;

  @override
  void initState() {
    super.initState();
    final entry = widget.existing;
    _label = TextEditingController(text: entry?.label ?? 'Home');
    _recipient = TextEditingController(text: entry?.recipientName ?? '');
    _phone = TextEditingController(text: entry?.phone ?? '');
    _line1 = TextEditingController(text: entry?.line1 ?? '');
    _line2 = TextEditingController(text: entry?.line2 ?? '');
    _suburb = TextEditingController(text: entry?.suburb ?? '');
    _city = TextEditingController(text: entry?.city ?? 'Cape Town');
    _province = TextEditingController(text: entry?.province ?? '');
    _postal = TextEditingController(text: entry?.postalCode ?? '8001');
    _defaultShipping = entry?.isDefaultShipping ?? true;
  }

  @override
  void dispose() {
    for (final controller in [
      _label,
      _recipient,
      _phone,
      _line1,
      _line2,
      _suburb,
      _city,
      _province,
      _postal,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  void _submit() {
    final line1 = _line1.text.trim();
    final city = _city.text.trim();
    final postal = _postal.text.trim();
    final recipient = _recipient.text.trim();
    if (line1.isEmpty || city.isEmpty || postal.isEmpty || recipient.isEmpty) {
      showAppMessage(context, 'Recipient, street, city, and postal code are required.');
      return;
    }
    Navigator.pop(
      context,
      AddressBookEntry(
        id: widget.existing?.id ?? 0,
        label: _label.text.trim(),
        line1: line1,
        line2: _line2.text.trim(),
        suburb: _suburb.text.trim(),
        city: city,
        province: _province.text.trim(),
        postalCode: postal,
        recipientName: recipient,
        phone: _phone.text.trim(),
        singleLine: '',
        isDefaultShipping: _defaultShipping,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.existing == null ? 'Add address' : 'Edit address'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: _label, decoration: const InputDecoration(labelText: 'Label')),
            TextField(controller: _recipient, decoration: const InputDecoration(labelText: 'Recipient')),
            TextField(controller: _phone, decoration: const InputDecoration(labelText: 'Phone')),
            TextField(controller: _line1, decoration: const InputDecoration(labelText: 'Street')),
            TextField(controller: _line2, decoration: const InputDecoration(labelText: 'Line 2')),
            TextField(controller: _suburb, decoration: const InputDecoration(labelText: 'Suburb')),
            TextField(controller: _city, decoration: const InputDecoration(labelText: 'City')),
            TextField(controller: _province, decoration: const InputDecoration(labelText: 'Province')),
            TextField(controller: _postal, decoration: const InputDecoration(labelText: 'Postal code')),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Default shipping'),
              value: _defaultShipping,
              onChanged: (value) => setState(() => _defaultShipping = value),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }
}
