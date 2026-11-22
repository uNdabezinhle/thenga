import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';
import '../theme.dart';
import '../widgets/product_card.dart';

class ShopScreen extends ConsumerWidget {
  const ShopScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(productsProvider);
    final user = ref.watch(authStateProvider).valueOrNull?.user;
    final query = ref.watch(catalogueQueryProvider);
    final categories = ref.watch(categoriesProvider).valueOrNull ?? kCategories;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Northbound'),
            Text(
              user == null ? 'Browsing as a guest' : 'Welcome back, ${user.name}',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w400,
                color: NbColors.mute,
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: CategoryChips(
              categories: categories,
              selected: query.category,
              onSelected: (id) {
                ref.read(catalogueQueryProvider.notifier).state =
                    query.copyWith(category: id);
              },
            ),
          ),
          Expanded(
            child: products.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (error, _) => _CatalogueMessage(
                title: 'Could not load catalogue',
                detail: '$error',
                onRetry: () => ref.invalidate(productsProvider),
              ),
              data: (list) {
                if (list.isEmpty) {
                  return const _CatalogueMessage(
                    title: 'Nothing in the catalogue yet',
                    detail: 'Try another category, or check that the API is running.',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async => ref.invalidate(productsProvider),
                  child: GridView.builder(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: 12,
                      crossAxisSpacing: 12,
                      childAspectRatio: 0.72,
                    ),
                    itemCount: list.length,
                    itemBuilder: (_, index) => ProductCard(product: list[index]),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _CatalogueMessage extends StatelessWidget {
  const _CatalogueMessage({
    required this.title,
    required this.detail,
    this.onRetry,
  });

  final String title;
  final String detail;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
            ),
            const SizedBox(height: 8),
            Text(
              detail,
              textAlign: TextAlign.center,
              style: const TextStyle(color: NbColors.mute),
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
            ],
          ],
        ),
      ),
    );
  }
}
