import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import 'address_book.dart';
import 'orders_screen.dart';

class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key});

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  final _address = TextEditingController(text: defaultAddress);
  final _label = TextEditingController(text: 'Home');
  final _line1 = TextEditingController();
  final _city = TextEditingController(text: 'Cape Town');
  final _postal = TextEditingController(text: '8001');
  final _recipient = TextEditingController();
  String _pay = 'card';
  int? _addressId;
  bool _busy = false;

  @override
  void dispose() {
    _address.dispose();
    _label.dispose();
    _line1.dispose();
    _city.dispose();
    _postal.dispose();
    _recipient.dispose();
    super.dispose();
  }

  Future<void> _saveAddress() async {
    final line1 = _line1.text.trim();
    if (line1.isEmpty) {
      showAppMessage(context, 'Add a street line first.');
      return;
    }
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    try {
      final res = await api.dio.post(
        '/api/v1/orders/addresses/',
        data: {
          'label': _label.text.trim().isEmpty ? 'Home' : _label.text.trim(),
          'line1': line1,
          'city': _city.text.trim(),
          'postal_code': _postal.text.trim(),
          'recipient_name': _recipient.text.trim(),
          'is_default_shipping': true,
        },
      );
      final saved = AddressBookEntry.fromJson(Map<String, dynamic>.from(res.data as Map));
      ref.invalidate(addressesProvider);
      if (!mounted) return;
      setState(() {
        _addressId = saved.id;
        _address.text = saved.singleLine;
      });
      showAppMessage(context, 'Address saved');
    } catch (error) {
      if (mounted) showAppMessage(context, api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _place() async {
    final cart = ref.read(cartProvider).valueOrNull;
    if (cart == null || cart.items.isEmpty) return;
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    try {
      final body = <String, dynamic>{
        'payment_method': _pay,
        'address': _address.text.trim(),
      };
      if (_addressId != null) body['address_id'] = _addressId;
      final res = await api.dio.post(
        '/api/v1/orders/',
        data: body,
        options: Options(headers: {'Idempotency-Key': newIdempotencyKey()}),
      );
      final data = Map<String, dynamic>.from(res.data as Map);
      final reference = asReference(data);
      final payment = data['payment'];
      final redirect = payment is Map ? '${payment['redirect_url'] ?? ''}' : '';
      if (_pay != 'cod' && redirect.isNotEmpty) {
        final uri = Uri.tryParse(redirect);
        var opened = false;
        if (uri != null) {
          opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
        if (mounted) {
          if (opened) {
            showAppMessage(
              context,
              'Finish payment on the hosted page. This order stays unpaid until you do.',
            );
          } else {
            await showDialog<void>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Open the payment page'),
                content: SelectableText(redirect),
                actions: [
                  FilledButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('OK'),
                  ),
                ],
              ),
            );
          }
        }
      } else if (mounted) {
        showAppMessage(context, 'Order $reference placed');
      }
      await ref.read(cartProvider.notifier).refresh();
      ref.invalidate(ordersProvider);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const OrdersScreen()),
      );
    } catch (error) {
      if (mounted) showAppMessage(context, api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authStateProvider).valueOrNull;
    final cart = ref.watch(cartProvider).valueOrNull;
    final signedIn = auth?.isSignedIn ?? false;
    final items = cart?.items ?? const [];
    final totals = cart?.totals;
    final canPlace = signedIn && items.isNotEmpty && !_busy;
    final savedAddresses = signedIn
        ? ref.watch(addressesProvider).valueOrNull ?? const <AddressBookEntry>[]
        : const <AddressBookEntry>[];

    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (!signedIn)
            Card(
              color: NbColors.forest,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Sign in to place this order',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Your cart moves across with you — nothing is lost.',
                      style: TextStyle(color: Color(0xFFA9C2B4)),
                    ),
                    const SizedBox(height: 12),
                    FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: NbColors.lime,
                        foregroundColor: NbColors.forest,
                      ),
                      onPressed: () {
                        ref.read(shellTabProvider.notifier).state = NbTab.account;
                        Navigator.of(context).pop();
                      },
                      child: const Text('Sign in'),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 8),
          const Text('Deliver to', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          if (savedAddresses.isNotEmpty)
            for (final entry in savedAddresses)
              Card(
                margin: const EdgeInsets.only(bottom: 8),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(
                    color: _addressId == entry.id ? NbColors.forest : NbColors.hair,
                  ),
                ),
                child: ListTile(
                  onTap: () => setState(() {
                    _addressId = entry.id;
                    _address.text = entry.singleLine;
                  }),
                  leading: Icon(
                    _addressId == entry.id
                        ? Icons.radio_button_checked
                        : Icons.radio_button_off,
                  ),
                  title: Text(entry.label.isEmpty ? 'Saved address' : entry.label),
                  subtitle: Text(entry.singleLine),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        tooltip: 'Edit',
                        onPressed: () async {
                          final saved = await editAddressEntry(context, ref, entry);
                          if (saved != null && saved.id == _addressId && mounted) {
                            setState(() => _address.text = saved.singleLine);
                          }
                        },
                        icon: const Icon(Icons.edit_outlined),
                      ),
                      IconButton(
                        tooltip: 'Delete',
                        onPressed: () async {
                          final removed = await deleteAddressEntry(context, ref, entry);
                          if (removed && _addressId == entry.id && mounted) {
                            setState(() => _addressId = null);
                          }
                        },
                        icon: const Icon(Icons.delete_outline),
                      ),
                    ],
                  ),
                ),
              ),
          TextField(
            controller: _address,
            decoration: const InputDecoration(
              labelText: 'Address',
              filled: true,
              fillColor: Colors.white,
            ),
            onChanged: (_) {
              if (_addressId != null) setState(() => _addressId = null);
            },
          ),
          if (signedIn) ...[
            const SizedBox(height: 8),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Save a new address'),
              children: [
                TextField(
                  controller: _label,
                  decoration: const InputDecoration(labelText: 'Label'),
                ),
                TextField(
                  controller: _recipient,
                  decoration: const InputDecoration(labelText: 'Recipient'),
                ),
                TextField(
                  controller: _line1,
                  decoration: const InputDecoration(labelText: 'Street'),
                ),
                TextField(
                  controller: _city,
                  decoration: const InputDecoration(labelText: 'City'),
                ),
                TextField(
                  controller: _postal,
                  decoration: const InputDecoration(labelText: 'Postal code'),
                ),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton(
                    onPressed: _busy ? null : _saveAddress,
                    child: const Text('Save to address book'),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          const Text('Payment', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          for (final option in const [
            ('card', 'Card', 'Sandbox Visa ···· 4242'),
            ('eft', 'Instant EFT', 'Bank transfer'),
            ('cod', 'Cash on delivery', 'Pay the courier'),
          ])
            Card(
              margin: const EdgeInsets.only(bottom: 8),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(
                  color: _pay == option.$1 ? NbColors.forest : NbColors.hair,
                ),
              ),
              child: ListTile(
                onTap: () => setState(() => _pay = option.$1),
                leading: Icon(
                  _pay == option.$1
                      ? Icons.radio_button_checked
                      : Icons.radio_button_off,
                ),
                title: Text(option.$2),
                subtitle: Text(option.$3),
              ),
            ),
          const SizedBox(height: 8),
          const Text('Order summary', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  for (final item in items)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text('${item.productName} × ${item.quantity}'),
                          ),
                          Text(
                            moneyZar(item.lineTotal),
                            style: const TextStyle(fontFamily: 'monospace'),
                          ),
                        ],
                      ),
                    ),
                  if (totals != null && totals.hasDiscount)
                    _line('Discount', '− ${moneyZar(totals.discountTotal)}'),
                  if (totals != null)
                    _line(
                      'Delivery',
                      totals.hasShipping ? moneyZar(totals.shippingTotal) : 'Free',
                    ),
                  if (totals != null)
                    _line('Total', moneyZar(totals.grandTotal), strong: true),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'By placing this order you agree to our terms. Cooling-off rights apply per ECTA s44 where eligible.',
            style: TextStyle(color: NbColors.mute, fontSize: 12),
          ),
          const SizedBox(height: 16),
          FilledButton(
            key: const Key('place-order'),
            onPressed: canPlace ? _place : null,
            child: _busy
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(
                    'Place order${totals == null ? '' : ' · ${moneyZar(totals.grandTotal)}'}',
                  ),
          ),
        ],
      ),
    );
  }

  Widget _line(String label, String value, {bool strong = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(fontWeight: strong ? FontWeight.w800 : null)),
          Text(
            value,
            style: TextStyle(
              fontFamily: 'monospace',
              fontWeight: strong ? FontWeight.w800 : null,
            ),
          ),
        ],
      ),
    );
  }
}

String asReference(Map<String, dynamic> data) => data['reference'] as String? ?? '';
