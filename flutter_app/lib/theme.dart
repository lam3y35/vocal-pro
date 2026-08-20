import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// VocalPro dark glassmorphism theme – deep purple/red palette
/// matching the reference designs from the user's GUI folder.

class AppColors {
  // ── Core palette ──────────────────────────────────────────────────
  static const background = Color(0xFF0D0B1A);      // near-black with purple tint
  static const surface = Color(0xFF1A1530);          // dark purple card
  static const surfaceLight = Color(0xFF251E3A);     // lighter surface
  static const glass = Color(0x33FFFFFF);            // white @ 20% for glassmorphism
  static const glassBorder = Color(0x22FFFFFF);      // subtle white border

  // ── Accent gradient stops ─────────────────────────────────────────
  static const accentPurple = Color(0xFF7C3AED);
  static const accentPink = Color(0xFFE94560);
  static const accentRed = Color(0xFFDC2626);

  // ── Semantic ──────────────────────────────────────────────────────
  static const success = Color(0xFF22C55E);
  static const warning = Color(0xFFF59E0B);
  static const error = Color(0xFFEF4444);
  static const info = Color(0xFF3B82F6);

  // ── Text ──────────────────────────────────────────────────────────
  static const textPrimary = Color(0xFFF1F5F9);
  static const textSecondary = Color(0xFF94A3B8);
  static const textDim = Color(0xFF64748B);

  // ── Gradients ─────────────────────────────────────────────────────
  static const accentGradient = LinearGradient(
    colors: [accentPurple, accentPink],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const backgroundGradient = LinearGradient(
    colors: [Color(0xFF0D0B1A), Color(0xFF1A0E2E), Color(0xFF0D0B1A)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static const cardGradient = LinearGradient(
    colors: [Color(0x1AFFFFFF), Color(0x0DFFFFFF)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  // ── Stem colors (matching the Python GUI) ────────────────────────
  static const stemColors = [
    Color(0xFF7C3AED), // vocals – purple
    Color(0xFF22C55E), // drums – green
    Color(0xFFF59E0B), // bass – amber
    Color(0xFFEF4444), // other – red
    Color(0xFF3B82F6), // guitar – blue
    Color(0xFFEC4899), // piano – pink
  ];
}

/// Reusable text styles using Google Fonts (Inter).
class AppTextStyles {
  static TextStyle heading(BuildContext context) => GoogleFonts.inter(
    fontSize: 22,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    letterSpacing: -0.5,
  );

  static TextStyle subheading(BuildContext context) => GoogleFonts.inter(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
    letterSpacing: -0.3,
  );

  static TextStyle body(BuildContext context) => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
    height: 1.5,
  );

  static TextStyle caption(BuildContext context) => GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w500,
    color: AppColors.textDim,
    letterSpacing: 0.5,
  );

  static TextStyle label(BuildContext context) => GoogleFonts.inter(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    color: AppColors.textDim,
    letterSpacing: 1.0,
  );

  static TextStyle mono(BuildContext context) => GoogleFonts.jetBrainsMono(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    color: AppColors.textDim,
    height: 1.6,
  );

  static TextStyle buttonText(BuildContext context) => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: Colors.white,
  );
}
