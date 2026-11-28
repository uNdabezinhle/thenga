int asInt(dynamic value, [int fallback = 0]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value) ?? fallback;
  return fallback;
}

double asDouble(dynamic value, [double fallback = 0]) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? fallback;
  return fallback;
}

String asString(dynamic value, [String fallback = '']) {
  if (value == null) return fallback;
  return value.toString();
}

List<Map<String, dynamic>> jsonMaps(dynamic data) {
  final raw = data is Map && data['results'] is List
      ? data['results'] as List
      : data is List
          ? data
          : const [];
  return [
    for (final item in raw)
      if (item is Map) Map<String, dynamic>.from(item),
  ];
}

class ProductSpec {
  const ProductSpec({required this.key, required this.value});
  final String key;
  final String value;

  factory ProductSpec.fromJson(Map<String, dynamic> json) => ProductSpec(
        key: asString(json['key']),
        value: asString(json['value']),
      );
}

class ProductReview {
  const ProductReview({
    required this.who,
    required this.rating,
    required this.body,
  });

  final String who;
  final int rating;
  final String body;

  factory ProductReview.fromJson(Map<String, dynamic> json) => ProductReview(
        who: asString(json['who'], 'Customer'),
        rating: asInt(json['rating']),
        body: asString(json['body']),
      );
}

class Product {
  Product({
    required this.id,
    required this.sku,
    required this.name,
    required this.brand,
    required this.category,
    required this.price,
    this.compareAt = '',
    required this.currency,
    required this.rating,
    required this.reviews,
    required this.hue,
    required this.soldOut,
    this.imageUrl,
    this.description,
    this.variants = const [],
    this.specs = const [],
    this.reviewList = const [],
  });

  final int id;
  final String sku;
  final String name;
  final String brand;
  final String category;
  final String price;
  final String compareAt;
  final String currency;
  final double rating;
  final int reviews;
  final int hue;
  final bool soldOut;
  final String? imageUrl;
  final String? description;
  final List<ProductVariant> variants;
  final List<ProductSpec> specs;
  final List<ProductReview> reviewList;

  factory Product.fromJson(Map<String, dynamic> json) => Product(
        id: asInt(json['id']),
        sku: asString(json['sku']),
        name: asString(json['name']),
        brand: asString(json['brand']),
        category: asString(json['category']),
        price: asString(json['price'], '0.00'),
        compareAt: asString(json['compare_at']),
        currency: asString(json['currency'], 'ZAR'),
        rating: asDouble(json['rating']),
        reviews: asInt(json['reviews']),
        hue: asInt(json['hue'], 150),
        soldOut: json['sold_out'] as bool? ?? false,
        imageUrl: json['image_url'] as String?,
        description: json['description'] as String?,
        variants: (json['variants'] as List? ?? [])
            .whereType<Map>()
            .map((e) => ProductVariant.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
        specs: (json['specs'] as List? ?? [])
            .whereType<Map>()
            .map((e) => ProductSpec.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
        reviewList: (json['review_list'] as List? ?? [])
            .whereType<Map>()
            .map((e) => ProductReview.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
      );
}

class ProductVariant {
  ProductVariant({
    required this.id,
    required this.label,
    required this.stock,
    required this.unitPrice,
    this.lowStock = false,
  });

  final int id;
  final String label;
  final int stock;
  final String unitPrice;
  final bool lowStock;

  factory ProductVariant.fromJson(Map<String, dynamic> json) => ProductVariant(
        id: asInt(json['id']),
        label: asString(json['label']),
        stock: asInt(json['stock']),
        unitPrice: asString(json['unit_price'], '0.00'),
        lowStock: json['low_stock'] as bool? ?? false,
      );
}

class CartTotals {
  const CartTotals({
    required this.subtotal,
    required this.discountTotal,
    required this.shippingTotal,
    required this.grandTotal,
  });

  final String subtotal;
  final String discountTotal;
  final String shippingTotal;
  final String grandTotal;

  factory CartTotals.fromJson(Map<String, dynamic>? json) {
    final map = json ?? const {};
    return CartTotals(
      subtotal: asString(map['subtotal'], '0.00'),
      discountTotal: asString(map['discount_total'], '0.00'),
      shippingTotal: asString(map['shipping_total'], '0.00'),
      grandTotal: asString(map['grand_total'], '0.00'),
    );
  }

  bool get hasDiscount => (double.tryParse(discountTotal) ?? 0) > 0;
  bool get hasShipping => (double.tryParse(shippingTotal) ?? 0) > 0;
}

class CartDiscount {
  const CartDiscount({
    required this.id,
    required this.code,
    required this.discountType,
    required this.amount,
  });

  final int id;
  final String code;
  final String discountType;
  final String amount;

  factory CartDiscount.fromJson(Map<String, dynamic> json) => CartDiscount(
        id: asInt(json['id']),
        code: asString(json['code']),
        discountType: asString(json['discount_type']),
        amount: asString(json['amount'], '0.00'),
      );

  String get label =>
      discountType == 'percentage' ? '$amount% off' : 'R $amount off';
}

class ShippingEstimate {
  const ShippingEstimate({
    required this.id,
    required this.methodName,
    required this.price,
    required this.estimatedDays,
    required this.isSelected,
  });

  final int id;
  final String methodName;
  final String price;
  final String estimatedDays;
  final bool isSelected;

  factory ShippingEstimate.fromJson(Map<String, dynamic> json) =>
      ShippingEstimate(
        id: asInt(json['id']),
        methodName: asString(json['method_name']),
        price: asString(json['price'], '0.00'),
        estimatedDays: asString(json['estimated_days']),
        isSelected: json['is_selected'] as bool? ?? false,
      );

  bool get isFree => (double.tryParse(price) ?? 0) <= 0;
}

class CartSnapshot {
  CartSnapshot({
    required this.id,
    required this.items,
    required this.totalItems,
    required this.totals,
    this.discounts = const [],
    this.shippingEstimates = const [],
  });

  final int id;
  final List<CartItem> items;
  final int totalItems;
  final CartTotals totals;
  final List<CartDiscount> discounts;
  final List<ShippingEstimate> shippingEstimates;

  factory CartSnapshot.fromJson(Map<String, dynamic> json) => CartSnapshot(
        id: asInt(json['id']),
        items: (json['items'] as List? ?? [])
            .whereType<Map>()
            .map((e) => CartItem.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
        totalItems: asInt(json['total_items']),
        totals: CartTotals.fromJson(
          json['totals'] is Map
              ? Map<String, dynamic>.from(json['totals'] as Map)
              : null,
        ),
        discounts: (json['discounts'] as List? ?? [])
            .whereType<Map>()
            .map((e) => CartDiscount.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
        shippingEstimates: (json['shipping_estimates'] as List? ?? [])
            .whereType<Map>()
            .map((e) => ShippingEstimate.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
      );

  String get grandTotal => totals.grandTotal;
  CartDiscount? get discount => discounts.isEmpty ? null : discounts.first;
}

class CartItem {
  CartItem({
    required this.id,
    required this.productId,
    required this.productName,
    required this.variantLabel,
    required this.quantity,
    required this.unitPrice,
    required this.lineTotal,
    required this.hue,
  });

  final int id;
  final int productId;
  final String productName;
  final String variantLabel;
  final int quantity;
  final String unitPrice;
  final String lineTotal;
  final int hue;

  factory CartItem.fromJson(Map<String, dynamic> json) => CartItem(
        id: asInt(json['id']),
        productId: asInt(json['product_id']),
        productName: asString(json['product_name']),
        variantLabel: asString(json['variant_label']),
        quantity: asInt(json['quantity']),
        unitPrice: asString(json['unit_price'], '0.00'),
        lineTotal: asString(json['line_total'], '0.00'),
        hue: asInt(json['hue'], 150),
      );
}

class SavedItem {
  const SavedItem({
    required this.id,
    required this.productId,
    required this.productName,
    required this.variantLabel,
    required this.unitPrice,
    required this.hue,
  });

  final int id;
  final int productId;
  final String productName;
  final String variantLabel;
  final String unitPrice;
  final int hue;

  factory SavedItem.fromJson(Map<String, dynamic> json) => SavedItem(
        id: asInt(json['id']),
        productId: asInt(json['product_id']),
        productName: asString(json['product_name']),
        variantLabel: asString(json['variant_label']),
        unitPrice: asString(json['unit_price'], '0.00'),
        hue: asInt(json['hue'], 150),
      );
}

class UserMe {
  UserMe({
    required this.id,
    required this.email,
    required this.username,
    required this.emailVerified,
    required this.isStaffOps,
    this.displayName = '',
    this.mfaEnabled = false,
    this.shop = true,
    this.pos = true,
    this.merchantSlug = '',
    this.merchantName = '',
  });

  final int id;
  final String email;
  final String username;
  final bool emailVerified;
  final bool isStaffOps;
  final String displayName;
  final bool mfaEnabled;
  final bool shop;
  final bool pos;
  final String merchantSlug;
  final String merchantName;

  bool get runsTill => isStaffOps || (merchantSlug.isNotEmpty && pos);
  bool get runsShop => shop;

  String get name => displayName.isNotEmpty ? displayName : username;

  factory UserMe.fromJson(Map<String, dynamic> json, {String? displayName}) =>
      UserMe(
        id: asInt(json['id']),
        email: asString(json['email']),
        username: asString(json['username']),
        emailVerified: json['email_verified'] as bool? ?? false,
        isStaffOps:
            json['is_staff_ops'] as bool? ?? json['is_staff'] as bool? ?? false,
        displayName: displayName ?? asString(json['display_name']),
        mfaEnabled: json['mfa_enabled'] as bool? ?? false,
        shop: json['shop'] as bool? ?? true,
        pos: json['pos'] as bool? ?? true,
        merchantSlug: asString(json['merchant_slug']),
        merchantName: asString(json['merchant_name']),
      );
}

class AuthSession {
  const AuthSession({
    this.user,
    this.preAuthToken,
    this.pendingEmail,
    this.mfaEnabled = false,
    this.backupCodes = const [],
  });

  final UserMe? user;
  final String? preAuthToken;
  final String? pendingEmail;
  final bool mfaEnabled;
  final List<String> backupCodes;

  bool get isSignedIn => user != null;
  bool get mfaPending => preAuthToken != null && user == null;

  AuthSession copyWith({
    UserMe? user,
    String? preAuthToken,
    String? pendingEmail,
    bool? mfaEnabled,
    List<String>? backupCodes,
    bool clearChallenge = false,
    bool clearUser = false,
  }) {
    return AuthSession(
      user: clearUser ? null : (user ?? this.user),
      preAuthToken: clearChallenge ? null : (preAuthToken ?? this.preAuthToken),
      pendingEmail: clearChallenge ? null : (pendingEmail ?? this.pendingEmail),
      mfaEnabled: mfaEnabled ?? this.mfaEnabled,
      backupCodes: backupCodes ?? this.backupCodes,
    );
  }
}

class OrderLine {
  const OrderLine({
    required this.name,
    required this.sku,
    required this.quantity,
    required this.unitPrice,
    required this.lineTotal,
  });

  final String name;
  final String sku;
  final int quantity;
  final String unitPrice;
  final String lineTotal;

  factory OrderLine.fromJson(Map<String, dynamic> json) => OrderLine(
        name: asString(json['product_name_snapshot']),
        sku: asString(json['sku_snapshot']),
        quantity: asInt(json['quantity']),
        unitPrice: asString(json['unit_price'], '0.00'),
        lineTotal: asString(json['line_total'], '0.00'),
      );
}

class CoolingOff {
  const CoolingOff({required this.eligible, required this.daysRemaining});
  final bool eligible;
  final int daysRemaining;
}

class OrderEvent {
  const OrderEvent({
    required this.toStatus,
    required this.note,
    required this.createdAt,
  });

  final String toStatus;
  final String note;
  final String createdAt;

  factory OrderEvent.fromJson(Map<String, dynamic> json) => OrderEvent(
        toStatus: asString(json['to_status']),
        note: asString(json['note']),
        createdAt: asString(json['created_at']),
      );
}

class ShipmentUpdate {
  const ShipmentUpdate({
    required this.status,
    required this.note,
    required this.createdAt,
  });

  final String status;
  final String note;
  final String createdAt;

  factory ShipmentUpdate.fromJson(Map<String, dynamic> json) => ShipmentUpdate(
        status: asString(json['status']),
        note: asString(json['note']),
        createdAt: asString(json['created_at']),
      );
}

class ShipmentInfo {
  const ShipmentInfo({
    required this.carrier,
    required this.trackingNumber,
    required this.status,
    this.events = const [],
  });

  final String carrier;
  final String trackingNumber;
  final String status;
  final List<ShipmentUpdate> events;

  bool get isBooked => trackingNumber.isNotEmpty;

  factory ShipmentInfo.fromJson(Map<String, dynamic> json) => ShipmentInfo(
        carrier: asString(json['carrier']),
        trackingNumber: asString(json['tracking_number']),
        status: asString(json['status']),
        events: (json['events'] as List? ?? [])
            .whereType<Map>()
            .map((row) => ShipmentUpdate.fromJson(Map<String, dynamic>.from(row)))
            .toList(),
      );
}

class OrderSummary {
  OrderSummary({
    required this.reference,
    required this.status,
    required this.grandTotal,
    required this.itemCount,
    required this.trackingStage,
    this.placedAt,
    this.shippingMethod = '',
    this.paymentMethod = '',
    this.shipTo = '',
    this.subtotal = '0.00',
    this.discountTotal = '0.00',
    this.shippingTotal = '0.00',
    this.coolingOff = const CoolingOff(eligible: false, daysRemaining: 0),
    this.lines = const [],
    this.events = const [],
    this.shipment,
  });

  final String reference;
  final String status;
  final String grandTotal;
  final int itemCount;
  final int trackingStage;
  final String? placedAt;
  final String shippingMethod;
  final String paymentMethod;
  final String shipTo;
  final String subtotal;
  final String discountTotal;
  final String shippingTotal;
  final CoolingOff coolingOff;
  final List<OrderLine> lines;
  final List<OrderEvent> events;
  final ShipmentInfo? shipment;

  bool get awaitingPayment => status == 'awaiting_payment';
  bool get isClosed => status == 'cancelled' || status == 'refunded';
  bool get canCancel =>
      status == 'awaiting_payment' ||
      status == 'payment_confirmed' ||
      status == 'packed';

  factory OrderSummary.fromJson(Map<String, dynamic> json) {
    final cooling = json['cooling_off'];
    return OrderSummary(
      reference: asString(json['reference']),
      status: asString(json['status']),
      grandTotal: asString(json['grand_total'], '0.00'),
      itemCount: asInt(json['item_count']),
      trackingStage: asInt(json['tracking_stage']),
      placedAt: json['placed_at'] as String?,
      shippingMethod: asString(json['shipping_method']),
      paymentMethod: asString(json['payment_method']),
      shipTo: asString(json['shipping_address_text']),
      subtotal: asString(json['subtotal'], '0.00'),
      discountTotal: asString(json['discount_total'], '0.00'),
      shippingTotal: asString(json['shipping_total'], '0.00'),
      coolingOff: cooling is Map
          ? CoolingOff(
              eligible: cooling['eligible'] as bool? ?? false,
              daysRemaining: asInt(cooling['days_remaining']),
            )
          : const CoolingOff(eligible: false, daysRemaining: 0),
      lines: (json['items'] as List? ?? [])
          .whereType<Map>()
          .map((row) => OrderLine.fromJson(Map<String, dynamic>.from(row)))
          .toList(),
      events: (json['events'] as List? ?? [])
          .whereType<Map>()
          .map((row) => OrderEvent.fromJson(Map<String, dynamic>.from(row)))
          .toList(),
      shipment: json['shipment'] is Map
          ? ShipmentInfo.fromJson(Map<String, dynamic>.from(json['shipment'] as Map))
          : null,
    );
  }
}

class AddressBookEntry {
  const AddressBookEntry({
    required this.id,
    required this.label,
    required this.line1,
    required this.city,
    required this.postalCode,
    required this.recipientName,
    required this.singleLine,
    this.line2 = '',
    this.suburb = '',
    this.province = '',
    this.phone = '',
    this.isDefaultShipping = false,
  });

  final int id;
  final String label;
  final String line1;
  final String line2;
  final String suburb;
  final String city;
  final String province;
  final String postalCode;
  final String recipientName;
  final String phone;
  final String singleLine;
  final bool isDefaultShipping;

  Map<String, dynamic> toJson() => {
        'label': label.isEmpty ? 'Home' : label,
        'line1': line1,
        'line2': line2,
        'suburb': suburb,
        'city': city,
        'province': province,
        'postal_code': postalCode,
        'recipient_name': recipientName,
        'recipient_phone': phone,
        'is_default_shipping': isDefaultShipping,
      };

  factory AddressBookEntry.fromJson(Map<String, dynamic> json) {
    final parts = [
      json['line1'],
      json['line2'],
      json['suburb'],
      json['city'],
      json['postal_code'],
    ].map((part) => asString(part)).where((part) => part.isNotEmpty);
    return AddressBookEntry(
      id: asInt(json['id']),
      label: asString(json['label'], 'Home'),
      line1: asString(json['line1']),
      line2: asString(json['line2']),
      suburb: asString(json['suburb']),
      city: asString(json['city']),
      province: asString(json['province']),
      postalCode: asString(json['postal_code']),
      recipientName: asString(json['recipient_name']),
      phone: asString(json['recipient_phone']),
      singleLine: parts.join(', '),
      isDefaultShipping: json['is_default_shipping'] as bool? ?? false,
    );
  }
}

class UserProfile {
  const UserProfile({
    required this.id,
    required this.displayName,
    required this.firstName,
    required this.lastName,
    required this.address,
    this.phoneNumber = '',
    this.dateOfBirth = '',
  });

  final int id;
  final String displayName;
  final String firstName;
  final String lastName;
  final String address;
  final String phoneNumber;
  final String dateOfBirth;

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
        id: asInt(json['id']),
        displayName: asString(json['display_name']),
        firstName: asString(json['first_name']),
        lastName: asString(json['last_name']),
        address: asString(json['address']),
        phoneNumber: asString(json['phone_number']),
        dateOfBirth: asString(json['date_of_birth']),
      );
}

class PromotionOffer {
  const PromotionOffer({
    required this.code,
    required this.title,
    required this.description,
    required this.discountType,
    required this.amount,
  });

  final String code;
  final String title;
  final String description;
  final String discountType;
  final String amount;

  String get label => discountType == 'percentage' ? '$amount% off' : 'R$amount off';

  factory PromotionOffer.fromJson(Map<String, dynamic> json) => PromotionOffer(
        code: asString(json['code']),
        title: asString(json['title']),
        description: asString(json['description']),
        discountType: asString(json['discount_type']),
        amount: asString(json['amount'], '0.00'),
      );
}

class ShopAd {
  const ShopAd({
    required this.id,
    required this.title,
    required this.body,
    this.productId,
    this.productSlug = '',
    this.isActive = true,
  });

  final int id;
  final String title;
  final String body;
  final int? productId;
  final String productSlug;
  final bool isActive;

  factory ShopAd.fromJson(Map<String, dynamic> json) => ShopAd(
        id: asInt(json['id']),
        title: asString(json['title']),
        body: asString(json['body']),
        productId: json['product_id'] == null ? null : asInt(json['product_id']),
        productSlug: asString(json['product_slug']),
        isActive: json['is_active'] as bool? ?? true,
      );
}

class ShopBundle {
  const ShopBundle({
    required this.id,
    required this.title,
    required this.price,
    required this.compareAt,
    required this.isActive,
    this.items = const [],
  });

  final int id;
  final String title;
  final String price;
  final String compareAt;
  final bool isActive;
  final List<String> items;

  factory ShopBundle.fromJson(Map<String, dynamic> json) => ShopBundle(
        id: asInt(json['id']),
        title: asString(json['title']),
        price: asString(json['price'], '0.00'),
        compareAt: asString(json['compare_at']),
        isActive: json['is_active'] as bool? ?? true,
        items: [
          for (final row in (json['items'] as List? ?? []))
            if (row is Map) asString(row['name']),
        ],
      );
}

class LoyaltyStatus {
  const LoyaltyStatus({
    required this.points,
    required this.referralCode,
    this.referrerCode = '',
  });

  final int points;
  final String referralCode;
  final String referrerCode;

  factory LoyaltyStatus.fromJson(Map<String, dynamic> json) => LoyaltyStatus(
        points: asInt(json['points']),
        referralCode: asString(json['referral_code']),
        referrerCode: asString(json['referrer_code']),
      );
}

class StaffFlash {
  const StaffFlash({
    required this.id,
    required this.productName,
    required this.salePrice,
    required this.compareAt,
    required this.isActive,
    this.startsAt = '',
    this.endsAt = '',
  });

  final int id;
  final String productName;
  final String salePrice;
  final String compareAt;
  final bool isActive;
  final String startsAt;
  final String endsAt;

  factory StaffFlash.fromJson(Map<String, dynamic> json) => StaffFlash(
        id: asInt(json['id']),
        productName: asString(json['product_name']),
        salePrice: asString(json['sale_price'], '0.00'),
        compareAt: asString(json['compare_at']),
        isActive: json['is_active'] as bool? ?? true,
        startsAt: asString(json['starts_at']),
        endsAt: asString(json['ends_at']),
      );
}

class StaffBundle {
  const StaffBundle({
    required this.id,
    required this.title,
    required this.price,
    required this.isActive,
  });

  final int id;
  final String title;
  final String price;
  final bool isActive;

  factory StaffBundle.fromJson(Map<String, dynamic> json) => StaffBundle(
        id: asInt(json['id']),
        title: asString(json['title']),
        price: asString(json['price'], '0.00'),
        isActive: json['is_active'] as bool? ?? true,
      );
}

class ShippingRate {
  const ShippingRate({
    required this.id,
    required this.methodName,
    required this.price,
    required this.estimatedDays,
  });

  final int id;
  final String methodName;
  final String price;
  final String estimatedDays;

  factory ShippingRate.fromJson(Map<String, dynamic> json) => ShippingRate(
        id: asInt(json['id']),
        methodName: asString(json['method_name']),
        price: asString(json['price'], '0.00'),
        estimatedDays: asString(json['estimated_days']),
      );
}

class StaffPromotion {
  const StaffPromotion({
    required this.code,
    required this.title,
    required this.description,
    required this.discountType,
    required this.amount,
    required this.isActive,
    this.startsAt = '',
    this.endsAt = '',
  });

  final String code;
  final String title;
  final String description;
  final String discountType;
  final String amount;
  final bool isActive;
  final String startsAt;
  final String endsAt;

  factory StaffPromotion.fromJson(Map<String, dynamic> json) => StaffPromotion(
        code: asString(json['code']),
        title: asString(json['title']),
        description: asString(json['description']),
        discountType: asString(json['discount_type']),
        amount: asString(json['amount'], '0.00'),
        isActive: json['is_active'] as bool? ?? true,
        startsAt: asString(json['starts_at']),
        endsAt: asString(json['ends_at']),
      );
}

class InboxNote {
  const InboxNote({
    required this.id,
    required this.title,
    required this.body,
    required this.kind,
    required this.read,
    required this.createdAt,
  });

  final int id;
  final String title;
  final String body;
  final String kind;
  final bool read;
  final String createdAt;

  factory InboxNote.fromJson(Map<String, dynamic> json) => InboxNote(
        id: asInt(json['id']),
        title: asString(json['title']),
        body: asString(json['body']),
        kind: asString(json['kind']),
        read: json['read'] as bool? ?? false,
        createdAt: asString(json['created_at']),
      );
}

class NotificationPrefs {
  const NotificationPrefs({
    required this.emailTransactional,
    required this.emailMarketing,
    required this.pushOrderUpdates,
    required this.pushMarketing,
  });

  final bool emailTransactional;
  final bool emailMarketing;
  final bool pushOrderUpdates;
  final bool pushMarketing;

  factory NotificationPrefs.fromJson(Map<String, dynamic> json) =>
      NotificationPrefs(
        emailTransactional: json['email_transactional'] as bool? ?? true,
        emailMarketing: json['email_marketing'] as bool? ?? false,
        pushOrderUpdates: json['push_order_updates'] as bool? ?? true,
        pushMarketing: json['push_marketing'] as bool? ?? false,
      );
}

class PushDevice {
  const PushDevice({required this.id, required this.platform, required this.token});
  final int id;
  final String platform;
  final String token;

  factory PushDevice.fromJson(Map<String, dynamic> json) => PushDevice(
        id: asInt(json['id']),
        platform: asString(json['platform']),
        token: asString(json['token']),
      );
}

class RefundRow {
  const RefundRow({
    required this.amount,
    required this.orderReference,
    required this.reason,
    required this.createdAt,
  });

  final String amount;
  final String orderReference;
  final String reason;
  final String createdAt;

  factory RefundRow.fromJson(Map<String, dynamic> json) => RefundRow(
        amount: asString(json['amount'], '0.00'),
        orderReference: asString(json['order_reference']),
        reason: asString(json['reason']),
        createdAt: asString(json['created_at']),
      );
}

class TaxInvoice {
  const TaxInvoice({
    required this.invoiceNumber,
    required this.issuedAt,
    required this.merchantName,
    required this.vatNumber,
    required this.merchantAddress,
    required this.customerEmail,
    required this.shipTo,
    required this.lines,
    required this.currency,
    required this.subtotal,
    required this.discount,
    required this.shipping,
    required this.netAmount,
    required this.vatAmount,
    required this.vatRate,
    required this.grandTotal,
  });

  final String invoiceNumber;
  final String issuedAt;
  final String merchantName;
  final String vatNumber;
  final String merchantAddress;
  final String customerEmail;
  final String shipTo;
  final List<Map<String, dynamic>> lines;
  final String currency;
  final String subtotal;
  final String discount;
  final String shipping;
  final String netAmount;
  final String vatAmount;
  final String vatRate;
  final String grandTotal;

  factory TaxInvoice.fromJson(Map<String, dynamic> json) {
    final merchant = json['merchant'] is Map
        ? Map<String, dynamic>.from(json['merchant'] as Map)
        : const <String, dynamic>{};
    return TaxInvoice(
      invoiceNumber: asString(json['invoice_number']),
      issuedAt: asString(json['issued_at']),
      merchantName: asString(merchant['name']),
      vatNumber: asString(merchant['vat_number']),
      merchantAddress: asString(merchant['address']),
      customerEmail: asString(json['customer_email']),
      shipTo: asString(json['ship_to']),
      lines: (json['lines'] as List? ?? [])
          .whereType<Map>()
          .map((row) => Map<String, dynamic>.from(row))
          .toList(),
      currency: asString(json['currency'], 'ZAR'),
      subtotal: asString(json['subtotal'], '0.00'),
      discount: asString(json['discount'], '0.00'),
      shipping: asString(json['shipping'], '0.00'),
      netAmount: asString(json['net_amount'], '0.00'),
      vatAmount: asString(json['vat_amount'], '0.00'),
      vatRate: asString(json['vat_rate_pct'], '15'),
      grandTotal: asString(json['grand_total'], '0.00'),
    );
  }
}

class AppVersionInfo {
  const AppVersionInfo({
    required this.minSupported,
    required this.latest,
    required this.forceUpdate,
    this.message,
  });

  final String minSupported;
  final String latest;
  final bool forceUpdate;
  final String? message;

  factory AppVersionInfo.fromJson(Map<String, dynamic> json) => AppVersionInfo(
        minSupported: asString(json['min_supported'], '1.0.0'),
        latest: asString(json['latest'], '1.0.0'),
        forceUpdate: json['force_update'] as bool? ?? false,
        message: json['message'] == null ? null : asString(json['message']),
      );
}

class ReconReport {
  const ReconReport({
    required this.date,
    required this.paymentsSucceeded,
    required this.paymentsPending,
    required this.grossCaptured,
    required this.grossRefunded,
    required this.net,
    required this.exceptionCount,
  });

  final String date;
  final int paymentsSucceeded;
  final int paymentsPending;
  final String grossCaptured;
  final String grossRefunded;
  final String net;
  final int exceptionCount;

  factory ReconReport.fromJson(Map<String, dynamic> json) => ReconReport(
        date: asString(json['date']),
        paymentsSucceeded: asInt(json['payments_succeeded']),
        paymentsPending: asInt(json['payments_pending']),
        grossCaptured: asString(json['gross_captured'], '0.00'),
        grossRefunded: asString(json['gross_refunded'], '0.00'),
        net: asString(json['net'], '0.00'),
        exceptionCount: asInt(json['exception_count']),
      );
}

const orderStages = [
  'Order placed',
  'Payment confirmed',
  'Packed',
  'Out for delivery',
  'Delivered',
];
