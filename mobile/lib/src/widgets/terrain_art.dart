import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

class TerrainArt extends StatelessWidget {
  const TerrainArt({super.key, required this.hue, this.iconSize = 48});

  final int hue;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: HSLColor.fromAHSL(1, hue.toDouble(), 0.34, 0.93).toColor(),
      child: Center(
        child: Icon(
          Icons.terrain,
          size: iconSize,
          color: HSLColor.fromAHSL(1, hue.toDouble(), 0.42, 0.26).toColor(),
        ),
      ),
    );
  }
}

class ProductArt extends StatefulWidget {
  const ProductArt({
    super.key,
    required this.hue,
    this.imageUrl,
    this.iconSize = 48,
  });

  final int hue;
  final String? imageUrl;
  final double iconSize;

  @override
  State<ProductArt> createState() => _ProductArtState();
}

class _ProductArtState extends State<ProductArt> {
  String? _svg;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(ProductArt oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.imageUrl != widget.imageUrl) {
      _svg = null;
      _failed = false;
      _load();
    }
  }

  Future<void> _load() async {
    final url = widget.imageUrl;
    if (url == null || url.isEmpty) return;
    try {
      final response = await Dio().get<String>(
        url,
        options: Options(responseType: ResponseType.plain),
      );
      final body = response.data ?? '';
      if (!mounted) return;
      if (!body.contains('<svg')) {
        setState(() => _failed = true);
        return;
      }
      setState(() => _svg = body);
    } catch (_) {
      if (mounted) setState(() => _failed = true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final svg = _svg;
    if (svg == null || _failed) {
      return TerrainArt(hue: widget.hue, iconSize: widget.iconSize);
    }
    return SvgPicture.string(
      svg,
      fit: BoxFit.cover,
      width: double.infinity,
      height: double.infinity,
    );
  }
}
