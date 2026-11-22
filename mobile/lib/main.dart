import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'src/screens/shell.dart';
import 'src/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: NorthboundApp()));
}

class NorthboundApp extends StatelessWidget {
  const NorthboundApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Northbound',
      debugShowCheckedModeBanner: false,
      theme: northboundTheme(),
      home: const AppShell(),
    );
  }
}
