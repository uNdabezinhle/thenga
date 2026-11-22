import 'package:flutter/material.dart';

/// Northbound brand tokens from the prototype / SPA.
class NbColors {
  static const forest = Color(0xFF0E2A22);
  static const forest2 = Color(0xFF16362B);
  static const lime = Color(0xFFC8F751);
  static const paper = Color(0xFFF3F4EF);
  static const paper2 = Color(0xFFE7E9E1);
  static const ink = Color(0xFF101512);
  static const mute = Color(0xFF6E7B72);
  static const hair = Color(0xFFD8DCD3);
}

ThemeData northboundTheme() {
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorScheme: ColorScheme.fromSeed(
      seedColor: NbColors.forest,
      primary: NbColors.forest,
      secondary: NbColors.lime,
      surface: NbColors.paper,
    ),
    scaffoldBackgroundColor: NbColors.paper,
    appBarTheme: const AppBarTheme(
      backgroundColor: NbColors.paper,
      foregroundColor: NbColors.ink,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: 'Roboto',
        fontWeight: FontWeight.w800,
        fontSize: 24,
        color: NbColors.ink,
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: NbColors.forest,
        foregroundColor: NbColors.lime,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: Colors.white,
      selectedColor: NbColors.forest,
      labelStyle: const TextStyle(fontSize: 12.5),
      side: const BorderSide(color: NbColors.hair),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
    ),
  );
  return base;
}

String moneyZar(String amount) {
  final n = double.tryParse(amount) ?? 0;
  return 'R ${n.toStringAsFixed(2)}';
}

String formatWhen(String? iso) {
  if (iso == null || iso.isEmpty) return '';
  final parsed = DateTime.tryParse(iso)?.toLocal();
  if (parsed == null) return '';
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  return '${parsed.day} ${months[parsed.month - 1]} ${parsed.year}';
}

void showAppMessage(BuildContext context, String message) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
}
