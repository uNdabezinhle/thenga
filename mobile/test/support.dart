import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:northbound/src/api/client.dart';
import 'package:northbound/src/models/models.dart';
import 'package:northbound/src/state/providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class ScriptedAdapter implements HttpClientAdapter {
  ScriptedAdapter(this.onFetch);

  final Future<ResponseBody> Function(RequestOptions options) onFetch;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) {
    return onFetch(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody jsonBody(Object data, [int status = 200]) {
  return ResponseBody.fromString(
    jsonEncode(data),
    status,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );
}

Map<String, dynamic> sampleCartJson({
  int shippingId = 9,
  bool selected = true,
  bool withDiscount = true,
}) {
  return {
    'id': 1,
    'items': [
      {
        'id': 3,
        'product_id': 1,
        'product_name': 'Ridge Pack',
        'variant_label': 'M',
        'quantity': 1,
        'unit_price': '100.00',
        'line_total': '100.00',
        'hue': 150,
      },
    ],
    'discounts': withDiscount
        ? [
            {
              'id': 1,
              'code': 'DISCOUNT20',
              'discount_type': 'percentage',
              'amount': '20.00',
            },
          ]
        : [],
    'shipping_estimates': [
      {
        'id': shippingId,
        'method_name': 'Collect',
        'price': '0.00',
        'estimated_days': '1 day',
        'is_selected': selected,
      },
    ],
    'totals': {
      'subtotal': '100.00',
      'discount_total': '20.00',
      'shipping_total': '0.00',
      'grand_total': '80.00',
    },
    'total_items': 1,
  };
}

CartSnapshot sampleCart({bool withDiscount = true}) =>
    CartSnapshot.fromJson(sampleCartJson(withDiscount: withDiscount));

RekaApi scriptedApi(
  Future<ResponseBody> Function(RequestOptions options) onFetch,
) {
  final dio = Dio(BaseOptions(baseUrl: 'http://api.test'));
  dio.httpClientAdapter = ScriptedAdapter(onFetch);
  return RekaApi(
    baseUrl: 'http://api.test',
    dio: dio,
    store: MemoryTokenStore(),
  );
}

ProviderContainer testContainer(RekaApi api) {
  final container = ProviderContainer(
    overrides: [
      apiProvider.overrideWithValue(api),
      authStateProvider.overrideWith(
        (ref) => AuthNotifier(ref.watch(apiProvider), bootstrap: false),
      ),
      cartProvider.overrideWith(
        (ref) => CartNotifier(ref.watch(apiProvider), load: false),
      ),
    ],
  );
  addTearDown(container.dispose);
  return container;
}
