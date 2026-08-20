// Test helpers for Flutter widget tests.

import 'package:flutter/material.dart';
import 'package:vocal_pro_flutter/theme.dart';

/// MaterialApp wrapper for testing widgets in isolation.
/// Provides the VocalPro dark theme and required dependencies.
class TestApp extends StatelessWidget {
  final Widget child;

  const TestApp({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.background,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.accentPurple,
          secondary: AppColors.accentPink,
          surface: AppColors.surface,
          error: AppColors.error,
        ),
        cardTheme: const CardThemeData(
          color: AppColors.surface,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(16)),
          ),
        ),
        useMaterial3: true,
      ),
      home: child,
    );
  }
}
