import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/sidebar.dart';
import '../widgets/changelog_dialog.dart';
import '../services/api_service.dart';
import '../services/backend_service.dart';
import '../utils/window_service.dart';
import '../l10n/locale_provider.dart';
import 'separation_screen.dart';
import 'results_screen.dart';
import 'history_screen.dart';
import 'settings_screen.dart';

/// Main home screen with sidebar navigation and content area.
/// Starts directly on the Separation screen — the dashboard/home tab
/// has been removed per user request to simplify the UI.
class HomeScreen extends StatefulWidget {
  final LocaleProvider localeProvider;
  final BackendService backendService;
  final WindowService windowService;
  const HomeScreen({
    super.key,
    required this.localeProvider,
    required this.backendService,
    required this.windowService,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;
  final _api = ApiService();
  bool _changelogShown = false;

  @override
  void initState() {
    super.initState();
    _api.connectWebSocket();
    // Show changelog on first load after backend is confirmed running
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_changelogShown) {
        _changelogShown = true;
        ChangelogDialog.show(context);
      }
    });
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.backgroundGradient),
        child: Row(
          children: [
            SideBar(
              selectedIndex: _selectedIndex,
              onSelected: (i) => setState(() => _selectedIndex = i),
            ),
            Expanded(
              child: _buildContent(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent() {
    final Widget screen;
    switch (_selectedIndex) {
      case 0:
        screen = SeparationScreen(
          api: _api,
          localeProvider: widget.localeProvider,
          backendService: widget.backendService,
        );
        break;
      case 1:
        screen = ResultsScreen(api: _api, localeProvider: widget.localeProvider);
        break;
      case 2:
        screen = HistoryScreen(api: _api, localeProvider: widget.localeProvider);
        break;
      case 3:
        screen = SettingsScreen(
          api: _api,
          localeProvider: widget.localeProvider,
          windowService: widget.windowService,
        );
        break;
      default:
        screen = const SizedBox.shrink();
    }
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      transitionBuilder: (Widget child, Animation<double> animation) {
        return SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0.04, 0),
            end: Offset.zero,
          ).animate(CurvedAnimation(
            parent: animation,
            curve: Curves.easeOutCubic,
          )),
          child: FadeTransition(
            opacity: animation,
            child: child,
          ),
        );
      },
      child: KeyedSubtree(
        key: ValueKey(_selectedIndex),
        child: screen,
      ),
    );
  }
}
