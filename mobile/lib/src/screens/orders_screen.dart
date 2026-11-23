import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';

class OrdersScreen extends ConsumerStatefulWidget {
  const OrdersScreen({super.key});

  @override
  ConsumerState<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends ConsumerState<OrdersScreen>
    with WidgetsBindingObserver {
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    _poll?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      ref.invalidate(ordersProvider);
    }
  }

  void _watchUnpaid(List<OrderSummary> orders) {
    final waiting = orders.any((order) => order.awaitingPayment);
    if (waiting && _poll == null) {
      _poll = Timer.periodic(const Duration(seconds: 4), (_) {
        ref.invalidate(ordersProvider);
      });
    } else if (!waiting) {
      _poll?.cancel();
      _poll = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authStateProvider).valueOrNull;
    final orders = ref.watch(ordersProvider);
    final loaded = orders.valueOrNull;
    if (loaded != null) _watchUnpaid(loaded);

    return Scaffold(
      appBar: AppBar(title: const Text('Orders')),
      body: auth == null || !auth.isSignedIn
          ? const Center(
              child: Text(
                'Sign in to see orders',
                style: TextStyle(color: NbColors.mute),
              ),
            )
          : orders.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('$error', textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: () => ref.invalidate(ordersProvider),
                      child: const Text('Try again'),
                    ),
                  ],
                ),
              ),
              data: (list) {
                if (list.isEmpty) {
                  return const Center(
                    child: Text(
                      'No orders yet',
                      style: TextStyle(color: NbColors.mute),
                    ),
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(ordersProvider),
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: list.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (_, index) => _OrderCard(order: list[index]),
                  ),
                );
              },
            ),
    );
  }
}

class _OrderCard extends ConsumerWidget {
  const _OrderCard({required this.order});
  final OrderSummary order;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final date = formatWhen(order.placedAt);
    final stage = order.trackingStage.clamp(0, orderStages.length - 1);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    order.reference,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Text(
                  moneyZar(order.grandTotal),
                  style: const TextStyle(fontFamily: 'monospace'),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              [
                if (date.isNotEmpty) date,
                '${order.itemCount} items',
                if (order.shippingMethod.isNotEmpty) order.shippingMethod,
                order.status,
              ].join(' · '),
              style: const TextStyle(color: NbColors.mute, fontSize: 12),
            ),
            if (order.shipTo.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Ship to ${order.shipTo}',
                style: const TextStyle(color: NbColors.mute, fontSize: 12),
              ),
            ],
            if (order.lines.isNotEmpty) ...[
              const SizedBox(height: 8),
              for (final line in order.lines)
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Row(
                    children: [
                      Expanded(child: Text('${line.quantity} × ${line.name}')),
                      Text(
                        moneyZar(line.lineTotal),
                        style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                      ),
                    ],
                  ),
                ),
            ],
            const SizedBox(height: 8),
            _money('Subtotal', moneyZar(order.subtotal)),
            if ((double.tryParse(order.discountTotal) ?? 0) > 0)
              _money('Discount', '− ${moneyZar(order.discountTotal)}'),
            _money(
              'Delivery',
              (double.tryParse(order.shippingTotal) ?? 0) > 0
                  ? moneyZar(order.shippingTotal)
                  : 'Free',
            ),
            _money('Total', moneyZar(order.grandTotal), strong: true),
            if (order.events.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text('History', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              for (final event in order.events)
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Text(
                    [
                      if (formatWhen(event.createdAt).isNotEmpty)
                        formatWhen(event.createdAt),
                      event.toStatus,
                      if (event.note.isNotEmpty) event.note,
                    ].join(' · '),
                    style: const TextStyle(color: NbColors.mute, fontSize: 12),
                  ),
                ),
            ],
            const SizedBox(height: 12),
            for (var i = 0; i < orderStages.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Icon(
                      i <= stage ? Icons.check_circle : Icons.circle_outlined,
                      size: 16,
                      color: i <= stage ? NbColors.forest : NbColors.mute,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        orderStages[i],
                        style: TextStyle(
                          color: i <= stage ? NbColors.ink : NbColors.mute,
                          fontWeight: i == stage ? FontWeight.w700 : FontWeight.w400,
                        ),
                      ),
                    ),
                    if (i == stage)
                      const Text(
                        'Current',
                        style: TextStyle(fontSize: 11, color: NbColors.mute),
                      ),
                  ],
                ),
              ),
            if (order.shipment != null || order.status == 'packed') ...[
              const SizedBox(height: 8),
              ShipmentTracking(shipment: order.shipment),
            ],
            if (order.awaitingPayment) ...[
              const SizedBox(height: 8),
              FilledButton(
                onPressed: () => _pay(context, ref),
                child: const Text('Complete sandbox payment'),
              ),
            ],
            if (!order.awaitingPayment && !order.isClosed) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => _invoice(context, ref),
                child: const Text('View tax invoice'),
              ),
            ],
            if (order.coolingOff.eligible) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => _coolingOff(context, ref),
                child: const Text('Exercise 7-day cooling-off'),
              ),
              Text(
                'ECTA s44 · ${order.coolingOff.daysRemaining} day(s) left · full refund',
                style: const TextStyle(color: NbColors.mute, fontSize: 12),
              ),
            ],
            if (!order.awaitingPayment &&
                !order.isClosed &&
                order.trackingStage < 4) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => _advance(context, ref),
                child: const Text('Advance fulfilment'),
              ),
            ],
            if (order.canCancel) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => _cancel(context, ref),
                child: const Text('Cancel order'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _pay(BuildContext context, WidgetRef ref) async {
    final api = ref.read(apiProvider);
    try {
      await api.dio.post(
        '/api/v1/payments/sandbox/complete/',
        data: {'order_reference': order.reference},
      );
      ref.invalidate(ordersProvider);
      if (context.mounted) showAppMessage(context, 'Payment confirmed');
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    }
  }

  Future<void> _invoice(BuildContext context, WidgetRef ref) async {
    final api = ref.read(apiProvider);
    try {
      final res = await api.dio.get(
        '/api/v1/orders/${order.reference}/invoice/',
        queryParameters: const {'format': 'json'},
      );
      final invoice = TaxInvoice.fromJson(Map<String, dynamic>.from(res.data as Map));
      if (!context.mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => InvoiceScreen(invoice: invoice)),
      );
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    }
  }

  Future<void> _cancel(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel this order?'),
        content: const Text(
          'You can cancel before the order goes out for delivery. Stock is released.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep order'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel order'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final api = ref.read(apiProvider);
    try {
      await api.dio.post('/api/v1/orders/${order.reference}/cancel/');
      ref.invalidate(ordersProvider);
      if (context.mounted) showAppMessage(context, 'Order cancelled');
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    }
  }

  Future<void> _coolingOff(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Exercise cooling-off?'),
        content: const Text(
          'This cancels the order and issues a full refund under ECTA s44.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep order'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Refund'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final api = ref.read(apiProvider);
    try {
      await api.dio.post(
        '/api/v1/orders/${order.reference}/cooling-off/exercise/',
        data: {'reason': 'Customer cooling-off (ECTA s44)'},
      );
      ref.invalidate(ordersProvider);
      if (context.mounted) showAppMessage(context, 'Cooling-off accepted — full refund issued');
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    }
  }

  Future<void> _advance(BuildContext context, WidgetRef ref) async {
    final api = ref.read(apiProvider);
    try {
      await api.dio.post('/api/v1/orders/${order.reference}/advance/');
      ref.invalidate(ordersProvider);
      if (context.mounted) showAppMessage(context, 'Status updated');
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    }
  }
}

Widget _money(String label, String value, {bool strong = false}) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 1),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: TextStyle(fontWeight: strong ? FontWeight.w800 : null)),
        Text(
          value,
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
            fontWeight: strong ? FontWeight.w800 : null,
          ),
        ),
      ],
    ),
  );
}

class InvoiceScreen extends StatelessWidget {
  const InvoiceScreen({super.key, required this.invoice});

  final TaxInvoice invoice;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(invoice.invoiceNumber)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            invoice.merchantName,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text('VAT ${invoice.vatNumber}', style: const TextStyle(color: NbColors.mute)),
          Text(invoice.merchantAddress, style: const TextStyle(color: NbColors.mute)),
          const SizedBox(height: 12),
          Text('Issued ${invoice.issuedAt}'),
          Text('Bill to ${invoice.customerEmail}'),
          Text('Ship to ${invoice.shipTo}'),
          const SizedBox(height: 12),
          for (final line in invoice.lines)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '${asInt(line['qty'])} × ${asString(line['name'])}',
                    ),
                  ),
                  Text(
                    moneyZar(asString(line['line_total'], '0.00')),
                    style: const TextStyle(fontFamily: 'monospace'),
                  ),
                ],
              ),
            ),
          const Divider(),
          _row('Subtotal', moneyZar(invoice.subtotal)),
          _row('Discount', moneyZar(invoice.discount)),
          _row('Delivery', moneyZar(invoice.shipping)),
          _row('Net', moneyZar(invoice.netAmount)),
          _row('VAT ${invoice.vatRate}%', moneyZar(invoice.vatAmount)),
          _row('Total', moneyZar(invoice.grandTotal), strong: true),
        ],
      ),
    );
  }

  Widget _row(String label, String value, {bool strong = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
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

class ShipmentTracking extends StatelessWidget {
  const ShipmentTracking({super.key, required this.shipment});

  final ShipmentInfo? shipment;

  @override
  Widget build(BuildContext context) {
    final booked = shipment?.isBooked ?? false;
    if (!booked) {
      return const Text(
        'Waiting for the courier',
        key: Key('shipment-waiting'),
        style: TextStyle(color: NbColors.mute, fontSize: 12),
      );
    }
    final info = shipment!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          info.carrier.isEmpty ? 'Courier' : info.carrier,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 2),
        Text(
          info.trackingNumber,
          key: const Key('shipment-tracking'),
          style: const TextStyle(fontFamily: 'monospace'),
        ),
        for (final event in info.events)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              [
                if (formatWhen(event.createdAt).isNotEmpty) formatWhen(event.createdAt),
                _shipmentLabel(event.status),
                if (event.note.isNotEmpty) event.note,
              ].join(' · '),
              style: const TextStyle(color: NbColors.mute, fontSize: 12),
            ),
          ),
      ],
    );
  }
}

String _shipmentLabel(String status) {
  switch (status) {
    case 'dispatched':
      return 'Dispatched';
    case 'in_transit':
      return 'In transit';
    case 'delivered':
      return 'Delivered';
    case 'pending':
      return 'Waiting for the courier';
    default:
      return status;
  }
}
