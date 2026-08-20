import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/sidebar.dart';
import '../widgets/cards.dart';
import '../widgets/changelog_dialog.dart';
import '../services/api_service.dart';
import '../services/backend_service.dart';
import '../utils/window_service.dart';
import '../l10n/app_localizations.dart';
import '../l10n/locale_provider.dart';
import 'separation_screen.dart';
import 'results_screen.dart';
import 'history_screen.dart';
import 'settings_screen.dart';

/// Main home screen with sidebar navigation and content area.
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
  Map<String, dynamic>? _health;
  bool _loading = false;
  bool _changelogShown = false;

  @override
  void initState() {
    super.initState();
    _checkHealth();
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

  Future<void> _checkHealth() async {
    if (_loading) return;
    setState(() => _loading = true);
    final h = await widget.backendService.health();
    if (!mounted) return;
    setState(() {
      _health = h;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
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
              child: _buildContent(l10n),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(AppLocalizations l10n) {
    final Widget screen;
    switch (_selectedIndex) {
      case 0:
        screen = _DashboardTab(
          health: _health,
          loading: _loading,
          onRefresh: _checkHealth,
          onNavigate: (i) => setState(() => _selectedIndex = i),
        );
        break;
      case 1:
        screen = SeparationScreen(api: _api, localeProvider: widget.localeProvider);
        break;
      case 2:
        screen = ResultsScreen(api: _api, localeProvider: widget.localeProvider);
        break;
      case 3:
        screen = HistoryScreen(api: _api, localeProvider: widget.localeProvider);
        break;
      case 4:
        screen = SettingsScreen(
          api: _api,
          localeProvider: widget.localeProvider,
          backendService: widget.backendService,
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

/// Dashboard / Home tab.
class _DashboardTab extends StatelessWidget {
  final Map<String, dynamic>? health;
  final bool loading;
  final VoidCallback onRefresh;
  final ValueChanged<int> onNavigate;

  const _DashboardTab({
    required this.health,
    required this.loading,
    required this.onRefresh,
    required this.onNavigate,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    final isOnline = health?['status'] == 'ok';
    final gpu = health?['gpu_available'] == true;
    final gpuName = health?['gpu_name'] ?? 'N/A';
    final gpuVram = health?['gpu_vram'] ?? 'N/A';

    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Text(l10n.appTitle, style: AppTextStyles.heading(context)),
              const SizedBox(width: 12),
              StatusBadge(
                text: isOnline ? l10n.serverOnline : l10n.serverOffline,
                color: isOnline ? AppColors.success : AppColors.error,
              ),
              const Spacer(),
              GhostButton(
                label: l10n.refresh,
                icon: Icons.refresh_rounded,
                onPressed: onRefresh,
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            l10n.tagline,
            style: AppTextStyles.body(context),
          ),
          const SizedBox(height: 32),

          // Status cards
          if (loading)
            const Center(
              child: CircularProgressIndicator(color: AppColors.accentPurple),
            )
          else ...[
            Row(
              children: [
                Expanded(
                  child: _StatusCard(
                    icon: Icons.dns_rounded,
                    title: l10n.backend,
                    value: isOnline ? l10n.connected : l10n.disconnected,
                    color: isOnline ? AppColors.success : AppColors.error,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _StatusCard(
                    icon: Icons.memory_rounded,
                    title: l10n.gpu,
                    value: gpu ? gpuName : l10n.notAvailable,
                    color: gpu ? AppColors.info : AppColors.warning,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _StatusCard(
                    icon: Icons.speed_rounded,
                    title: l10n.vram,
                    value: gpu ? gpuVram : 'N/A',
                    color: gpu ? AppColors.info : AppColors.textDim,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 32),

            // Quick actions
            Text(l10n.quickActions, style: AppTextStyles.label(context)),
            const SizedBox(height: 12),
            Row(
              children: [
                _QuickAction(
                  icon: Icons.content_cut_rounded,
                  label: l10n.newSeparation,
                  onTap: () => onNavigate(1),
                ),
                const SizedBox(width: 12),
                _QuickAction(
                  icon: Icons.folder_rounded,
                  label: l10n.viewResults,
                  onTap: () => onNavigate(2),
                ),
                const SizedBox(width: 12),
                _QuickAction(
                  icon: Icons.history_rounded,
                  label: l10n.history,
                  onTap: () => onNavigate(3),
                ),
              ],
            ),
            const Spacer(),

            // Instructions
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.gettingStarted, style: AppTextStyles.subheading(context)),
                  const SizedBox(height: 8),
                  Text(
                    l10n.instructions,
                    style: AppTextStyles.mono(context),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;
  final Color color;

  const _StatusCard({
    required this.icon,
    required this.title,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTextStyles.label(context)),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: AppTextStyles.body(context).copyWith(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w500,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _QuickAction({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: GlassCard(
          highlighted: true,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: AppColors.accentPurple, size: 32),
              const SizedBox(height: 10),
              Text(label, style: AppTextStyles.body(context)),
            ],
          ),
        ),
      ),
    );
  }
}
