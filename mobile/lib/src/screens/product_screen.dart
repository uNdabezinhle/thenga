import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/models.dart';
import '../state/providers.dart';
import '../theme.dart';
import '../widgets/terrain_art.dart';

class _ReviewBox extends ConsumerStatefulWidget {
  const _ReviewBox({required this.productId, required this.onPosted});

  final int productId;
  final Future<void> Function() onPosted;

  @override
  ConsumerState<_ReviewBox> createState() => _ReviewBoxState();
}

class _ReviewBoxState extends ConsumerState<_ReviewBox> {
  final _body = TextEditingController();
  int _rating = 5;
  bool _busy = false;

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  Future<void> _post() async {
    final text = _body.text.trim();
    if (text.isEmpty) {
      showAppMessage(context, 'Write a short review.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(apiProvider).dio.post(
        '/api/v1/products/${widget.productId}/reviews/',
        data: {'rating': _rating, 'body': text},
      );
      _body.clear();
      await widget.onPosted();
      if (mounted) showAppMessage(context, 'Review posted');
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
    final signedIn = ref.watch(authStateProvider).valueOrNull?.isSignedIn ?? false;
    if (!signedIn) {
      return const Text(
        'Sign in to review this product.',
        style: TextStyle(color: NbColors.mute),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 6,
          children: [
            for (var star = 1; star <= 5; star++)
              ChoiceChip(
                label: Text('$star'),
                selected: _rating == star,
                onSelected: (_) => setState(() => _rating = star),
              ),
          ],
        ),
        const SizedBox(height: 8),
        TextField(
          key: const Key('review-body'),
          controller: _body,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(labelText: 'Your review'),
        ),
        const SizedBox(height: 8),
        OutlinedButton(
          onPressed: _busy ? null : _post,
          child: const Text('Post review'),
        ),
      ],
    );
  }
}

class ProductScreen extends ConsumerStatefulWidget {
  const ProductScreen({super.key, required this.productId});
  final int productId;

  @override
  ConsumerState<ProductScreen> createState() => _ProductScreenState();
}

class _ProductScreenState extends ConsumerState<ProductScreen> {
  Product? _product;
  ProductVariant? _variant;
  String? _error;
  bool _loading = true;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      final res = await api.dio.get('/api/v1/products/${widget.productId}/');
      final product = Product.fromJson(Map<String, dynamic>.from(res.data as Map));
      ProductVariant? variant;
      for (final item in product.variants) {
        if (item.stock > 0) {
          variant = item;
          break;
        }
      }
      variant ??= product.variants.isNotEmpty ? product.variants.first : null;
      if (!mounted) return;
      setState(() {
        _product = product;
        _variant = variant;
        _loading = false;
      });
      await ref.read(recentProvider.notifier).remember(product.id);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = ref.read(apiProvider).errorMessage(error);
        _loading = false;
      });
    }
  }

  Future<void> _add() async {
    final product = _product;
    final variant = _variant;
    if (product == null || variant == null || variant.stock <= 0) return;
    setState(() => _busy = true);
    try {
      await ref.read(cartProvider.notifier).addItem(
            productId: product.id,
            variantId: variant.id,
          );
      if (mounted) showAppMessage(context, '${product.name} added to cart');
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
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_error != null || _product == null) {
      return Scaffold(
        appBar: AppBar(),
        body: Center(child: Text(_error ?? 'Not found')),
      );
    }
    final product = _product!;
    final wished = ref.watch(wishlistProvider).contains(product.id);
    final variant = _variant;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          product.sku,
          style: const TextStyle(fontSize: 14, fontFamily: 'monospace'),
        ),
        actions: [
          IconButton(
            tooltip: wished ? 'Remove from wishlist' : 'Save to wishlist',
            onPressed: () => ref.read(wishlistProvider.notifier).toggle(product.id),
            icon: Icon(wished ? Icons.bookmark : Icons.bookmark_border),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(14),
            child: AspectRatio(
              aspectRatio: 4 / 3,
              child: ProductArt(
                hue: product.hue,
                imageUrl: product.imageUrl,
                iconSize: 72,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            product.brand.toUpperCase(),
            style: const TextStyle(
              fontSize: 11,
              color: NbColors.mute,
              letterSpacing: 0.6,
            ),
          ),
          Text(
            product.name,
            style: const TextStyle(
              fontSize: 23,
              fontWeight: FontWeight.w800,
              color: NbColors.ink,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '${product.rating} · ${product.reviews} reviews',
            style: const TextStyle(color: NbColors.mute),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                moneyZar(product.price),
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w600,
                  fontFamily: 'monospace',
                  color: NbColors.forest,
                ),
              ),
              if (product.compareAt.isNotEmpty && product.compareAt != product.price)
                Text(
                  moneyZar(product.compareAt),
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    color: NbColors.mute,
                    decoration: TextDecoration.lineThrough,
                  ),
                ),
            ],
          ),
          if (product.description != null && product.description!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              product.description!,
              style: const TextStyle(color: NbColors.mute, height: 1.5),
            ),
          ],
          const SizedBox(height: 20),
          const Text('Choose an option', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: product.variants.map((item) {
              final on = variant?.id == item.id;
              final disabled = item.stock <= 0;
              return ChoiceChip(
                label: Text(item.label),
                selected: on,
                onSelected: disabled ? null : (_) => setState(() => _variant = item),
              );
            }).toList(),
          ),
          const SizedBox(height: 10),
          Text(
            variant == null
                ? 'Select an option to see stock.'
                : variant.stock <= 0
                    ? 'Out of stock'
                    : variant.lowStock || variant.stock <= 3
                        ? 'Only ${variant.stock} left in stock'
                        : '${variant.stock} in stock',
            style: TextStyle(
              color: variant != null && variant.stock <= 3
                  ? const Color(0xFF9B3B1E)
                  : NbColors.mute,
            ),
          ),
          const SizedBox(height: 20),
          const Text('Specification', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          if (product.specs.isEmpty)
            const Text('No specs listed.', style: TextStyle(color: NbColors.mute))
          else
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                child: Column(
                  children: [
                    for (final spec in product.specs)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                spec.key,
                                style: const TextStyle(color: NbColors.mute),
                              ),
                            ),
                            Text(
                              spec.value,
                              style: const TextStyle(fontFamily: 'monospace'),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 20),
          const Text('What buyers say', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          if (product.reviewList.isEmpty)
            const Text('No reviews yet.', style: TextStyle(color: NbColors.mute))
          else
            for (final review in product.reviewList)
              Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  title: Text(review.who),
                  subtitle: Text(review.body),
                  trailing: Text('★' * review.rating.clamp(0, 5)),
                ),
              ),
          const SizedBox(height: 8),
          _ReviewBox(productId: product.id, onPosted: _load),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy || variant == null || variant.stock <= 0 ? null : _add,
            child: _busy
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(variant != null && variant.stock <= 0 ? 'Out of stock' : 'Add to cart'),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: () {
              ref.read(wishlistProvider.notifier).toggle(product.id);
              showAppMessage(
                context,
                wished ? 'Removed from wishlist' : 'Saved to wishlist',
              );
            },
            child: Text(wished ? 'Saved to wishlist' : 'Save to wishlist'),
          ),
        ],
      ),
    );
  }
}
