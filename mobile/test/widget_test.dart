import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:northbound/main.dart';
import 'package:northbound/src/models/models.dart';
import 'package:northbound/src/screens/account_screen.dart';
import 'package:northbound/src/screens/cart_screen.dart';
import 'package:northbound/src/screens/checkout_screen.dart';
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
  });
}
