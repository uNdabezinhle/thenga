import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';
import '../theme.dart';
import '../widgets/product_card.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  late final TextEditingController _query;
  late final TextEditingController _min;
  late final TextEditingController _max;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    final query = ref.read(catalogueQueryProvider);
    _query = TextEditingController(text: query.q);
    _min = TextEditingController(text: query.priceMin);
    _max = TextEditingController(text: query.priceMax);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    _min.dispose();
    _max.dispose();
    super.dispose();
  }

  void _applyPrice() {
    final current = ref.read(catalogueQueryProvider);
    ref.read(catalogueQueryProvider.notifier).state = current.copyWith(
      priceMin: _min.text.trim(),
      priceMax: _max.text.trim(),
    );
  }

  void _setQuery(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 320), () {
      final current = ref.read(catalogueQueryProvider);
      ref.read(catalogueQueryProvider.notifier).state = current.copyWith(q: value);
    });
  }

  @override
  Widget build(BuildContext context) {
    final products = ref.watch(productsProvider);
    final query = ref.watch(catalogueQueryProvider);
    final categories = ref.watch(categoriesProvider).valueOrNull ?? kCategories;
    final brands = ref.watch(brandsProvider).valueOrNull ?? const <CatalogueChip>[];
    const sorts = [
      ('featured', 'Featured'),
      ('low', 'Price ↑'),
      ('high', 'Price ↓'),
      ('rated', 'Top rated'),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Search')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: TextField(
              controller: _query,
              decoration: InputDecoration(
                hintText: 'Search packs, shells, stoves...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: query.q.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear',
                        onPressed: () {
                          _query.clear();
                          ref.read(catalogueQueryProvider.notifier).state =
                              query.copyWith(q: '');
                        },
                        icon: const Icon(Icons.close),
                      ),
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(999),
                  borderSide: const BorderSide(color: NbColors.hair),
                ),
              ),
              onChanged: _setQuery,
            ),
          ),
          SizedBox(
            height: 40,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: sorts.length,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (_, index) {
                final sort = sorts[index];
                final on = query.sort == sort.$1;
                return ChoiceChip(
                  label: Text(sort.$2),
                  selected: on,
                  selectedColor: NbColors.forest,
                  labelStyle: TextStyle(color: on ? NbColors.lime : NbColors.ink),
                  onSelected: (_) {
                    ref.read(catalogueQueryProvider.notifier).state =
                        query.copyWith(sort: sort.$1);
                  },
                );
              },
            ),
          ),
          if (brands.isNotEmpty)
            SizedBox(
              height: 40,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                itemCount: brands.length + 1,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (_, index) {
                  final chip = index == 0 ? const CatalogueChip('', 'Any brand') : brands[index - 1];
                  final on = query.brand == chip.id;
                  return ChoiceChip(
                    label: Text(chip.label),
                    selected: on,
                    selectedColor: NbColors.forest,
                    labelStyle: TextStyle(color: on ? NbColors.lime : NbColors.ink, fontSize: 12.5),
                    onSelected: (_) {
                      ref.read(catalogueQueryProvider.notifier).state =
                          query.copyWith(brand: chip.id);
                    },
                  );
                },
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _min,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Min price',
                      isDense: true,
                    ),
                    onSubmitted: (_) => _applyPrice(),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _max,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Max price',
                      isDense: true,
                    ),
                    onSubmitted: (_) => _applyPrice(),
                  ),
                ),
                const SizedBox(width: 8),
                TextButton(onPressed: _applyPrice, child: const Text('Apply')),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
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
              error: (error, _) => Center(child: Text('$error')),
              data: (list) {
                if (list.isEmpty) {
                  final term = query.q.isEmpty ? 'that filter' : '“${query.q}”';
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                        'Nothing matched $term.\nTry a broader term, or clear the category filter.',
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: NbColors.mute),
                      ),
                    ),
                  );
                }
                return GridView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                    childAspectRatio: 0.72,
                  ),
                  itemCount: list.length,
                  itemBuilder: (_, index) => ProductCard(product: list[index]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
