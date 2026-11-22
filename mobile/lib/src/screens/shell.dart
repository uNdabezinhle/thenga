import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/providers.dart';
import '../theme.dart';
import 'account_screen.dart';
import 'cart_screen.dart';
import 'saved_screen.dart';
import 'search_screen.dart';
import 'shop_screen.dart';
import 'staff_screen.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _index = 0;
  bool _updateBlocked = false;

  @override
  Widget build(BuildContext context) {
    ref.listen(appVersionProvider, (previous, next) {
      final info = next.valueOrNull;
      if (info == null || !info.forceUpdate || _updateBlocked) return;
      _updateBlocked = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        showDialog<void>(
          context: context,
          barrierDismissible: false,
          builder: (context) => AlertDialog(
            title: const Text('Update required'),
            content: Text(
              info.message == null || info.message!.isEmpty
                  ? 'This version of Northbound is no longer supported.'
                  : info.message!,
            ),
          ),
        );
      });
    });
    ref.listen<int>(shellTabProvider, (previous, next) {
      if (next != _index) setState(() => _index = next);
    });
    ref.listen(authStateProvider, (previous, next) {
      final signedIn = next.valueOrNull?.isSignedIn ?? false;
      if (!signedIn && _index == NbTab.staff) {
        setState(() => _index = NbTab.account);
      }
    });

    final cartCount = ref.watch(cartProvider).valueOrNull?.totalItems ?? 0;
    final staff = ref.watch(authStateProvider).valueOrNull?.user?.isStaffOps ?? false;
    final pages = <Widget>[
      const ShopScreen(),
      const SearchScreen(),
      const CartScreen(),
      const SavedScreen(),
      const AccountScreen(),
      if (staff) const StaffScreen(),
    ];
    final index = _index.clamp(0, pages.length - 1);
    final version = ref.watch(appVersionProvider).valueOrNull;
    final offerUpdate = version != null &&
        !version.forceUpdate &&
        isNewerVersion(version.latest, kAppVersion);

    return Scaffold(
      body: Column(
        children: [
          if (offerUpdate)
            Material(
              color: NbColors.lime,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    const Icon(Icons.system_update_alt, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text('Version ${version.latest} is available.'),
                    ),
                  ],
                ),
              ),
            ),
          Expanded(child: IndexedStack(index: index, children: pages)),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) {
          if (value == NbTab.shop) {
            final query = ref.read(catalogueQueryProvider);
            if (query.q.isNotEmpty) {
              ref.read(catalogueQueryProvider.notifier).state = query.copyWith(q: '');
            }
          }
          setState(() => _index = value);
          ref.read(shellTabProvider.notifier).state = value;
        },
        backgroundColor: Colors.white,
        indicatorColor: NbColors.lime,
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.storefront_outlined),
            selectedIcon: Icon(Icons.storefront),
            label: 'Shop',
          ),
          const NavigationDestination(
            icon: Icon(Icons.search),
            label: 'Search',
          ),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: cartCount > 0,
              label: Text('$cartCount'),
              child: const Icon(Icons.shopping_bag_outlined),
            ),
            selectedIcon: Badge(
              isLabelVisible: cartCount > 0,
              label: Text('$cartCount'),
              child: const Icon(Icons.shopping_bag),
            ),
            label: 'Cart',
          ),
          const NavigationDestination(
            icon: Icon(Icons.bookmark_border),
            selectedIcon: Icon(Icons.bookmark),
            label: 'Saved',
          ),
          const NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Account',
          ),
          if (staff)
            const NavigationDestination(
              icon: Icon(Icons.layers_outlined),
              selectedIcon: Icon(Icons.layers),
              label: 'Ops',
            ),
        ],
      ),
    );
  }
}
