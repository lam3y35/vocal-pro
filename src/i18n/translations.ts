export type SupportedLocale =
  | "en"
  | "es"
  | "fr"
  | "de"
  | "it"
  | "pt"
  | "ru"
  | "ja"
  | "zh"
  | "ko"
  | "ar"
  | "hi"
  | "tr"
  | "nl"
  | "pl"
  | "sv";

export const LOCALE_LABELS: Record<SupportedLocale, string> = {
  en: "English",
  ar: "العربية (Arabic)",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
  it: "Italiano",
  pt: "Português",
  ru: "Русский",
  ja: "日本語",
  zh: "中文",
  ko: "한국어",
  hi: "हिन्दी",
  tr: "Türkçe",
  nl: "Nederlands",
  pl: "Polski",
  sv: "Svenska",
};

const BASE_EN = {
  nav_home: "Dashboard",
  nav_separate: "Separation",
  nav_results: "Results & Mixer",
  nav_history: "History",
  nav_settings: "Settings",
  app_subtitle: "Studio AI Vocal & Stem Separator",
  btn_start_separation: "Start Separation",
  btn_cancel_job: "Cancel Job",
  btn_add_files: "Add Audio / Video Files",
  btn_export_mix: "Export Mix",
  btn_export_separate: "Export Custom Stems",
  btn_stem_to_midi: "Export MIDI (.mid)",
  btn_analyze: "Analyze BPM & Key",
  song_mode_title: "Song Mode (1-Click Studio Vocal Preset)",
  song_mode_desc:
    "Automatically locks optimal vocal isolation settings: Audio-only, Spectral Denoise, Vocal Gate, Silence Trim, no SFX bleed.",
  download_card_title: "Direct Media URL Downloader",
  log_card_title: "Engine & Worker Live Stream",
  whats_new: "What's New",
};

export const TRANSLATIONS: Record<SupportedLocale, typeof BASE_EN> = {
  en: BASE_EN,
  ar: {
    nav_home: "لوحة التحكم",
    nav_separate: "فصل الصوت",
    nav_results: "النتائج والميكسر",
    nav_history: "السجل",
    nav_settings: "الإعدادات",
    app_subtitle: "استوديو فصل الصوتيات بالذكاء الاصطناعي",
    btn_start_separation: "بدء الفصل الآن",
    btn_cancel_job: "إلغاء المهمة",
    btn_add_files: "إضافة ملفات صوت أو فيديو",
    btn_export_mix: "تصدير المزيج",
    btn_export_separate: "تصدير المسارات منفصلة",
    btn_stem_to_midi: "تحويل إلى MIDI",
    btn_analyze: "تحليل السرعة والمقام (BPM & Key)",
    song_mode_title: "وضع الأغاني (إعداد احترافي بضغطة واحدة)",
    song_mode_desc: "يضبط تلقائياً أفضل إعدادات عزل الصوت البشري مع إزالة الضوضاء والصمت.",
    download_card_title: "تحميل مباشر من رابط وسائط",
    log_card_title: "سجل المحرك المباشر",
    whats_new: "ما الجديد",
  },
  es: {
    ...BASE_EN,
    nav_home: "Inicio",
    nav_separate: "Separación",
    nav_results: "Resultados y Mezclador",
    nav_history: "Historial",
    nav_settings: "Ajustes",
    btn_start_separation: "Iniciar Separación",
    btn_cancel_job: "Cancelar",
  },
  fr: {
    ...BASE_EN,
    nav_home: "Accueil",
    nav_separate: "Séparation",
    nav_results: "Résultats & Mixeur",
    nav_history: "Historique",
    nav_settings: "Paramètres",
    btn_start_separation: "Démarrer la Séparation",
    btn_cancel_job: "Annuler",
  },
  de: {
    ...BASE_EN,
    nav_home: "Übersicht",
    nav_separate: "Trennung",
    nav_results: "Ergebnisse & Mixer",
    nav_history: "Verlauf",
    nav_settings: "Einstellungen",
    btn_start_separation: "Trennung Starten",
    btn_cancel_job: "Abbrechen",
  },
  it: {
    ...BASE_EN,
    nav_home: "Home",
    nav_separate: "Separazione",
    nav_results: "Risultati e Mixer",
    nav_history: "Cronologia",
    nav_settings: "Impostazioni",
  },
  pt: {
    ...BASE_EN,
    nav_home: "Início",
    nav_separate: "Separação",
    nav_results: "Resultados e Mixer",
    nav_history: "Histórico",
    nav_settings: "Configurações",
  },
  ru: {
    ...BASE_EN,
    nav_home: "Главная",
    nav_separate: "Разделение",
    nav_results: "Результаты и Микшер",
    nav_history: "История",
    nav_settings: "Настройки",
  },
  ja: {
    ...BASE_EN,
    nav_home: "ホーム",
    nav_separate: "音声分離",
    nav_results: "結果とミキサー",
    nav_history: "履歴",
    nav_settings: "設定",
  },
  zh: {
    ...BASE_EN,
    nav_home: "主页",
    nav_separate: "人声分离",
    nav_results: "结果与混音器",
    nav_history: "历史记录",
    nav_settings: "设置",
  },
  ko: {
    ...BASE_EN,
    nav_home: "홈",
    nav_separate: "보컬 분리",
    nav_results: "결과 및 믹서",
    nav_history: "기록",
    nav_settings: "설정",
  },
  hi: {
    ...BASE_EN,
    nav_home: "होम",
    nav_separate: "वोकल सेपरेशन",
    nav_results: "परिणाम और मिक्सर",
    nav_history: "इतिहास",
    nav_settings: "सेटिंग्स",
  },
  tr: {
    ...BASE_EN,
    nav_home: "Ana Sayfa",
    nav_separate: "Ayrıştırma",
    nav_results: "Sonuçlar ve Mikser",
    nav_history: "Geçmiş",
    nav_settings: "Ayarlar",
  },
  nl: {
    ...BASE_EN,
    nav_home: "Overzicht",
    nav_separate: "Scheiding",
    nav_results: "Resultaten & Mixer",
    nav_history: "Geschiedenis",
    nav_settings: "Instellingen",
  },
  pl: {
    ...BASE_EN,
    nav_home: "Start",
    nav_separate: "Separacja",
    nav_results: "Wyniki i Mikser",
    nav_history: "Historia",
    nav_settings: "Ustawienia",
  },
  sv: {
    ...BASE_EN,
    nav_home: "Hem",
    nav_separate: "Separering",
    nav_results: "Resultat & Mixer",
    nav_history: "Historik",
    nav_settings: "Inställningar",
  },
};
