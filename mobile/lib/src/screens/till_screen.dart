import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:uuid/uuid.dart';

import '../state/providers.dart';
import '../theme.dart';

const _queueKey = 'nb_pos_queue';

class TillScreen extends ConsumerStatefulWidget {
  const TillScreen({super.key});

  @override
  ConsumerState<TillScreen> createState() => _TillScreenState();
}

class _TillLine {
  _TillLine({required this.name, required this.price, this.variantId, this.bundleId, this.quantity = 1});

  final String name;
  final String price;
  final int? variantId;
  final int? bundleId;
  int quantity;
}

class _TillScreenState extends ConsumerState<TillScreen> {
  final _search = TextEditingController();
  final _email = TextEditingController();
  final _code = TextEditingController();
  final _uuid = const Uuid();

  List<Map<String, dynamic>> _stores = [];
  String _store = 'harbour';
  List<Map<String, dynamic>> _hits = [];
  final List<_TillLine> _lines = [];
  String _tender = 'cash';
  String _note = '';
  String _receipt = '';
  bool _busy = false;
  int _queued = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _open());
  }

  @override
  void dispose() {
    _search.dispose();
    _email.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<List<Map<String, dynamic>>> _readQueue() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_queueKey);
    if (raw == null || raw.isEmpty) return [];
    final decoded = jsonDecode(raw);
    if (decoded is! List) return [];
    return decoded.whereType<Map>().map((row) => Map<String, dynamic>.from(row)).toList();
  }

  Future<void> _writeQueue(List<Map<String, dynamic>> rows) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_queueKey, jsonEncode(rows));
    if (mounted) setState(() => _queued = rows.length);
  }

  Future<void> _open() async {
    await _sync(silent: true);
    await _loadStores();
    await _loadCatalog('');
  }

  Future<void> _loadStores() async {
    try {
      final res = await ref.read(apiProvider).dio.get('/api/v1/pos/stores/');
      final rows = (res.data['results'] as List?) ?? [];
      if (!mounted) return;
      setState(() {
        _stores = rows.map((row) => Map<String, dynamic>.from(row as Map)).toList();
        if (_stores.isNotEmpty && !_stores.any((row) => row['code'] == _store)) {
          _store = _stores.first['code'].toString();
        }
      });
    } catch (_) {}
  }

  Future<void> _loadCatalog(String query) async {
    try {
      final res = await ref.read(apiProvider).dio.get(
        '/api/v1/pos/catalog/',
        queryParameters: {'store': _store, 'q': query},
      );
      final variants = (res.data['variants'] as List?) ?? [];
      final bundles = (res.data['bundles'] as List?) ?? [];
      if (!mounted) return;
      setState(() {
        _hits = [
          ...variants.map((row) => Map<String, dynamic>.from(row as Map)),
          ...bundles.map((row) => Map<String, dynamic>.from(row as Map)),
        ];
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _note = ref.read(apiProvider).errorMessage(error));
    }
  }

  Future<void> _submitSearch(String raw) async {
    final code = raw.trim();
    if (code.isEmpty) {
      await _loadCatalog('');
      return;
    }
    try {
      final res = await ref.read(apiProvider).dio.post(
        '/api/v1/pos/scan/',
        data: {'code': code, 'store_code': _store},
      );
      _addHit(Map<String, dynamic>.from(res.data as Map));
      _search.clear();
    } on DioException catch (error) {
      if (error.response == null) {
        if (mounted) setState(() => _note = 'Offline. Search needs the network.');
        return;
      }
      await _loadCatalog(code);
    }
  }

  void _addHit(Map<String, dynamic> hit) {
    final variantId = hit['variant_id'] as int?;
    final bundleId = hit['bundle_id'] as int?;
    final existing = _lines.where((line) {
      return (variantId != null && line.variantId == variantId) ||
          (bundleId != null && line.bundleId == bundleId);
    });
    setState(() {
      if (existing.isNotEmpty) {
        existing.first.quantity += 1;
      } else {
        _lines.add(
          _TillLine(
            name: '${hit['name'] ?? ''}',
            price: '${hit['unit_price'] ?? ''}',
            variantId: variantId,
            bundleId: bundleId,
          ),
        );
      }
    });
  }

  Map<String, dynamic> _payload(String key) {
    return {
      'store_code': _store,
      'tender': _tender,
      'customer_email': _email.text.trim(),
      'discount_code': _code.text.trim(),
      'idempotency_key': key,
      'lines': [
        for (final line in _lines)
          if (line.bundleId != null)
            {'bundle_id': line.bundleId, 'quantity': line.quantity}
          else
            {'variant_id': line.variantId, 'quantity': line.quantity},
      ],
    };
  }

  Future<void> _pay() async {
    if (_lines.isEmpty) {
      setState(() => _note = 'Add a line first.');
      return;
    }
    final key = _uuid.v4();
    final body = _payload(key);
    setState(() => _busy = true);
    try {
      final res = await ref.read(apiProvider).dio.post('/api/v1/pos/sales/', data: body);
      _showSale(Map<String, dynamic>.from(res.data as Map));
    } on DioException catch (error) {
      if (error.response == null) {
        final queued = await _readQueue();
        queued.add(body);
        await _writeQueue(queued);
        if (mounted) {
          setState(() {
            _lines.clear();
            _note = 'Saved offline. Sync when the till is back online.';
            _receipt = '';
          });
        }
      } else if (mounted) {
        setState(() => _note = ref.read(apiProvider).errorMessage(error));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _showSale(Map<String, dynamic> body) {
    final reference = body['reference'] ?? '';
    final total = body['grand_total'] ?? '';
    final redirect = '${body['redirect_url'] ?? ''}';
    setState(() {
      _lines.clear();
      _receipt = redirect.isEmpty
          ? '$reference · R $total'
          : '$reference is waiting for PayFast';
      _note = body['drawer_kick'] == true ? 'Cash drawer opened.' : '';
    });
    if (redirect.isNotEmpty && mounted) {
      showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('PayFast'),
          content: const Text('Finish this tender on the hosted checkout. The till does not mark it paid.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Stay')),
            TextButton(
              onPressed: () {
                Navigator.pop(context);
                launchUrl(Uri.parse(redirect), mode: LaunchMode.externalApplication);
              },
              child: const Text('Open checkout'),
            ),
          ],
        ),
      );
    }
  }

  Future<void> _sync({bool silent = false}) async {
    final queued = await _readQueue();
    if (mounted) setState(() => _queued = queued.length);
    if (queued.isEmpty) {
      if (!silent && mounted) setState(() => _note = 'Nothing waiting to sync.');
      return;
    }
    try {
      final res = await ref.read(apiProvider).dio.post(
        '/api/v1/pos/sales/sync/',
        data: {'sales': queued},
      );
      final results = (res.data['results'] as List?) ?? [];
      final failed = <Map<String, dynamic>>[];
      for (var i = 0; i < queued.length; i++) {
        final row = i < results.length ? results[i] : null;
        final ok = row is Map && row['ok'] == true;
        if (!ok) failed.add(queued[i]);
      }
      await _writeQueue(failed);
      if (mounted) {
        setState(() => _note = failed.isEmpty ? 'Offline sales synced.' : 'Some sales still need attention.');
      }
    } catch (error) {
      if (!silent && mounted) {
        setState(() => _note = ref.read(apiProvider).errorMessage(error));
      }
    }
  }

  Future<void> _drawer(String action) async {
    final amount = TextEditingController();
    final entered = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(action == 'open' ? 'Opening float' : 'Counted cash'),
        content: TextField(
          controller: amount,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(hintText: '0.00'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, amount.text.trim()), child: const Text('Save')),
        ],
      ),
    );
    amount.dispose();
    if (entered == null || entered.isEmpty) return;
    try {
      await ref.read(apiProvider).dio.post('/api/v1/pos/drawer/', data: {
        'action': action,
        'store_code': _store,
        if (action == 'open') 'opening_float': entered,
        if (action == 'close') 'closing_count': entered,
      });
      if (mounted) setState(() => _note = action == 'open' ? 'Drawer open.' : 'Drawer closed.');
    } catch (error) {
      if (mounted) setState(() => _note = ref.read(apiProvider).errorMessage(error));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Till'),
        actions: [
          TextButton(
            key: const Key('till-sync'),
            onPressed: _busy ? null : () => _sync(),
            child: Text('Sync $_queued'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_stores.length > 1)
            Wrap(
              spacing: 8,
              children: [
                for (final store in _stores)
                  ChoiceChip(
                    label: Text('${store['name']}'),
                    selected: store['code'] == _store,
                    onSelected: (_) {
                      setState(() => _store = '${store['code']}');
                      _loadCatalog(_search.text);
                    },
                  ),
              ],
            ),
          const SizedBox(height: 8),
          TextField(
            key: const Key('till-search'),
            controller: _search,
            autofocus: true,
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(
              labelText: 'Scan or search',
              hintText: 'Barcode, SKU, or name',
            ),
            onSubmitted: _submitSearch,
          ),
          const SizedBox(height: 8),
          for (final hit in _hits.take(8))
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: FilledButton(
                onPressed: () => _addHit(hit),
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                  alignment: Alignment.centerLeft,
                ),
                child: Text('${hit['name']}  ·  R ${hit['unit_price']}  ·  ${hit['available']}'),
              ),
            ),
          const Divider(),
          if (_lines.isEmpty)
            const Text('No lines yet.', style: TextStyle(color: NbColors.mute))
          else
            for (var i = 0; i < _lines.length; i++)
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(_lines[i].name),
                subtitle: Text('R ${_lines[i].price}'),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      onPressed: () => setState(() {
                        if (_lines[i].quantity > 1) {
                          _lines[i].quantity -= 1;
                        } else {
                          _lines.removeAt(i);
                        }
                      }),
                      icon: const Icon(Icons.remove),
                    ),
                    Text('${_lines[i].quantity}', style: const TextStyle(fontSize: 18)),
                    IconButton(
                      onPressed: () => setState(() => _lines[i].quantity += 1),
                      icon: const Icon(Icons.add),
                    ),
                  ],
                ),
              ),
          TextField(
            controller: _email,
            decoration: const InputDecoration(labelText: 'Customer email (optional)'),
            keyboardType: TextInputType.emailAddress,
          ),
          TextField(
            controller: _code,
            decoration: const InputDecoration(labelText: 'Discount code (optional)'),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              for (final tender in ['cash', 'card', 'payfast'])
                ChoiceChip(
                  label: Text(tender),
                  selected: _tender == tender,
                  onSelected: (_) => setState(() => _tender = tender),
                ),
            ],
          ),
          const SizedBox(height: 12),
          FilledButton(
            key: const Key('till-pay'),
            onPressed: _busy ? null : _pay,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
            child: Text(_busy ? 'Taking payment…' : 'Take ${_tender}'),
          ),
          if (_receipt.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(_receipt, key: const Key('till-receipt'), style: const TextStyle(fontWeight: FontWeight.w800)),
          ],
          if (_note.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_note, style: const TextStyle(color: NbColors.mute)),
            ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: OutlinedButton(onPressed: () => _drawer('open'), child: const Text('Open drawer'))),
              const SizedBox(width: 8),
              Expanded(child: OutlinedButton(onPressed: () => _drawer('close'), child: const Text('Close drawer'))),
            ],
          ),
        ],
      ),
    );
  }
}
