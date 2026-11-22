import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';

class StaffScreen extends ConsumerWidget {
  const StaffScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authStateProvider).valueOrNull?.user;
    if (user == null || !user.isStaffOps) {
      return const Scaffold(
        body: Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Staff only',
                  key: Key('staff-gate'),
                  style: TextStyle(fontWeight: FontWeight.w800, fontSize: 20),
                ),
                SizedBox(height: 8),
                Text(
                  'Sign in as staff@northbound.test',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: NbColors.mute),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final recon = ref.watch(reconProvider);
    final orders = ref.watch(staffOrdersProvider);
    final filter = ref.watch(staffFilterProvider);
    const filters = [
      ('', 'All'),
      ('awaiting_payment', 'Unpaid'),
      ('payment_confirmed', 'Paid'),
      ('packed', 'Packed'),
      ('out_for_delivery', 'Ship'),
      ('delivered', 'Done'),
      ('refunded', 'Refunded'),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Ops'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: () {
              ref.invalidate(staffOrdersProvider);
              ref.invalidate(reconProvider);
              ref.invalidate(refundsProvider);
            },
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          recon.when(
            loading: () => const LinearProgressIndicator(),
            error: (error, _) => Text('$error'),
            data: (report) {
              if (report == null) return const SizedBox.shrink();
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              "Today's recon",
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                          ),
                          Text(
                            report.date,
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              color: NbColors.mute,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      _line('Captured', moneyZar(report.grossCaptured)),
                      _line('Refunded', '− ${moneyZar(report.grossRefunded)}'),
                      _line('Net', moneyZar(report.net), strong: true),
                      const SizedBox(height: 6),
                      Text(
                        '${report.paymentsSucceeded} paid · ${report.paymentsPending} pending · ${report.exceptionCount} exceptions',
                        style: const TextStyle(color: NbColors.mute, fontSize: 12),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 12),
          const Text('Refunds', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          ref.watch(refundsProvider).when(
                loading: () => const LinearProgressIndicator(),
                error: (error, _) => Text('$error'),
                data: (rows) {
                  if (rows.isEmpty) {
                    return const Text(
                      'No refunds yet.',
                      style: TextStyle(color: NbColors.mute),
                    );
                  }
                  return Column(
                    children: [
                      for (final row in rows)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(
                            '${row.orderReference} · ${moneyZar(row.amount)}',
                            style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
                          ),
                          subtitle: Text(
                            [
                              if (row.reason.isNotEmpty) row.reason,
                              if (row.createdAt.isNotEmpty) row.createdAt,
                            ].join(' · '),
                          ),
                        ),
                    ],
                  );
                },
              ),
          const SizedBox(height: 12),
          SizedBox(
            height: 40,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: filters.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (_, index) {
                final item = filters[index];
                final on = filter == item.$1;
                return ChoiceChip(
                  label: Text(item.$2),
                  selected: on,
                  selectedColor: NbColors.forest,
                  labelStyle: TextStyle(color: on ? NbColors.lime : NbColors.ink),
                  onSelected: (_) {
                    ref.read(staffFilterProvider.notifier).state = item.$1;
                  },
                );
              },
            ),
          ),
          const SizedBox(height: 12),
          orders.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => Text('$error'),
            data: (list) {
              if (list.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                    'No orders match this filter.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: NbColors.mute),
                  ),
                );
              }
              return Column(
                children: [
                  for (final order in list) _StaffOrder(order: order),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _line(String label, String value, {bool strong = false}) {
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

class _StaffOrder extends ConsumerWidget {
  const _StaffOrder({required this.order});
  final OrderSummary order;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final closed = order.isClosed || order.awaitingPayment;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
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
              '${order.status} · ${order.itemCount} items · ${order.paymentMethod}',
              style: const TextStyle(color: NbColors.mute, fontSize: 12),
            ),
            const SizedBox(height: 8),
            if (order.awaitingPayment)
              const Text(
                'Awaiting customer payment',
                style: TextStyle(color: NbColors.mute, fontSize: 12),
              )
            else if (order.status == 'refunded')
              const Text(
                'Refunded',
                style: TextStyle(color: Color(0xFF2F7A4F), fontSize: 12),
              )
            else if (!closed)
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton(
                    onPressed: () => _advance(context, ref),
                    child: const Text('Advance'),
                  ),
                  OutlinedButton(
                    onPressed: () => _refund(context, ref),
                    child: const Text('Refund'),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _advance(BuildContext context, WidgetRef ref) async {
    final api = ref.read(apiProvider);
    try {
      await api.dio.post('/api/v1/orders/staff/${order.reference}/advance/');
      ref.invalidate(staffOrdersProvider);
      if (context.mounted) showAppMessage(context, '${order.reference} advanced');
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    }
  }

  Future<void> _refund(BuildContext context, WidgetRef ref) async {
    final amount = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Refund'),
        content: TextField(
          controller: amount,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(
            labelText: 'Amount in ZAR',
            hintText: 'Blank = full remaining',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Refund'),
          ),
        ],
      ),
    );
    if (confirmed != true) {
      amount.dispose();
      return;
    }
    final api = ref.read(apiProvider);
    try {
      final body = <String, dynamic>{
        'order_reference': order.reference,
        'reason': 'Staff refund from the app',
      };
      final raw = amount.text.trim();
      if (raw.isNotEmpty) body['amount'] = raw;
      await api.dio.post(
        '/api/v1/payments/refunds/',
        data: body,
        options: Options(headers: {'Idempotency-Key': newIdempotencyKey()}),
      );
      ref.invalidate(staffOrdersProvider);
      ref.invalidate(reconProvider);
      ref.invalidate(refundsProvider);
      if (context.mounted) showAppMessage(context, 'Refund issued');
    } catch (error) {
      if (context.mounted) showAppMessage(context, api.errorMessage(error));
    } finally {
      amount.dispose();
    }
  }
}
