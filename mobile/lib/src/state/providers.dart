import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

import '../api/client.dart';
import '../models/models.dart';

final apiProvider = Provider<RekaApi>((ref) => RekaApi());

/// Hosted shop from the web address. Empty means the Northbound sample.
String shopMerchantSlug() {
  if (!kIsWeb) return '';
  return (Uri.base.queryParameters['merchant'] ?? '').trim().toLowerCase();
}

Map<String, dynamic> merchantQuery([Map<String, dynamic> params = const {}]) {
  final slug = shopMerchantSlug();
  if (slug.isEmpty) return params;
  return {...params, 'merchant': slug};
}

class NbTab {
  static const shop = 0;
  static const search = 1;
  static const cart = 2;
  static const saved = 3;
  static const account = 4;
  static const staff = 5;
}

final shellTabProvider = StateProvider<int>((ref) => NbTab.shop);

class CatalogueChip {
  const CatalogueChip(this.id, this.label);
  final String id;
  final String label;
}

const kCategories = <CatalogueChip>[
  CatalogueChip('all', 'Everything'),
  CatalogueChip('packs', 'Packs'),
  CatalogueChip('shells', 'Shells'),
  CatalogueChip('sleep', 'Sleep'),
  CatalogueChip('tools', 'Tools'),
];

class CatalogueQuery {
  const CatalogueQuery({
    this.q = '',
    this.category = 'all',
    this.sort = 'featured',
    this.brand = '',
    this.priceMin = '',
    this.priceMax = '',
  });

  final String q;
  final String category;
  final String sort;
  final String brand;
  final String priceMin;
  final String priceMax;

  CatalogueQuery copyWith({
    String? q,
    String? category,
    String? sort,
    String? brand,
    String? priceMin,
    String? priceMax,
  }) {
    return CatalogueQuery(
      q: q ?? this.q,
      category: category ?? this.category,
      sort: sort ?? this.sort,
      brand: brand ?? this.brand,
      priceMin: priceMin ?? this.priceMin,
      priceMax: priceMax ?? this.priceMax,
    );
  }
}

const kAppVersion = '1.0.0';

bool isNewerVersion(String latest, String current) {
  List<int> parts(String value) {
    return value
        .split('.')
        .map((part) => int.tryParse(part.trim()) ?? 0)
        .toList();
  }

  final left = parts(latest);
  final right = parts(current);
  final length = left.length > right.length ? left.length : right.length;
  for (var i = 0; i < length; i++) {
    final a = i < left.length ? left[i] : 0;
    final b = i < right.length ? right[i] : 0;
    if (a != b) return a > b;
  }
  return false;
}

final catalogueQueryProvider =
    StateProvider<CatalogueQuery>((ref) => const CatalogueQuery());

Map<String, dynamic> _queryParams(CatalogueQuery query) {
  final params = <String, dynamic>{'page_size': 100};
  if (query.category.isNotEmpty && query.category != 'all') {
    params['category'] = query.category;
  }
  if (query.q.trim().isNotEmpty) params['q'] = query.q.trim();
  if (query.sort.isNotEmpty && query.sort != 'featured') {
    params['sort'] = query.sort;
  }
  if (query.brand.trim().isNotEmpty) params['brand'] = query.brand.trim();
  if (query.priceMin.trim().isNotEmpty) params['price_min'] = query.priceMin.trim();
  if (query.priceMax.trim().isNotEmpty) params['price_max'] = query.priceMax.trim();
  return merchantQuery(params);
}

final categoriesProvider = FutureProvider<List<CatalogueChip>>((ref) async {
  try {
    final api = ref.watch(apiProvider);
    final res = await api.dio.get(
      '/api/v1/products/meta/categories/',
      queryParameters: merchantQuery({}),
    );
    final chips = <CatalogueChip>[
      const CatalogueChip('all', 'Everything'),
      for (final row in jsonMaps(res.data))
        if (asString(row['slug']).isNotEmpty)
          CatalogueChip(asString(row['slug']), asString(row['name'], asString(row['slug']))),
    ];
    return chips.length > 1 ? chips : kCategories;
  } catch (_) {
    return kCategories;
  }
});

final brandsProvider = FutureProvider<List<CatalogueChip>>((ref) async {
  try {
    final api = ref.watch(apiProvider);
    final res = await api.dio.get(
      '/api/v1/products/meta/brands/',
      queryParameters: merchantQuery({}),
    );
    return [
      for (final row in jsonMaps(res.data))
        if (asString(row['slug']).isNotEmpty)
          CatalogueChip(asString(row['slug']), asString(row['name'], asString(row['slug']))),
    ];
  } catch (_) {
    return const [];
  }
});

final appVersionProvider = FutureProvider<AppVersionInfo>((ref) async {
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/app/version-check/');
  return AppVersionInfo.fromJson(Map<String, dynamic>.from(res.data as Map));
});

List<Product> _productsFrom(dynamic data) =>
    jsonMaps(data).map(Product.fromJson).toList();

final allProductsProvider = FutureProvider<List<Product>>((ref) async {
  final api = ref.watch(apiProvider);
  final res = await api.dio.get(
    '/api/v1/products/',
    queryParameters: merchantQuery({'page_size': 100}),
  );
  return _productsFrom(res.data);
});

final productsProvider = FutureProvider.autoDispose<List<Product>>((ref) async {
  final api = ref.watch(apiProvider);
  final query = ref.watch(catalogueQueryProvider);
  final res = await api.dio.get(
    '/api/v1/products/',
    queryParameters: _queryParams(query),
  );
  return _productsFrom(res.data);
});

final authStateProvider =
    StateNotifierProvider<AuthNotifier, AsyncValue<AuthSession>>((ref) {
  return AuthNotifier(ref.watch(apiProvider));
});

class AuthNotifier extends StateNotifier<AsyncValue<AuthSession>> {
  AuthNotifier(this._api, {bool bootstrap = true})
      : super(const AsyncValue.data(AuthSession())) {
    _ready = bootstrap ? _bootstrap() : Future<void>.value();
  }

  final RekaApi _api;
  late final Future<void> _ready;

  Future<void> _bootstrap() async {
    try {
      if (!await _api.hasAccessToken()) return;
      final me = await _loadMe();
      await _api.setMfaEnrolled(me.mfaEnabled);
      state = AsyncValue.data(AuthSession(user: me, mfaEnabled: me.mfaEnabled));
    } catch (_) {
      await _api.clearTokens();
      state = const AsyncValue.data(AuthSession());
    }
  }

  Future<UserMe> _loadMe() async {
    final me = await _api.dio.get('/api/v1/auth/users/me/');
    var displayName = '';
    try {
      final prof = await _api.dio.get('/api/v1/auth/profiles/');
      final rows = jsonMaps(prof.data);
      if (rows.isNotEmpty) {
        displayName = asString(rows.first['display_name']);
      }
    } catch (_) {}
    return UserMe.fromJson(
      Map<String, dynamic>.from(me.data as Map),
      displayName: displayName,
    );
  }

  Future<void> refreshMe() async {
    final session = state.valueOrNull;
    if (session == null || !session.isSignedIn) return;
    final me = await _loadMe();
    await _api.setMfaEnrolled(me.mfaEnabled);
    state = AsyncValue.data(
      session.copyWith(user: me, mfaEnabled: me.mfaEnabled),
    );
  }

  Future<void> _mergeCart() async {
    try {
      final session = await _api.cartSessionId();
      await _api.dio.post(
        '/api/v1/cart/cart/transfer_cart/',
        data: {'session_id': session},
      );
    } catch (_) {}
  }

  Future<void> _establish(Map<String, dynamic> tokens, {required bool mfa}) async {
    final access = tokens['access'] as String?;
    final refresh = tokens['refresh'] as String?;
    if (access == null || refresh == null) {
      throw StateError('Sign-in did not return a token pair.');
    }
    await _api.saveTokens(access: access, refresh: refresh);
    final me = await _loadMe();
    final enrolled = me.mfaEnabled || mfa;
    await _api.setMfaEnrolled(enrolled);
    await _mergeCart();
    state = AsyncValue.data(
      AuthSession(user: me, mfaEnabled: enrolled),
    );
  }

  /// Returns when the password step finishes. MFA stops here and waits
  /// for [verifyMfa]. A code is never submitted automatically.
  Future<void> login(String email, String password) async {
    await _ready;
    final res = await _api.dio.post(
      '/api/v1/auth/token/',
      data: {'email': email, 'password': password},
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    if (data['mfa_required'] == true || data['pre_auth_token'] != null) {
      final pre = data['pre_auth_token'] as String?;
      if (pre == null || pre.isEmpty) {
        throw StateError('MFA is required but no pre-auth token was issued.');
      }
      state = AsyncValue.data(
        AuthSession(preAuthToken: pre, pendingEmail: email),
      );
      return;
    }
    await _establish(data, mfa: false);
  }

  void cancelChallenge() {
    state = const AsyncValue.data(AuthSession());
  }

  Future<void> verifyMfa(String code, {bool backup = false}) async {
    await _ready;
    final session = state.valueOrNull ?? const AuthSession();
    final pre = session.preAuthToken;
    if (pre == null || pre.isEmpty) {
      throw StateError('No MFA challenge is in progress.');
    }
    final res = await _api.dio.post(
      '/api/v1/auth/mfa/verify/',
      data: {
        'code': code.trim(),
        'device_type': backup ? 'backup' : 'authenticator',
        'pre_auth_token': pre,
      },
      options: Options(headers: {'Authorization': 'Bearer $pre'}),
    );
    await _establish(
      Map<String, dynamic>.from(res.data as Map),
      mfa: true,
    );
  }

  Future<void> register({
    required String email,
    required String username,
    required String password,
    required String password2,
    String referralCode = '',
  }) async {
    await _ready;
    final code = referralCode.trim();
    final res = await _api.dio.post(
      '/api/v1/auth/users/',
      data: {
        'email': email,
        'username': username,
        'password': password,
        'password2': password2,
        if (code.isNotEmpty) 'referral_code': code,
      },
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    final token = data['dev_email_token'] as String?;
    if (token != null && token.isNotEmpty) {
      await _api.dio.post(
        '/api/v1/auth/email/verify/',
        data: {'token': token},
      );
    }
    await login(email, password);
  }

  Future<void> social(String provider) async {
    await _ready;
    final res = await _api.dio.post(
      '/api/v1/auth/social/$provider/',
      data: {
        'email': 'jordan@northbound.test',
        'username': 'jordan.m',
      },
    );
    await _establish(
      Map<String, dynamic>.from(res.data as Map),
      mfa: false,
    );
  }

  Future<String> setupMfa() async {
    final res = await _api.dio.post(
      '/api/v1/auth/mfa/setup/',
      data: {'device_type': 'authenticator'},
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    await _api.setMfaEnrolled(true);
    final session = state.valueOrNull ?? const AuthSession();
    state = AsyncValue.data(session.copyWith(mfaEnabled: true, backupCodes: const []));
    return asString(data['secret']);
  }

  Future<void> disableMfa() async {
    await _api.dio.delete('/api/v1/auth/mfa/disable/');
    await _api.setMfaEnrolled(false);
    final session = state.valueOrNull ?? const AuthSession();
    state = AsyncValue.data(
      session.copyWith(mfaEnabled: false, backupCodes: const []),
    );
  }

  Future<List<String>> generateBackupCodes() async {
    final res = await _api.dio.post('/api/v1/auth/mfa/generate_backup_codes/');
    final data = Map<String, dynamic>.from(res.data as Map);
    final codes = (data['backup_codes'] as List? ?? [])
        .map((code) => code.toString())
        .toList();
    final session = state.valueOrNull ?? const AuthSession();
    state = AsyncValue.data(session.copyWith(backupCodes: codes, mfaEnabled: true));
    return codes;
  }

  Future<void> logout() async {
    final refresh = await _api.readRefresh();
    if (refresh != null && refresh.isNotEmpty) {
      try {
        await _api.dio.post(
          '/api/v1/auth/logout/',
          data: {'refresh': refresh},
        );
      } catch (_) {}
    }
    await _api.clearTokens();
    await _api.setMfaEnrolled(false);
    await _api.rotateCartSession();
    state = const AsyncValue.data(AuthSession());
  }
}

final cartProvider =
    StateNotifierProvider<CartNotifier, AsyncValue<CartSnapshot?>>((ref) {
  return CartNotifier(ref.watch(apiProvider));
});

class CartNotifier extends StateNotifier<AsyncValue<CartSnapshot?>> {
  CartNotifier(this._api, {bool load = true}) : super(const AsyncValue.data(null)) {
    if (load) refresh();
  }

  final RekaApi _api;

  Future<void> refresh() async {
    if (state.valueOrNull == null) {
      state = const AsyncValue.loading();
    }
    try {
      final res = await _api.dio.get('/api/v1/cart/cart/');
      state = AsyncValue.data(
        CartSnapshot.fromJson(Map<String, dynamic>.from(res.data as Map)),
      );
    } catch (error, stack) {
      state = AsyncValue.error(_api.errorMessage(error), stack);
    }
  }

  void _store(Response<dynamic> res) {
    state = AsyncValue.data(
      CartSnapshot.fromJson(Map<String, dynamic>.from(res.data as Map)),
    );
  }

  Future<void> addBundle(int bundleId) async {
    final res = await _api.dio.post('/api/v1/promotions/bundles/$bundleId/add/');
    _store(res);
  }

  Future<void> addItem({
    required int productId,
    required int variantId,
    int quantity = 1,
  }) async {
    final res = await _api.dio.post(
      '/api/v1/cart/cart/add_item/',
      data: {
        'product': productId,
        'variant': variantId,
        'quantity': quantity,
      },
    );
    _store(res);
  }

  Future<void> updateQty(int itemId, int quantity) async {
    final res = await _api.dio.post(
      '/api/v1/cart/cart/items/$itemId/update/',
      data: {'quantity': quantity},
    );
    _store(res);
  }

  Future<void> remove(int itemId) async {
    final res = await _api.dio.delete('/api/v1/cart/cart/items/$itemId/remove/');
    _store(res);
  }

  Future<void> clear() async {
    final res = await _api.dio.post('/api/v1/cart/cart/clear/');
    _store(res);
  }

  Future<void> applyDiscount(String code) async {
    final res = await _api.dio.post(
      '/api/v1/cart/cart/apply_discount/',
      data: {'code': code.trim().toUpperCase()},
    );
    _store(res);
  }

  Future<void> removeDiscount() async {
    final res = await _api.dio.post('/api/v1/cart/cart/remove_discount/', data: {});
    _store(res);
  }

  Future<void> selectShipping(int shippingMethodId) async {
    final res = await _api.dio.post(
      '/api/v1/cart/cart/select_shipping/',
      data: {'shipping_method_id': shippingMethodId},
    );
    _store(res);
  }

  Future<void> saveForLater(int itemId) async {
    await _api.dio.post('/api/v1/cart/cart/items/$itemId/save-for-later/');
    await refresh();
  }
}

final savedProvider =
    StateNotifierProvider<SavedNotifier, AsyncValue<List<SavedItem>>>((ref) {
  return SavedNotifier(ref.watch(apiProvider), ref.watch(authStateProvider));
});

class SavedNotifier extends StateNotifier<AsyncValue<List<SavedItem>>> {
  SavedNotifier(this._api, AsyncValue<AuthSession> auth)
      : super(const AsyncValue.data([])) {
    final signedIn = auth.valueOrNull?.isSignedIn ?? false;
    if (signedIn) refresh();
  }

  final RekaApi _api;

  Future<void> refresh() async {
    try {
      final res = await _api.dio.get('/api/v1/cart/saved-items/');
      state = AsyncValue.data(jsonMaps(res.data).map(SavedItem.fromJson).toList());
    } catch (error, stack) {
      state = AsyncValue.error(_api.errorMessage(error), stack);
    }
  }

  Future<void> moveToCart(int itemId) async {
    await _api.dio.post('/api/v1/cart/saved-items/$itemId/move_to_cart/');
    await refresh();
  }
}

final ordersProvider = FutureProvider.autoDispose<List<OrderSummary>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth == null || !auth.isSignedIn) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/orders/');
  return jsonMaps(res.data).map(OrderSummary.fromJson).toList();
});

final staffFilterProvider = StateProvider<String>((ref) => '');

final staffOrdersProvider =
    FutureProvider.autoDispose<List<OrderSummary>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return [];
  final api = ref.watch(apiProvider);
  final status = ref.watch(staffFilterProvider);
  final res = await api.dio.get(
    '/api/v1/orders/staff/',
    queryParameters: status.isEmpty ? null : {'status': status},
  );
  return jsonMaps(res.data).map(OrderSummary.fromJson).toList();
});

final reconProvider = FutureProvider.autoDispose<ReconReport?>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return null;
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/payments/reconciliation/');
  return ReconReport.fromJson(Map<String, dynamic>.from(res.data as Map));
});

final wishlistProvider =
    StateNotifierProvider<WishlistNotifier, Set<int>>((ref) {
  return WishlistNotifier();
});

final recentProvider = StateNotifierProvider<RecentNotifier, List<int>>((ref) {
  return RecentNotifier();
});

class RecentNotifier extends StateNotifier<List<int>> {
  RecentNotifier({bool load = true}) : super(const []) {
    if (load) _load();
  }

  static const _key = 'nb_recent';
  static const _cap = 8;

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getStringList(_key) ?? const [];
      state = [
        for (final item in raw)
          if (int.tryParse(item) != null) int.parse(item),
      ].take(_cap).toList();
    } catch (_) {}
  }

  Future<void> remember(int id) async {
    final next = [id, ...state.where((item) => item != id)].take(_cap).toList();
    state = next;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(_key, next.map((value) => value.toString()).toList());
    } catch (_) {}
  }
}

class WishlistNotifier extends StateNotifier<Set<int>> {
  WishlistNotifier() : super({}) {
    _load();
  }

  static const _key = 'nb_wishlist';

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getStringList(_key) ?? const [];
      state = {
        for (final item in raw)
          if (int.tryParse(item) != null) int.parse(item),
      };
    } catch (_) {}
  }

  Future<void> toggle(int id) async {
    final next = {...state};
    if (!next.add(id)) next.remove(id);
    state = next;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(
        _key,
        next.map((value) => value.toString()).toList(),
      );
    } catch (_) {}
  }

  bool contains(int id) => state.contains(id);
}

final addressesProvider =
    FutureProvider.autoDispose<List<AddressBookEntry>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth == null || !auth.isSignedIn) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/orders/addresses/');
  return jsonMaps(res.data).map(AddressBookEntry.fromJson).toList();
});

final profileProvider = FutureProvider.autoDispose<UserProfile?>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth == null || !auth.isSignedIn) return null;
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/auth/profiles/');
  final rows = jsonMaps(res.data);
  if (rows.isEmpty) return null;
  return UserProfile.fromJson(rows.first);
});

final bundlesProvider = FutureProvider<List<ShopBundle>>((ref) async {
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/promotions/bundles/');
  return jsonMaps(res.data).map(ShopBundle.fromJson).toList();
});

final loyaltyProvider = FutureProvider.autoDispose<LoyaltyStatus?>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth == null || !auth.isSignedIn) return null;
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/promotions/loyalty/');
  return LoyaltyStatus.fromJson(Map<String, dynamic>.from(res.data as Map));
});

final promotionsProvider = FutureProvider<List<PromotionOffer>>((ref) async {
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/promotions/');
  return jsonMaps(res.data).map(PromotionOffer.fromJson).toList();
});

final adsProvider = FutureProvider<List<ShopAd>>((ref) async {
  final api = ref.watch(apiProvider);
  final res = await api.dio.get(
    '/api/v1/ads/',
    queryParameters: merchantQuery({'placement': 'shop_top'}),
  );
  return jsonMaps(res.data).map(ShopAd.fromJson).toList();
});

final inboxProvider = FutureProvider.autoDispose<List<InboxNote>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth == null || !auth.isSignedIn) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/notifications/inbox/');
  return jsonMaps(res.data).map(InboxNote.fromJson).toList();
});

final notificationPrefsProvider =
    FutureProvider.autoDispose<NotificationPrefs?>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth == null || !auth.isSignedIn) return null;
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/notifications/preferences/');
  return NotificationPrefs.fromJson(Map<String, dynamic>.from(res.data as Map));
});

final shippingRatesProvider =
    FutureProvider.autoDispose<List<ShippingRate>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/orders/staff/shipping-rates/');
  return jsonMaps(res.data).map(ShippingRate.fromJson).toList();
});

final staffAdsProvider = FutureProvider.autoDispose<List<ShopAd>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/ads/staff/');
  return jsonMaps(res.data).map(ShopAd.fromJson).toList();
});

final staffFlashesProvider = FutureProvider.autoDispose<List<StaffFlash>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/promotions/staff/flashes/');
  return jsonMaps(res.data).map(StaffFlash.fromJson).toList();
});

final staffBundlesProvider = FutureProvider.autoDispose<List<StaffBundle>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/promotions/staff/bundles/');
  return jsonMaps(res.data).map(StaffBundle.fromJson).toList();
});

final staffPromotionsProvider =
    FutureProvider.autoDispose<List<StaffPromotion>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/promotions/staff/');
  return jsonMaps(res.data).map(StaffPromotion.fromJson).toList();
});

final devicesProvider = FutureProvider.autoDispose<List<PushDevice>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth == null || !auth.isSignedIn) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/notifications/devices/');
  return jsonMaps(res.data).map(PushDevice.fromJson).toList();
});

final refundsProvider = FutureProvider.autoDispose<List<RefundRow>>((ref) async {
  final auth = ref.watch(authStateProvider).valueOrNull;
  if (auth?.user?.isStaffOps != true) return [];
  final api = ref.watch(apiProvider);
  final res = await api.dio.get('/api/v1/payments/refunds/list/');
  return jsonMaps(res.data).map(RefundRow.fromJson).toList();
});

class SessionDebug {
  const SessionDebug({
    required this.tokenPrefix,
    required this.mfaVerified,
    required this.cartSession,
    required this.apiBase,
  });

  final String tokenPrefix;
  final bool? mfaVerified;
  final String cartSession;
  final String apiBase;
}

final sessionDebugProvider = FutureProvider<SessionDebug>((ref) async {
  ref.watch(authStateProvider);
  final api = ref.watch(apiProvider);
  var token = '';
  var cart = '';
  try {
    token = await api.readAccess() ?? '';
  } catch (_) {}
  try {
    cart = await api.cartSessionId();
  } catch (_) {}
  return SessionDebug(
    tokenPrefix: token.isEmpty ? '—' : token.substring(0, token.length < 12 ? token.length : 12),
    mfaVerified: token.isEmpty ? null : jwtBoolClaim(token, 'mfa_verified'),
    cartSession: cart.isEmpty ? '—' : cart.substring(0, cart.length < 8 ? cart.length : 8),
    apiBase: api.baseUrl,
  );
});

const defaultAddress = '14 Harbour Lane, Cape Town 8001';

String newIdempotencyKey() => const Uuid().v4();
