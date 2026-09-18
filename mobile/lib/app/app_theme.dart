import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  const AppTheme._();

  // Brand Colors synced directly with web CSS variables (:root)
  static const orange = Color(0xFFFF5A36); // --color-orange: #ff5a36
  static const crimson = Color(0xFFE61E43); // --color-crimson: #e61e43

  // Dark Theme Tokens
  static const darkBg = Color(0xFF0A0A0C); // --bg-primary: #0a0a0c
  static const darkSurface = Color(0xFF121215); // --bg-secondary: #121215
  static const darkSurfaceHigh = Color(0xFF1A1A1E); // --bg-tertiary: #1a1a1e
  static const darkCard = Color(0xFF1A1A1E);
  static const darkCardBorder = Color(0x1FFFFFFF); // subtle glass border
  static const darkCardBorderHover = Color(0x33FF5A36); // --glass-border-hover

  // Light Theme Tokens
  static const lightBg = Color(0xFFFFFFFF); // --bg-primary: #fff
  static const lightSurface = Color(0xFFF3F1EC); // --bg-secondary: #f3f1ec
  static const lightSurfaceHigh = Color(0xFFEBE8E2);
  static const lightCard = Color(0xFFFFFFFF);
  static const lightCardBorder = Color(0x14121215);

  // Status Colors
  static const statusScanned = Color(0xFF36D399); // --status-scanned: #36d399
  static const statusProcessing = Color(0xFFFBBD23); // --status-designing: #fbbd23
  static const statusCompleted = Color(0xFF38BDF8); // --status-completed: #38bdf8

  // Text Colors
  static const darkTextPrimary = Color(0xFFFFFFFF);
  static const darkTextSecondary = Color(0xFF9A9AA2);
  static const darkTextMuted = Color(0xFF62626A);

  static const lightTextPrimary = Color(0xFF121215);
  static const lightTextSecondary = Color(0xFF62626A);
  static const lightTextMuted = Color(0xFF8A8A93);

  // Reusable text styles with Google Fonts
  static TextStyle headingFont({
    double? fontSize,
    FontWeight? fontWeight,
    Color? color,
    double? height,
    double? letterSpacing,
  }) {
    return GoogleFonts.spaceGrotesk(
      fontSize: fontSize,
      fontWeight: fontWeight ?? FontWeight.w700,
      color: color,
      height: height,
      letterSpacing: letterSpacing,
    );
  }

  static TextStyle bodyFont({
    double? fontSize,
    FontWeight? fontWeight,
    Color? color,
    double? height,
    double? letterSpacing,
  }) {
    return GoogleFonts.outfit(
      fontSize: fontSize,
      fontWeight: fontWeight ?? FontWeight.w400,
      color: color,
      height: height,
      letterSpacing: letterSpacing,
    );
  }

  static TextStyle monoFont({
    double? fontSize,
    FontWeight? fontWeight,
    Color? color,
    double? letterSpacing,
  }) {
    return GoogleFonts.spaceMono(
      fontSize: fontSize,
      fontWeight: fontWeight ?? FontWeight.w700,
      color: color,
      letterSpacing: letterSpacing,
    );
  }

  static ThemeData dark() {
    final scheme = ColorScheme.fromSeed(
      seedColor: orange,
      brightness: Brightness.dark,
      surface: darkSurface,
      primary: orange,
      secondary: crimson,
      onPrimary: Colors.black,
      onSurface: darkTextPrimary,
      surfaceContainerHighest: darkCard,
      outline: darkCardBorder,
    );

    final baseTextTheme = GoogleFonts.outfitTextTheme(ThemeData.dark().textTheme);
    final textTheme = baseTextTheme.copyWith(
      displayLarge: GoogleFonts.spaceGrotesk(
        fontSize: 38,
        fontWeight: FontWeight.w900,
        letterSpacing: -1.0,
        color: darkTextPrimary,
        height: 1.05,
      ),
      displayMedium: GoogleFonts.spaceGrotesk(
        fontSize: 32,
        fontWeight: FontWeight.w900,
        letterSpacing: -0.8,
        color: darkTextPrimary,
        height: 1.1,
      ),
      displaySmall: GoogleFonts.spaceGrotesk(
        fontSize: 26,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.5,
        color: darkTextPrimary,
        height: 1.15,
      ),
      headlineLarge: GoogleFonts.spaceGrotesk(
        fontSize: 24,
        fontWeight: FontWeight.w800,
        color: darkTextPrimary,
      ),
      headlineMedium: GoogleFonts.spaceGrotesk(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: darkTextPrimary,
      ),
      headlineSmall: GoogleFonts.spaceGrotesk(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: darkTextPrimary,
      ),
      titleLarge: GoogleFonts.spaceGrotesk(
        fontSize: 16,
        fontWeight: FontWeight.w700,
        color: darkTextPrimary,
      ),
      titleMedium: GoogleFonts.outfit(
        fontSize: 15,
        fontWeight: FontWeight.w600,
        color: darkTextPrimary,
      ),
      bodyLarge: GoogleFonts.outfit(
        fontSize: 15,
        fontWeight: FontWeight.w400,
        color: darkTextPrimary,
      ),
      bodyMedium: GoogleFonts.outfit(
        fontSize: 13.5,
        fontWeight: FontWeight.w400,
        color: darkTextSecondary,
      ),
      labelLarge: GoogleFonts.spaceMono(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        letterSpacing: 1.2,
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: darkBg,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: darkBg,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleTextStyle: GoogleFonts.spaceGrotesk(
          fontSize: 19,
          fontWeight: FontWeight.w800,
          color: darkTextPrimary,
        ),
      ),
      cardTheme: CardThemeData(
        color: darkCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(22),
          side: const BorderSide(color: darkCardBorder, width: 1.2),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: orange,
          foregroundColor: Colors.black,
          minimumSize: const Size.fromHeight(52),
          textStyle: GoogleFonts.spaceGrotesk(
            fontWeight: FontWeight.w800,
            fontSize: 15,
            letterSpacing: 0.2,
          ),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.white,
          side: const BorderSide(color: Color(0x33FF5A36), width: 1.4),
          minimumSize: const Size.fromHeight(50),
          textStyle: GoogleFonts.spaceGrotesk(
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: darkSurface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: darkCardBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: darkCardBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: orange, width: 1.6),
        ),
        labelStyle: GoogleFonts.outfit(color: darkTextSecondary),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: darkSurface,
        selectedItemColor: orange,
        unselectedItemColor: darkTextMuted,
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
      secondary: crimson,
      onPrimary: Colors.black,
      onSurface: lightTextPrimary,
      surfaceContainerHighest: lightCard,
      outline: lightCardBorder,
    );

    final baseTextTheme = GoogleFonts.outfitTextTheme(ThemeData.light().textTheme);
    final textTheme = baseTextTheme.copyWith(
      displayLarge: GoogleFonts.spaceGrotesk(
        fontSize: 38,
        fontWeight: FontWeight.w900,
        color: lightTextPrimary,
      ),
      displayMedium: GoogleFonts.spaceGrotesk(
        fontSize: 32,
        fontWeight: FontWeight.w900,
        color: lightTextPrimary,
      ),
      displaySmall: GoogleFonts.spaceGrotesk(
        fontSize: 26,
        fontWeight: FontWeight.w800,
        color: lightTextPrimary,
      ),
      headlineLarge: GoogleFonts.spaceGrotesk(
        fontSize: 24,
        fontWeight: FontWeight.w800,
        color: lightTextPrimary,
      ),
      headlineMedium: GoogleFonts.spaceGrotesk(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: lightTextPrimary,
      ),
      headlineSmall: GoogleFonts.spaceGrotesk(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: lightTextPrimary,
      ),
      titleLarge: GoogleFonts.spaceGrotesk(
        fontSize: 16,
        fontWeight: FontWeight.w700,
        color: lightTextPrimary,
      ),
      titleMedium: GoogleFonts.outfit(
        fontSize: 15,
        fontWeight: FontWeight.w600,
        color: lightTextPrimary,
      ),
      bodyLarge: GoogleFonts.outfit(
        fontSize: 15,
        fontWeight: FontWeight.w400,
        color: lightTextPrimary,
      ),
      bodyMedium: GoogleFonts.outfit(
        fontSize: 13.5,
        fontWeight: FontWeight.w400,
        color: lightTextSecondary,
      ),
      labelLarge: GoogleFonts.spaceMono(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        letterSpacing: 1.2,
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: scheme,
      scaffoldBackgroundColor: lightBg,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: lightBg,
        foregroundColor: lightTextPrimary,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleTextStyle: GoogleFonts.spaceGrotesk(
          fontSize: 19,
          fontWeight: FontWeight.w800,
          color: lightTextPrimary,
        ),
      ),
      cardTheme: CardThemeData(
        color: lightCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(22),
          side: const BorderSide(color: lightCardBorder, width: 1.2),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: orange,
          foregroundColor: Colors.black,
          minimumSize: const Size.fromHeight(52),
          textStyle: GoogleFonts.spaceGrotesk(
            fontWeight: FontWeight.w800,
            fontSize: 15,
          ),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.black,
          side: const BorderSide(color: Color(0x33FF5A36), width: 1.4),
          minimumSize: const Size.fromHeight(50),
          textStyle: GoogleFonts.spaceGrotesk(
            fontWeight: FontWeight.w700,
            fontSize: 14,
          ),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: lightSurface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: lightCardBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: lightCardBorder),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: lightSurface,
        selectedItemColor: orange,
        unselectedItemColor: lightTextMuted,
        type: BottomNavigationBarType.fixed,
      ),
    );
  }
}
