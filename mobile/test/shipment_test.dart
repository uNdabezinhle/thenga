import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:northbound/src/models/models.dart';
import 'package:northbound/src/screens/orders_screen.dart';

void main() {
  testWidgets('Shipment block shows the tracking number', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ShipmentTracking(
            shipment: ShipmentInfo(
              carrier: 'Northbound Courier',
              trackingNumber: 'SBX1234ABCD',
              status: 'dispatched',
            ),
          ),
        ),
      ),
    );
    expect(find.text('SBX1234ABCD'), findsOneWidget);
    expect(find.text('Northbound Courier'), findsOneWidget);
  });
}
