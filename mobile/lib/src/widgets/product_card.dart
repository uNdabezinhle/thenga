import 'package:flutter/material.dart';

import '../models/models.dart';
import '../screens/product_screen.dart';
import '../state/providers.dart';
import '../theme.dart';
import 'terrain_art.dart';

class ProductCard extends StatelessWidget {
  const ProductCard({super.key, required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: NbColors.hair),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => ProductScreen(productId: product.id),
            ),
          );
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  ProductArt(hue: product.hue, imageUrl: product.imageUrl),
                  if (product.soldOut)
                    const Positioned(
                      top: 8,
                      left: 8,
                      child: _SoldOutTag(),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(11, 9, 11, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    product.brand.toUpperCase(),
                    style: const TextStyle(
                      fontSize: 10.5,
                      color: NbColors.mute,
                      letterSpacing: 0.4,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    product.name,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: NbColors.ink,
                    ),
                  ),
                  const SizedBox(height: 6),
                  _PriceLine(product: product),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PriceLine extends StatelessWidget {
  const _PriceLine({required this.product});

  final Product product;

  @override
  Widget build(BuildContext context) {
    final sale = product.compareAt.isNotEmpty && product.compareAt != product.price;
    return Wrap(
      spacing: 6,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text(
          moneyZar(product.price),
          style: const TextStyle(
            fontFamily: 'monospace',
            fontWeight: FontWeight.w600,
            color: NbColors.forest,
            fontSize: 13,
          ),
        ),
        if (sale)
          Text(
            moneyZar(product.compareAt),
            key: Key('compare-${product.id}'),
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 11,
              color: NbColors.mute,
              decoration: TextDecoration.lineThrough,
            ),
          ),
      ],
    );
  }
}

class _SoldOutTag extends StatelessWidget {
  const _SoldOutTag();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: NbColors.ink,
        borderRadius: BorderRadius.circular(5),
      ),
      child: const Text(
        'SOLD OUT',
        style: TextStyle(
          color: Colors.white,
          fontSize: 9.5,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.8,
        ),
      ),
    );
  }
}

class CategoryChips extends StatelessWidget {
  const CategoryChips({
    super.key,
    required this.selected,
    required this.onSelected,
    this.categories = kCategories,
  });

  final String selected;
  final ValueChanged<String> onSelected;
  final List<CatalogueChip> categories;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 40,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: categories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, index) {
          final chip = categories[index];
          final on = chip.id == selected;
          return ChoiceChip(
            label: Text(chip.label),
            selected: on,
            selectedColor: NbColors.forest,
            labelStyle: TextStyle(
              color: on ? NbColors.lime : NbColors.ink,
              fontSize: 12.5,
            ),
            onSelected: (_) => onSelected(chip.id),
          );
        },
      ),
    );
  }
}
