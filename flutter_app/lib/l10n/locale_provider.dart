import 'package:flutter/material.dart';
import 'app_localizations.dart';

/// Provides the current locale and notifies listeners on change.
///
/// Actual [AppLocalizations] instances are created by the
/// [AppLocalizationsDelegate] and looked up via
/// `AppLocalizations.instance(context)` — no need to hold one here.
class LocaleProvider extends ChangeNotifier {
  Locale _locale = const Locale('en');

  Locale get locale => _locale;

  List<Locale> get supportedLocales =>
      AppLocalizations.supportedLocales;

  List<Locale> get displayedLocales =>
      AppLocalizations.displayedLocales;

  void setLocale(Locale locale) {
    if (!AppLocalizations.isSupported(locale)) return;
    _locale = locale;
    notifyListeners();
  }

  /// Build the MaterialApp locale resolution.
  Locale resolveLocale(Locale? deviceLocale) {
    if (deviceLocale == null) return _locale;
    if (AppLocalizations.isSupported(deviceLocale)) return deviceLocale;
    // Try language-only
    final lang = Locale(deviceLocale.languageCode);
    if (AppLocalizations.isSupported(lang)) return lang;
    return _locale;
  }
}
