import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:northbound/src/state/providers.dart';

import 'support.dart';

void main() {
  test('login stops at MFA and does not submit a code', () async {
    final paths = <String>[];
    final api = scriptedApi((options) async {
      paths.add('${options.method} ${options.path}');
      return jsonBody({
        'mfa_required': true,
        'pre_auth_token': 'pre-1',
      });
    });
    final container = testContainer(api);

    await container
        .read(authStateProvider.notifier)
        .login('jordan@northbound.test', 'correct-horse-42');

    final session = container.read(authStateProvider).valueOrNull;
    expect(session?.mfaPending, isTrue);
    expect(session?.preAuthToken, 'pre-1');
    expect(paths, ['POST /api/v1/auth/token/']);
    expect(paths.any((path) => path.contains('mfa/verify')), isFalse);
  });

  test('applyDiscount stores the returned cart', () async {
    final api = scriptedApi((options) async {
      expect(options.path, contains('apply_discount'));
      expect(options.data['code'], 'DISCOUNT20');
      return jsonBody(sampleCartJson());
    });
    final container = testContainer(api);

    await container.read(cartProvider.notifier).applyDiscount('discount20');

    final cart = container.read(cartProvider).valueOrNull;
    expect(cart?.discount?.code, 'DISCOUNT20');
    expect(cart?.grandTotal, '80.00');
  });

  test('selectShipping posts the estimate id', () async {
    int? sentId;
    final api = scriptedApi((options) async {
      sentId = options.data['shipping_method_id'] as int?;
      return jsonBody(sampleCartJson(shippingId: 9));
    });
    final container = testContainer(api);

    await container.read(cartProvider.notifier).selectShipping(9);

    expect(sentId, 9);
    expect(
      container.read(cartProvider).valueOrNull?.shippingEstimates.single.isSelected,
      isTrue,
    );
  });
}
