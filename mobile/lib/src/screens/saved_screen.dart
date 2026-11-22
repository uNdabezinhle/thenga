import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';
import '../theme.dart';
import '../widgets/product_card.dart';
import '../widgets/terrain_art.dart';

class SavedScreen extends ConsumerWidget {
  const SavedScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final signedIn = ref.watch(authStateProvider).valueOrNull?.isSignedIn ?? false;
    final saved = ref.watch(savedProvider);
    final wishedIds = ref.watch(wishlistProvider);
    final catalogue = ref.watch(allProductsProvider).valueOrNull ?? const [];

    final wished = [
      for (final id in wishedIds)
        for (final product in catalogue)
          if (product.id == id) product,
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Saved')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (!signedIn)
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: Text(
                'Sign in to keep items you set aside. The wishlist on this device stays either way.',
                style: TextStyle(color: NbColors.mute),
              ),
            ),
          saved.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (error, _) => Text('$error'),
            data: (items) {
              if (items.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    'Nothing saved for later yet. Use “Save for later” in the cart after you sign in.',
                    style: TextStyle(color: NbColors.mute),
                  ),
                );
              }
              return Column(
                children: [
                  for (final item in items)
                    Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      child: ListTile(
                        leading: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: SizedBox(
                            width: 48,
                            height: 48,
                            child: TerrainArt(hue: item.hue, iconSize: 22),
                          ),
                        ),
                        title: Text(item.productName),
                        subtitle: Text(
                          item.variantLabel.isEmpty
                              ? moneyZar(item.unitPrice)
                              : '${item.variantLabel} · ${moneyZar(item.unitPrice)}',
                        ),
                        trailing: TextButton(
                          onPressed: () async {
                            try {
                              await ref.read(savedProvider.notifier).moveToCart(item.id);
                              await ref.read(cartProvider.notifier).refresh();
                              if (context.mounted) {
                                showAppMessage(context, 'Moved to cart');
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
                          child: const Text('Move to cart'),
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
          if (wished.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Wishlist', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 0.72,
              ),
              itemCount: wished.length,
              itemBuilder: (_, index) => ProductCard(product: wished[index]),
            ),
          ],
        ],
      ),
    );
  }
}
