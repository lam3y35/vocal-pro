import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Localized strings for every user-facing text in VocalPro.
///
/// Translations are loaded at runtime from [assets/lang/{lang}.json].
/// English is used as the fallback for any missing keys.
///
/// Usage:  `AppLocalizations.instance(context).someString`
class AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) => AppLocalizations.isSupported(locale);

  @override
  Future<AppLocalizations> load(Locale locale) async {
    final lang = locale.languageCode;
    // Load the target language and English (fallback) in parallel.
    final results = await Future.wait([
      _loadJson('assets/lang/$lang.json'),
      _loadJson('assets/lang/en.json'),
    ]);
    return AppLocalizations(locale, results[0], results[1]);
  }

  @override
  bool shouldReload(AppLocalizationsDelegate old) => false;

  static Future<Map<String, String>> _loadJson(String path) async {
    final data = await rootBundle.loadString(path);
    final decoded = jsonDecode(data);
    return Map<String, String>.from(decoded);
  }
}

class AppLocalizations {
  final Locale locale;
  final Map<String, String> _strings;
  final Map<String, String> _enFallback;

  AppLocalizations(this.locale, this._strings, this._enFallback);

  // ── Supported locales ───────────────────────────────────────────

  static const supportedLocales = [
    Locale('en'), Locale('es'), Locale('fr'), Locale('de'),
    Locale('it'), Locale('pt'), Locale('ru'), Locale('ja'),
    Locale('zh'), Locale('ko'), Locale('ar'), Locale('hi'),
    Locale('tr'), Locale('nl'), Locale('pl'), Locale('sv'),
  ];

  static const displayedLocales = [
    Locale('en', 'US'), Locale('es', 'ES'), Locale('fr', 'FR'),
    Locale('de', 'DE'), Locale('it', 'IT'), Locale('pt', 'BR'),
    Locale('ru', 'RU'), Locale('ja', 'JP'), Locale('zh', 'CN'),
    Locale('ko', 'KR'), Locale('ar', 'SA'), Locale('hi', 'IN'),
    Locale('tr', 'TR'), Locale('nl', 'NL'), Locale('pl', 'PL'),
    Locale('sv', 'SE'),
  ];

  static const languageNames = {
    'en': 'English',
    'es': 'Español',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
    'pt': 'Português',
    'ru': 'Русский',
    'ja': '日本語',
    'zh': '简体中文',
    'ko': '한국어',
    'ar': 'العربية',
    'hi': 'हिन्दी',
    'tr': 'Türkçe',
    'nl': 'Nederlands',
    'pl': 'Polski',
    'sv': 'Svenska',
  };

  static bool isSupported(Locale locale) =>
      supportedLocales.any((l) => l.languageCode == locale.languageCode);

  // ── Lookup ──────────────────────────────────────────────────────

  String _tr(String key) => _strings[key] ?? _enFallback[key] ?? key;

  // ── General ─────────────────────────────────────────────────────
  String get appTitle => _tr('appTitle');
  String get language => _tr('language');
  String get languageDesc => _tr('languageDesc');

  // ── Home ────────────────────────────────────────────────────────
  String get refresh => _tr('refresh');

  // ── Separation ──────────────────────────────────────────────────
  String get separation => _tr('separation');
  String get separationSubtitle => _tr('separationSubtitle');
  String get sourceFiles => _tr('sourceFiles');
  String get sourceFilesSubtitle => _tr('sourceFilesSubtitle');
  String get url => _tr('url');
  String get dropFilesHint => _tr('dropFilesHint');
  String get supportedFormats => _tr('supportedFormats');
  String get shortcuts => _tr('shortcuts');
  String get filesInQueue => _tr('filesInQueue');
  String get outputFolder => _tr('outputFolder');
  String get defaultOutput => _tr('defaultOutput');
  String get preview => _tr('preview');
  String get addFileForWaveform => _tr('addFileForWaveform');
  String get model => _tr('model');
  String get aiModel => _tr('aiModel');
  String get options => _tr('options');
  String get format => _tr('format');
  String get video => _tr('video');
  String get processing => _tr('processing');
  String get reduceNoise => _tr('reduceNoise');
  String get muteWithoutVocals => _tr('muteWithoutVocals');
  String get multibandNoise => _tr('multibandNoise');
  String get autoDetectNoise => _tr('autoDetectNoise');
  String get dynamicGate => _tr('dynamicGate');
  String get trimSilence => _tr('trimSilence');
  String get ensembleMode => _tr('ensembleMode');
  String get output => _tr('output');
  String get extractSfx => _tr('extractSfx');
  String get mixWithSfx => _tr('mixWithSfx');
  String get saveBackground => _tr('saveBackground');
  String get karaokeMode => _tr('karaokeMode');
  String get startSeparation => _tr('startSeparation');
  String get initializing => _tr('initializing');
  String get complete => _tr('complete');
  String get error => _tr('error');
  String get cancelled => _tr('cancelled');
  String get log => _tr('log');
  String get readyLog => _tr('readyLog');
  String get loadFromUrl => _tr('loadFromUrl');
  String get pasteUrlHint => _tr('pasteUrlHint');
  String get videoPlusAudio => _tr('videoPlusAudio');
  String get videoOnly => _tr('videoOnly');
  String get audioOnly => _tr('audioOnly');
  String get clear => _tr('clear');
  String get download => _tr('download');
  String get cancel => _tr('cancel');
  String get retry => _tr('retry');
  String get loading => _tr('loading');

  // ── Results ─────────────────────────────────────────────────────
  String get resultsAndStemMixer => _tr('resultsAndStemMixer');
  String get resultsSubtitle => _tr('resultsSubtitle');
  String get noOutputsYet => _tr('noOutputsYet');
  String get runSeparationToSee => _tr('runSeparationToSee');
  String get outputFolders => _tr('outputFolders');
  String get selectFolderToView => _tr('selectFolderToView');
  String get stemMixer => _tr('stemMixer');
  String get stemsLoaded => _tr('stemsLoaded');
  String get master => _tr('master');
  String get reset => _tr('reset');
  String get stop => _tr('stop');
  String get exportMix => _tr('exportMix');
  String get exportAll => _tr('exportAll');
  String get midiAll => _tr('midiAll');
  String get files => _tr('files');
  String get open => _tr('open');
  String get extractMidi => _tr('extractMidi');
  String get openFileLocation => _tr('openFileLocation');

  // ── History ─────────────────────────────────────────────────────
  String get history => _tr('history');
  String get separations => _tr('separations');
  String get downloads => _tr('downloads');
  String get sepHistorySubtitle => _tr('sepHistorySubtitle');
  String get dlHistorySubtitle => _tr('dlHistorySubtitle');
  String get noSepHistory => _tr('noSepHistory');
  String get noDlHistory => _tr('noDlHistory');
  String get clearAllHistory => _tr('clearAllHistory');
  String get entries => _tr('entries');
  String get noFilePathsInHistory => _tr('noFilePathsInHistory');
  String get rerun => _tr('rerun');

  // ── Settings ────────────────────────────────────────────────────
  String get settings => _tr('settings');
  String get settingsSubtitle => _tr('settingsSubtitle');
  String get serverConnection => _tr('serverConnection');
  String get serverEndpointSubtitle => _tr('serverEndpointSubtitle');
  String get test => _tr('test');
  String get general => _tr('general');
  String get processingBehavior => _tr('processingBehavior');
  String get safeMode => _tr('safeMode');
  String get safeModeDesc => _tr('safeModeDesc');
  String get autoPreview => _tr('autoPreview');
  String get autoPreviewDesc => _tr('autoPreviewDesc');
  String get outputFormat => _tr('outputFormat');
  String get advancedTuning => _tr('advancedTuning');
  String get fineTune => _tr('fineTune');
  String get ffmpeg => _tr('ffmpeg');
  String get ffmpegSubtitle => _tr('ffmpegSubtitle');
  String get audioBitrate => _tr('audioBitrate');

  // ── Sidebar ─────────────────────────────────────────────────────
  String get stems => _tr('stems');

  // ── Waveform ────────────────────────────────────────────────────
  String get noAudioLoaded => _tr('noAudioLoaded');
  String get play => _tr('play');
  String get pause => _tr('pause');
  String get points => _tr('points');

  // ── Model descriptions ──────────────────────────────────────────
  String get modelHtdemucsFt => _tr('model_htdemucs_ft');
  String get modelHtdemucs => _tr('model_htdemucs');
  String get modelHtdemucs6s => _tr('model_htdemucs_6s');
  String get modelHdemucsMmi => _tr('model_hdemucs_mmi');
  String get modelMdx => _tr('model_mdx');
  String get modelMdxExtra => _tr('model_mdx_extra');
  String get modelMdxQ => _tr('model_mdx_q');
  String get modelMdxExtraQ => _tr('model_mdx_extra_q');



  // ── Late additions ──────────────────────────────────────────────
  String get advanced => _tr('advanced');
  String get reveal => _tr('reveal');
  String get save => _tr('save');
  String get generateComparisonSamples => _tr('generateComparisonSamples');

  // ── Song Mode ───────────────────────────────────────────────────
  String get songMode => _tr('songMode');
  String get songModeActiveDesc => _tr('songModeActiveDesc');
  String get songModeInactiveDesc => _tr('songModeInactiveDesc');
  String get songModeAudioOnly => _tr('songModeAudioOnly');
  String get songModeVocalsOnly => _tr('songModeVocalsOnly');
  String get songModeTrimSilence => _tr('songModeTrimSilence');
  String get songModeDenoiseGate => _tr('songModeDenoiseGate');

  /// Helper: access localized string by key (for dynamic lookups).
  String get(String key) => _tr(key);

  /// Lookup from context.
  static AppLocalizations instance(BuildContext context) =>
      Localizations.of(context, AppLocalizations)!;
}
