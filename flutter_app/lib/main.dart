import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:google_fonts/google_fonts.dart';
import 'theme.dart';
import 'screens/home_screen.dart';
import 'screens/splash_screen.dart';
import 'l10n/app_localizations.dart';
import 'l10n/locale_provider.dart';
import 'services/backend_service.dart';
import 'utils/shortcut.dart';
import 'utils/file_associations.dart';
import 'utils/window_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ── Window service (manages tray icon, window state) ────────────
  final winSvc = WindowService();
  await winSvc.init();
  await winSvc.setupTray();

  // ── One-time setup tasks (async — won't block UI) ─────────────
  unawaited(createDesktopShortcut());
  unawaited(registerFileAssociations());

  runApp(VocalProApp(windowService: winSvc));
}

class VocalProApp extends StatefulWidget {
  final WindowService windowService;
  final BackendService? backendService; // optional, for test injection
  const VocalProApp({super.key, required this.windowService, this.backendService});

  @override
  State<VocalProApp> createState() => _VocalProAppState();
}

class _VocalProAppState extends State<VocalProApp> {
  final _localeProvider = LocaleProvider();
  late final BackendService _backendService;

  bool _showSplash = true;

  @override
  void initState() {
    super.initState();
    _backendService = widget.backendService ?? BackendService();
    _startBackend();
  }

  Future<void> _startBackend() async {
    // Start backend in the background — don't block the splash screen.
    // The home screen will show a "Connecting..." state if the server
    // isn't ready yet (handled by BackendService.health polling).
    final backendFuture = _backendService.start();

    // Show the splash animation for at least 2.5s, at most 4s.
    await Future.any([
      Future.delayed(const Duration(milliseconds: 2500)),
      backendFuture,
    ]);

    // Always transition to home screen, regardless of backend status.
    await Future.delayed(const Duration(milliseconds: 1500));
    if (mounted) setState(() => _showSplash = false);
  }

  @override
  void dispose() {
    _backendService.dispose();
    _localeProvider.dispose();
    widget.windowService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _localeProvider,
      builder: (context, _) {
        return MaterialApp(
          title: 'VocalPro',
          debugShowCheckedModeBanner: false,
          locale: _localeProvider.locale,
          localizationsDelegates: [
            const AppLocalizationsDelegate(),
            ...GlobalMaterialLocalizations.delegates,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          localeResolutionCallback: (locale, supported) {
            if (locale == null) return _localeProvider.locale;
            for (final supportedLocale in supported) {
              if (supportedLocale.languageCode == locale.languageCode) {
                return supportedLocale;
              }
            }
            return _localeProvider.locale;
          },
          theme: ThemeData(
            brightness: Brightness.dark,
            scaffoldBackgroundColor: Colors.transparent,
            colorScheme: ColorScheme.dark(
              primary: AppColors.accentPurple,
              secondary: AppColors.accentPink,
              surface: AppColors.surface,
              error: AppColors.error,
            ),
            cardTheme: CardThemeData(
              color: AppColors.surface,
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: const BorderSide(color: AppColors.glassBorder),
              ),
            ),
            textTheme: GoogleFonts.interTextTheme(
              ThemeData(brightness: Brightness.dark).textTheme,
            ).apply(
              bodyColor: AppColors.textSecondary,
              displayColor: AppColors.textPrimary,
            ),
            useMaterial3: true,
          ),
          home: AnimatedSwitcher(
            duration: const Duration(milliseconds: 600),
            switchInCurve: Curves.easeOutCubic,
            switchOutCurve: Curves.easeInCubic,
            transitionBuilder: (Widget child, Animation<double> animation) {
              return FadeTransition(
                opacity: animation,
                child: child,
              );
            },
            child: _showSplash
                ? const SplashScreen(
                    key: ValueKey('splash'),
                  )
                : HomeScreen(
                    key: const ValueKey('home'),
                    localeProvider: _localeProvider,
                    backendService: _backendService,
                    windowService: widget.windowService,
                  ),
          ),
        );
      },
    );
  }
}
