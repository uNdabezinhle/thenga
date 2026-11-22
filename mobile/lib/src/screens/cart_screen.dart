import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';
import '../theme.dart';
import '../widgets/terrain_art.dart';
import 'checkout_screen.dart';

class CartScreen extends ConsumerWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cart = ref.watch(cartProvider);
    final signedIn = ref.watch(authStateProvider).valueOrNull?.isSignedIn ?? false;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cart'),
        actions: [
          cart.maybeWhen(
            data: (snapshot) => snapshot != null && snapshot.items.isNotEmpty
                ? TextButton(
                    onPressed: () async {
                      try {
                        await ref.read(cartProvider.notifier).clear();
                        if (context.mounted) showAppMessage(context, 'Cart cleared');
                      } catch (error) {
                        if (context.mounted) {
                          showAppMessage(
                            context,
                            ref.read(apiProvider).errorMessage(error),
                          );
                        }
                      }
                    },
                    child: const Text('Clear all'),
                  )
                : const SizedBox.shrink(),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: cart.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('$error', textAlign: TextAlign.center),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => ref.read(cartProvider.notifier).refresh(),
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
        data: (snapshot) {
          if (snapshot == null || snapshot.items.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.shopping_bag_outlined, size: 40, color: NbColors.mute),
                    const SizedBox(height: 12),
                    const Text(
                      'Your cart is empty',
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 18),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Everything you add stays here, whether or not you sign in.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: NbColors.mute),
                    ),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: () {
                        ref.read(shellTabProvider.notifier).state = NbTab.shop;
                      },
                      child: const Text('Browse the shop'),
                    ),
                  ],
                ),
              ),
            );
          }
          final totals = snapshot.totals;
          final discount = snapshot.discount;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                '${snapshot.totalItems} item${snapshot.totalItems == 1 ? '' : 's'}',
                style: const TextStyle(color: NbColors.mute),
              ),
              const SizedBox(height: 8),
              for (final item in snapshot.items)
                Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: SizedBox(
                            width: 64,
                            height: 64,
                            child: TerrainArt(hue: item.hue, iconSize: 28),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      item.productName,
                                      style: const TextStyle(fontWeight: FontWeight.w600),
                                    ),
                                  ),
                                  Text(
                                    moneyZar(item.lineTotal),
                                    style: const TextStyle(fontFamily: 'monospace'),
                                  ),
                                ],
                              ),
                              if (item.variantLabel.isNotEmpty)
                                Text(
                                  item.variantLabel,
                                  style: const TextStyle(color: NbColors.mute, fontSize: 12),
                                ),
                              const SizedBox(height: 8),
                              Row(
                                children: [
                                  _Qty(
                                    quantity: item.quantity,
                                    onMinus: () {
                                      if (item.quantity <= 1) {
                                        ref.read(cartProvider.notifier).remove(item.id);
                                      } else {
                                        ref
                                            .read(cartProvider.notifier)
                                            .updateQty(item.id, item.quantity - 1);
                                      }
                                    },
                                    onPlus: () => ref
                                        .read(cartProvider.notifier)
                                        .updateQty(item.id, item.quantity + 1),
                                  ),
                                  const Spacer(),
                                  TextButton(
                                    onPressed: () async {
                                      if (!signedIn) {
                                        showAppMessage(context, 'Sign in to save for later');
                                        return;
                                      }
                                      try {
                                        await ref
                                            .read(cartProvider.notifier)
                                            .saveForLater(item.id);
                                        await ref.read(savedProvider.notifier).refresh();
                                        if (context.mounted) {
                                          showAppMessage(context, 'Moved to Saved');
                                        }
                                      } catch (error) {
                                        if (context.mounted) {
                                          showAppMessage(
                                            context,
                                            ref.read(apiProvider).errorMessage(error),
                                          );
                                        }
                                      }
                                    },
                                    child: const Text('Save for later'),
                                  ),
                                  IconButton(
                                    tooltip: 'Remove',
                                    onPressed: () =>
                                        ref.read(cartProvider.notifier).remove(item.id),
                                    icon: const Icon(Icons.delete_outline, color: Color(0xFF9B3B1E)),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              const SizedBox(height: 8),
              const Text('Discount code', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              if (discount != null)
                Card(
                  color: const Color(0xFFF7FBEE),
                  child: ListTile(
                    title: Text(
                      discount.code,
                      style: const TextStyle(fontFamily: 'monospace'),
                    ),
                    subtitle: Text(discount.label),
                    trailing: TextButton(
                      onPressed: () async {
                        try {
                          await ref.read(cartProvider.notifier).removeDiscount();
                        } catch (error) {
                          if (context.mounted) {
                            showAppMessage(
                              context,
                              ref.read(apiProvider).errorMessage(error),
                            );
                          }
                        }
                      },
                      child: const Text('Remove'),
                    ),
                  ),
                )
              else
                const _DiscountField(),
              const SizedBox(height: 16),
              const Text('Delivery', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              for (final estimate in snapshot.shippingEstimates)
                Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                      color: estimate.isSelected ? NbColors.forest : NbColors.hair,
                      width: estimate.isSelected ? 1.6 : 1,
                    ),
                  ),
                  child: ListTile(
                    onTap: () =>
                        ref.read(cartProvider.notifier).selectShipping(estimate.id),
                    leading: Icon(
                      estimate.isSelected
                          ? Icons.radio_button_checked
                          : Icons.radio_button_off,
                      color: NbColors.forest,
                    ),
                    title: Text(estimate.methodName),
                    subtitle: Text(estimate.estimatedDays),
                    trailing: Text(
                      estimate.isFree ? 'Free' : moneyZar(estimate.price),
                      style: const TextStyle(fontFamily: 'monospace'),
                    ),
                  ),
                ),
              const Divider(height: 28),
              _TotalLine(label: 'Subtotal', value: moneyZar(totals.subtotal)),
              if (totals.hasDiscount)
                _TotalLine(
                  label: 'Discount',
                  value: '− ${moneyZar(totals.discountTotal)}',
                  emphasis: true,
                ),
              _TotalLine(
                label: 'Delivery',
                value: totals.hasShipping ? moneyZar(totals.shippingTotal) : 'Free',
              ),
              _TotalLine(
                label: 'Total',
                value: moneyZar(totals.grandTotal),
                strong: true,
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const CheckoutScreen()),
                  );
                },
                child: Text('Checkout · ${moneyZar(totals.grandTotal)}'),
              ),
              if (!signedIn)
                const Padding(
                  padding: EdgeInsets.only(top: 10),
                  child: Text(
                    'Signing in will merge this guest cart into your account.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: NbColors.mute, fontSize: 12),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _Qty extends StatelessWidget {
  const _Qty({
    required this.quantity,
    required this.onMinus,
    required this.onPlus,
  });

  final int quantity;
  final VoidCallback onMinus;
  final VoidCallback onPlus;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(onPressed: onMinus, icon: const Icon(Icons.remove, size: 18)),
        Text('$quantity'),
        IconButton(onPressed: onPlus, icon: const Icon(Icons.add, size: 18)),
      ],
    );
  }
}

class _DiscountField extends ConsumerStatefulWidget {
  const _DiscountField();

  @override
  ConsumerState<_DiscountField> createState() => _DiscountFieldState();
}

class _DiscountFieldState extends ConsumerState<_DiscountField> {
  final _code = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _apply() async {
    final code = _code.text.trim();
    if (code.isEmpty) return;
    setState(() => _busy = true);
    try {
      await ref.read(cartProvider.notifier).applyDiscount(code);
      _code.clear();
      if (mounted) showAppMessage(context, 'Discount applied');
    } catch (error) {
      if (mounted) {
        showAppMessage(context, ref.read(apiProvider).errorMessage(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: TextField(
                key: const Key('discount-code'),
                controller: _code,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  hintText: 'Enter code',
                  filled: true,
                  fillColor: Colors.white,
                ),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: _busy ? null : _apply,
              child: const Text('Apply'),
            ),
          ],
        ),
        const Padding(
          padding: EdgeInsets.only(top: 6),
          child: Text(
            'Try DISCOUNT20',
            style: TextStyle(color: NbColors.mute, fontSize: 12),
          ),
        ),
      ],
    );
  }
}

class _TotalLine extends StatelessWidget {
  const _TotalLine({
    required this.label,
    required this.value,
    this.strong = false,
    this.emphasis = false,
  });

  final String label;
  final String value;
  final bool strong;
  final bool emphasis;

  @override
  Widget build(BuildContext context) {
    final style = TextStyle(
      fontWeight: strong ? FontWeight.w800 : FontWeight.w500,
      fontSize: strong ? 18 : 14,
      fontFamily: 'monospace',
      color: emphasis ? const Color(0xFF2F7A4F) : NbColors.ink,
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: style.copyWith(fontFamily: null)),
          Text(value, style: style),
        ],
      ),
    );
  }
}
