import 'package:flutter/material.dart';

class AppTheme {
  const AppTheme._();

  static const orange = Color(0xFFF36A35);
  static const darkBg = Color(0xFF090909);
  static const darkSurface = Color(0xFF171717);
  static const darkSurfaceHigh = Color(0xFF211A17);
  static const lightBg = Color(0xFFFFFBF7);
  static const lightSurface = Color(0xFFFFFFFF);
  static const lightSurfaceHigh = Color(0xFFFFEFE7);

  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: orange,
      brightness: Brightness.dark,
      surface: darkSurface,
      primary: orange,
      secondary: orange,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: darkBg,
      fontFamily: 'Roboto',
      appBarTheme: const AppBarTheme(
        backgroundColor: darkBg,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: darkSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: const BorderSide(color: Color(0xFF2D2D2D)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: orange,
          foregroundColor: Colors.black,
          minimumSize: const Size.fromHeight(52),
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.white,
          side: const BorderSide(color: Color(0xFF33231B)),
          minimumSize: const Size.fromHeight(48),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: darkSurfaceHigh,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFF34251E)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFF34251E)),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: darkSurface,
        selectedItemColor: orange,
        unselectedItemColor: Color(0xFF9B9B9B),
        type: BottomNavigationBarType.fixed,
      ),
    );
  }

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(
      seedColor: orange,
      brightness: Brightness.light,
      surface: lightSurface,
      primary: orange,
      secondary: orange,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: scheme,
      scaffoldBackgroundColor: lightBg,
      fontFamily: 'Roboto',
      appBarTheme: const AppBarTheme(
        backgroundColor: lightBg,
        foregroundColor: Colors.black,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: lightSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: const BorderSide(color: Color(0xFFFFD2BF)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: orange,
          foregroundColor: Colors.black,
          minimumSize: const Size.fromHeight(52),
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.black,
          side: const BorderSide(color: Color(0xFFFFC2A8)),
          minimumSize: const Size.fromHeight(48),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: lightSurfaceHigh,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFFFFC2A8)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFFFFC2A8)),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: lightSurface,
        selectedItemColor: orange,
        unselectedItemColor: Color(0xFF777777),
        type: BottomNavigationBarType.fixed,
      ),
    );
  }
}
