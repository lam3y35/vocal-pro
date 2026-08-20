import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:window_manager/window_manager.dart';
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

  // ── Window manager setup ──────────────────────────────────────────
  await WindowManager.instance.ensureInitialized();
  await WindowManager.instance.setTitle('VocalPro');
  await WindowManager.instance.setSize(const Size(1280, 720));
  await WindowManager.instance.setMinimumSize(const Size(960, 600));
  await WindowManager.instance.center();
  await WindowManager.instance.setSkipTaskbar(false);

  final winSvc = WindowService();
  await winSvc.init();
  await winSvc.loadWindowPosition();
  await winSvc.setupTray();

  // ── One-time setup tasks ─────────────────────────────────────────
  createDesktopShortcut();
  registerFileAssociations();

  // ── Listen for window close to minimize-to-tray ──────────────────
  WindowManager.instance.addListener(WindowCloseListener());

  runApp(VocalProApp(windowService: winSvc));
}

/// Listens for window close events to minimize to tray instead.
class WindowCloseListener extends WindowListener {
  @override
  void onWindowClose() async {
    WindowService().handleClose();
  }

  @override
  void onWindowResized() async {
    // Save position periodically
    WindowService().saveWindowPosition();
  }

  @override
  void onWindowMoved() async {
    WindowService().saveWindowPosition();
  }
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

  // Splash / backend state machine:
  //   splashAnimate  – splash animation is still playing
  //   backendLoading – backend is being started (animation may have finished)
  //   backendReady   – backend is confirmed running (brief wait then fade)
  //   backendError   – backend failed to start after max wait
  String _appState = 'splashAnimate';
  String? _backendError;
  Timer? _splashTimer;

  @override
  void initState() {
    super.initState();
    _backendService = widget.backendService ?? BackendService();
    _startBackend();

    // Minimum splash animation time (~2s) before showing backend loading state.
    _splashTimer = Timer(const Duration(milliseconds: 2000), () {
      if (mounted && _appState == 'splashAnimate') {
        setState(() => _appState = 'backendLoading');
      }
    });
  }

  Future<void> _startBackend() async {
    final success = await _backendService.start();
    if (!mounted) return;
    if (success) {
      setState(() => _appState = 'backendReady');
      // Brief pause so the splash can show "Connected" before crossfading.
      await Future.delayed(const Duration(milliseconds: 600));
      if (mounted) setState(() => _showSplash = false);
    } else {
      setState(() {
        _appState = 'backendError';
        _backendError = _backendService.startAttempted
            ? 'Failed to start the API server.\nCheck that Python is installed and'
                ' the api_server/ directory is present.'
            : null;
      });
    }
  }

  Future<void> _retryBackend() async {
    setState(() {
      _appState = 'backendLoading';
      _backendError = null;
    });
    await _startBackend();
  }

  @override
  void dispose() {
    _splashTimer?.cancel();
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
                ? SplashScreen(
                    key: const ValueKey('splash'),
                    appState: _appState,
                    errorMessage: _backendError,
                    onRetry: _retryBackend,
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
