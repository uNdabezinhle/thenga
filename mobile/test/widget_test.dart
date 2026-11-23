import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:northbound/main.dart';
import 'package:northbound/src/models/models.dart';
import 'package:northbound/src/screens/account_screen.dart';
import 'package:northbound/src/screens/cart_screen.dart';
import 'package:northbound/src/screens/checkout_screen.dart';
import 'package:northbound/src/screens/settings_screen.dart';
import 'package:northbound/src/screens/shop_screen.dart';
import 'package:northbound/src/screens/staff_screen.dart';

import 'package:northbound/src/state/providers.dart';

import 'support.dart';

void main() {
  testWidgets('App boots', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          productsProvider.overrideWith((ref) async => <Product>[]),
          allProductsProvider.overrideWith((ref) async => <Product>[]),
          promotionsProvider.overrideWith((ref) async => <PromotionOffer>[]),
          bundlesProvider.overrideWith((ref) async => <ShopBundle>[]),
          adsProvider.overrideWith((ref) async => <ShopAd>[]),
          categoriesProvider.overrideWith((ref) async => kCategories),
          brandsProvider.overrideWith((ref) async => <CatalogueChip>[]),
          appVersionProvider.overrideWith(
            (ref) async => const AppVersionInfo(
              minSupported: '1.0.0',
              latest: '1.0.0',
              forceUpdate: false,
            ),
          ),
          sessionDebugProvider.overrideWith(
            (ref) async => const SessionDebug(
              tokenPrefix: '—',
              mfaVerified: null,
              cartSession: '—',
              apiBase: 'http://127.0.0.1:8000',
            ),
          ),
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
          cartProvider.overrideWith(
            (ref) => CartNotifier(ref.watch(apiProvider), load: false),
          ),
        ],
        child: const NorthboundApp(),
      ),
    );
    await tester.pump();
    expect(find.text('Northbound'), findsOneWidget);
  });

  testWidgets('Shop shows an empty catalogue', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          productsProvider.overrideWith((ref) async => <Product>[]),
          promotionsProvider.overrideWith((ref) async => <PromotionOffer>[]),
          bundlesProvider.overrideWith((ref) async => <ShopBundle>[]),
          adsProvider.overrideWith((ref) async => <ShopAd>[]),
          categoriesProvider.overrideWith((ref) async => kCategories),
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
        ],
        child: const MaterialApp(home: ShopScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Nothing in the catalogue yet'), findsOneWidget);
  });

  testWidgets('Shop shows a catalogue error', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          productsProvider.overrideWith((ref) async => throw Exception('offline')),
          promotionsProvider.overrideWith((ref) async => <PromotionOffer>[]),
          bundlesProvider.overrideWith((ref) async => <ShopBundle>[]),
          adsProvider.overrideWith((ref) async => <ShopAd>[]),
          categoriesProvider.overrideWith((ref) async => kCategories),
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
        ],
        child: const MaterialApp(home: ShopScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Could not load catalogue'), findsOneWidget);
  });

  testWidgets('Cart shows totals and a discount field', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          cartProvider.overrideWith((ref) {
            final notifier = CartNotifier(ref.watch(apiProvider), load: false);
            notifier.state = AsyncData(sampleCart(withDiscount: false));
            return notifier;
          }),
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
        ],
        child: const MaterialApp(home: CartScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('discount-code')), findsOneWidget);
    expect(find.textContaining('R 80.00'), findsWidgets);
  });

  testWidgets('Checkout stays disabled until sign-in', (tester) async {
    tester.view.physicalSize = const Size(800, 2000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          cartProvider.overrideWith((ref) {
            final notifier = CartNotifier(ref.watch(apiProvider), load: false);
            notifier.state = AsyncData(sampleCart());
            return notifier;
          }),
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
        ],
        child: const MaterialApp(home: CheckoutScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Sign in to place this order'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('place-order')),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('Account asks for an MFA code', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authStateProvider.overrideWith((ref) {
            final notifier = AuthNotifier(ref.watch(apiProvider), bootstrap: false);
            notifier.state = const AsyncData(
              AuthSession(preAuthToken: 'pre', pendingEmail: 'jordan@northbound.test'),
            );
            return notifier;
          }),
        ],
        child: const MaterialApp(home: AccountScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Enter your code'), findsOneWidget);
    expect(find.byKey(const Key('mfa-code')), findsOneWidget);
  });

  testWidgets('Staff screen stays closed for guests', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
        ],
        child: const MaterialApp(home: StaffScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('staff-gate')), findsOneWidget);
    expect(find.text('Staff only'), findsOneWidget);
    expect(find.byKey(const Key('open-till')), findsNothing);
  });

  testWidgets('Shop shows the banner and promotion', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          productsProvider.overrideWith((ref) async => <Product>[]),
          promotionsProvider.overrideWith(
            (ref) async => const [
              PromotionOffer(
                code: 'DISCOUNT20',
                title: '20% off the trail shop',
                description: '',
                discountType: 'percentage',
                amount: '20.00',
              ),
            ],
          ),
          bundlesProvider.overrideWith((ref) async => <ShopBundle>[]),
          adsProvider.overrideWith(
            (ref) async => const [
              ShopAd(id: 1, title: 'Trail week', body: 'Walk further.', productId: 3),
            ],
          ),
          categoriesProvider.overrideWith((ref) async => kCategories),
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
        ],
        child: const MaterialApp(home: ShopScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Trail week'), findsOneWidget);
    expect(find.text('20% off the trail shop · code DISCOUNT20'), findsOneWidget);
  });

  testWidgets('Shop shows a compare-at price', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          productsProvider.overrideWith(
            (ref) async => [
              Product(
                id: 7,
                sku: 'NB-RDG45',
                name: 'Ridgeline 45 Pack',
                brand: 'Northbound',
                category: 'packs',
                price: '249.00',
                compareAt: '289.00',
                currency: 'ZAR',
                rating: 4.5,
                reviews: 3,
                hue: 140,
                soldOut: false,
              ),
            ],
          ),
          promotionsProvider.overrideWith((ref) async => <PromotionOffer>[]),
          bundlesProvider.overrideWith((ref) async => <ShopBundle>[]),
          adsProvider.overrideWith((ref) async => <ShopAd>[]),
          categoriesProvider.overrideWith((ref) async => kCategories),
          recentProvider.overrideWith((ref) {
            final notifier = RecentNotifier(load: false);
            notifier.state = [7];
            return notifier;
          }),
          authStateProvider.overrideWith(
            (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
          ),
        ],
        child: const MaterialApp(home: ShopScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('R 249.00'), findsWidgets);
    expect(find.byKey(const Key('compare-7')), findsWidgets);
    expect(find.text('Recently viewed'), findsOneWidget);
  });

  testWidgets('Settings shows the phone field', (tester) async {
    tester.view.physicalSize = const Size(800, 3200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authStateProvider.overrideWith((ref) {
            final notifier = AuthNotifier(ref.watch(apiProvider), bootstrap: false);
            notifier.state = AsyncData(
              AuthSession(
                user: UserMe(
                  id: 1,
                  email: 'jordan@northbound.test',
                  username: 'jordan',
                  emailVerified: true,
                  isStaffOps: false,
                ),
              ),
            );
            return notifier;
          }),
          profileProvider.overrideWith(
            (ref) async => const UserProfile(
              id: 1,
              displayName: 'Jordan',
              firstName: 'Jordan',
              lastName: 'Mabaso',
              address: '14 Harbour Lane',
              phoneNumber: '0825550101',
            ),
          ),
          notificationPrefsProvider.overrideWith(
            (ref) async => const NotificationPrefs(
              emailTransactional: true,
              emailMarketing: false,
              pushOrderUpdates: true,
              pushMarketing: false,
            ),
          ),
          addressesProvider.overrideWith((ref) async => <AddressBookEntry>[]),
          devicesProvider.overrideWith((ref) async => <PushDevice>[]),
          loyaltyProvider.overrideWith(
            (ref) async => const LoyaltyStatus(points: 120, referralCode: 'JORDAN'),
          ),
        ],
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('settings-phone')), findsOneWidget);
    expect(find.text('120 points'), findsOneWidget);
    expect(find.text('Marketing email'), findsOneWidget);
    expect(find.text('Store settings'), findsNothing);
  });

  testWidgets('Store settings is present for staff', (tester) async {
    tester.view.physicalSize = const Size(800, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authStateProvider.overrideWith((ref) {
            final notifier = AuthNotifier(ref.watch(apiProvider), bootstrap: false);
            notifier.state = AsyncData(
              AuthSession(
                user: UserMe(
                  id: 2,
                  email: 'staff@northbound.test',
                  username: 'staff',
                  emailVerified: true,
                  isStaffOps: true,
                ),
              ),
            );
            return notifier;
          }),
          reconProvider.overrideWith((ref) async => null),
          staffOrdersProvider.overrideWith((ref) async => <OrderSummary>[]),
          refundsProvider.overrideWith((ref) async => <RefundRow>[]),
          shippingRatesProvider.overrideWith(
            (ref) async => const [
              ShippingRate(
                id: 1,
                methodName: 'Express',
                price: '14.50',
                estimatedDays: '2 days',
              ),
            ],
          ),
          staffAdsProvider.overrideWith((ref) async => const <ShopAd>[]),
          staffFlashesProvider.overrideWith((ref) async => const <StaffFlash>[]),
          staffBundlesProvider.overrideWith((ref) async => const <StaffBundle>[]),
          staffPromotionsProvider.overrideWith(
            (ref) async => const [
              StaffPromotion(
                code: 'DISCOUNT20',
                title: '20% off',
                description: '',
                discountType: 'percentage',
                amount: '20.00',
                isActive: true,
              ),
            ],
          ),
        ],
        child: const MaterialApp(home: StaffScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('open-till')), findsOneWidget);
    expect(find.byKey(const Key('store-settings')), findsOneWidget);
    await tester.tap(find.byKey(const Key('store-settings')));
    await tester.pumpAndSettle();
    expect(find.text('Delivery'), findsOneWidget);
    expect(find.text('Shared promotion'), findsOneWidget);
  });
}
