import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';

class StoreSettingsScreen extends ConsumerWidget {
  const StoreSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authStateProvider).valueOrNull?.user;
    if (user == null || !user.isStaffOps) {
      return const Scaffold(
        body: Center(child: Text('Staff only', key: Key('store-gate'))),
      );
    }
    final rates = ref.watch(shippingRatesProvider);
    final ads = ref.watch(staffAdsProvider);
    final promos = ref.watch(staffPromotionsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Store settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Delivery', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          rates.when(
            loading: () => const LinearProgressIndicator(),
            error: (error, _) => Text('$error'),
            data: (rows) => Column(
              children: [for (final rate in rows) _RateEditor(rate: rate)],
            ),
          ),
          const SizedBox(height: 16),
          const Text('Shop banner', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          ads.when(
            loading: () => const LinearProgressIndicator(),
            error: (error, _) => Text('$error'),
            data: (rows) {
              if (rows.isEmpty) {
                return const Text('No banner yet', style: TextStyle(color: NbColors.mute));
              }
              return Column(children: [for (final ad in rows) _AdEditor(ad: ad)]);
            },
          ),
          const SizedBox(height: 16),
          const Text('Shared promotion', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          promos.when(
            loading: () => const LinearProgressIndicator(),
            error: (error, _) => Text('$error'),
            data: (rows) {
              if (rows.isEmpty) {
                return const Text('No promotion yet', style: TextStyle(color: NbColors.mute));
              }
              return Column(
                children: [for (final promo in rows) _PromoEditor(promo: promo)],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _RateEditor extends ConsumerStatefulWidget {
  const _RateEditor({required this.rate});

  final ShippingRate rate;

  @override
  ConsumerState<_RateEditor> createState() => _RateEditorState();
}

class _RateEditorState extends ConsumerState<_RateEditor> {
  late final TextEditingController _price;
  late final TextEditingController _days;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _price = TextEditingController(text: widget.rate.price);
    _days = TextEditingController(text: widget.rate.estimatedDays);
  }

  @override
  void dispose() {
    _price.dispose();
    _days.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    try {
      await api.dio.patch(
        '/api/v1/orders/staff/shipping-rates/${widget.rate.id}/',
        data: {
          'price': _price.text.trim(),
          'estimated_days': _days.text.trim(),
        },
      );
      ref.invalidate(shippingRatesProvider);
      if (mounted) showAppMessage(context, '${widget.rate.methodName} saved');
    } catch (error) {
      if (mounted) showAppMessage(context, api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.rate.methodName, style: const TextStyle(fontWeight: FontWeight.w700)),
            TextField(
              controller: _price,
              decoration: const InputDecoration(labelText: 'Price (ZAR)'),
            ),
            TextField(
              controller: _days,
              decoration: const InputDecoration(labelText: 'Days'),
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton(
                onPressed: _busy ? null : _save,
                child: const Text('Save delivery'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AdEditor extends ConsumerStatefulWidget {
  const _AdEditor({required this.ad});

  final ShopAd ad;

  @override
  ConsumerState<_AdEditor> createState() => _AdEditorState();
}

class _AdEditorState extends ConsumerState<_AdEditor> {
  late final TextEditingController _title;
  late final TextEditingController _body;
  late final TextEditingController _slug;
  late bool _active;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _title = TextEditingController(text: widget.ad.title);
    _body = TextEditingController(text: widget.ad.body);
    _slug = TextEditingController(text: widget.ad.productSlug);
    _active = widget.ad.isActive;
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    _slug.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    try {
      await api.dio.patch(
        '/api/v1/ads/staff/${widget.ad.id}/',
        data: {
          'title': _title.text.trim(),
          'body': _body.text.trim(),
          'product_slug': _slug.text.trim(),
          'is_active': _active,
        },
      );
      ref.invalidate(staffAdsProvider);
      ref.invalidate(adsProvider);
      if (mounted) showAppMessage(context, 'Banner saved');
    } catch (error) {
      if (mounted) showAppMessage(context, api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            TextField(controller: _title, decoration: const InputDecoration(labelText: 'Title')),
            TextField(controller: _body, decoration: const InputDecoration(labelText: 'Body')),
            TextField(
              controller: _slug,
              decoration: const InputDecoration(labelText: 'Product slug'),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Active'),
              value: _active,
              onChanged: (value) => setState(() => _active = value),
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton(
                onPressed: _busy ? null : _save,
                child: const Text('Save banner'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PromoEditor extends ConsumerStatefulWidget {
  const _PromoEditor({required this.promo});

  final StaffPromotion promo;

  @override
  ConsumerState<_PromoEditor> createState() => _PromoEditorState();
}

class _PromoEditorState extends ConsumerState<_PromoEditor> {
  late final TextEditingController _title;
  late final TextEditingController _description;
  late final TextEditingController _amount;
  late final TextEditingController _starts;
  late final TextEditingController _ends;
  late bool _active;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _title = TextEditingController(text: widget.promo.title);
    _description = TextEditingController(text: widget.promo.description);
    _amount = TextEditingController(text: widget.promo.amount);
    _starts = TextEditingController(text: widget.promo.startsAt);
    _ends = TextEditingController(text: widget.promo.endsAt);
    _active = widget.promo.isActive;
  }

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    _amount.dispose();
    _starts.dispose();
    _ends.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    final api = ref.read(apiProvider);
    String? when(TextEditingController controller) {
      final value = controller.text.trim();
      return value.isEmpty ? null : value;
    }

    try {
      await api.dio.patch(
        '/api/v1/promotions/staff/${widget.promo.code}/',
        data: {
          'title': _title.text.trim(),
          'description': _description.text.trim(),
          'amount': _amount.text.trim(),
          'is_active': _active,
          'starts_at': when(_starts),
          'ends_at': when(_ends),
        },
      );
      ref.invalidate(staffPromotionsProvider);
      ref.invalidate(promotionsProvider);
      if (mounted) showAppMessage(context, '${widget.promo.code} saved');
    } catch (error) {
      if (mounted) showAppMessage(context, api.errorMessage(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.promo.code, style: const TextStyle(fontWeight: FontWeight.w700)),
            TextField(controller: _title, decoration: const InputDecoration(labelText: 'Title')),
            TextField(
              controller: _description,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
            TextField(
              controller: _amount,
              decoration: InputDecoration(
                labelText: widget.promo.discountType == 'percentage' ? 'Percent' : 'Amount (ZAR)',
              ),
            ),
            TextField(
              controller: _starts,
              decoration: const InputDecoration(labelText: 'Starts'),
            ),
            TextField(
              controller: _ends,
              decoration: const InputDecoration(labelText: 'Ends'),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Active'),
              value: _active,
              onChanged: (value) => setState(() => _active = value),
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton(
                onPressed: _busy ? null : _save,
                child: const Text('Save promotion'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
