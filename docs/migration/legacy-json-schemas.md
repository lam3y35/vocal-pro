# Legacy JSON Files & Schemas (`config.json`, `separation_history.json`, `download_history.json`, `window_settings.json`, `flutter_settings.json`)

**Status:** `[V]` Verified against `code/config.py`, `code/_shared.py`, `api_server/main.py`, `flutter_app/lib/screens/history_screen.dart`, `flutter_app/lib/screens/settings_screen.dart`, `flutter_app/lib/utils/window_service.dart`, and `flutter_app/lib/l10n/locale_provider.dart`.

---

## 1. Legacy File Locations (`[V]`)

| File | Legacy Path (Windows) | Legacy Path (macOS / Linux) | Source (`file:line`) |
|---|---|---|---|
| **Backend Config (v2+)** | `%USERPROFILE%\.vocalpro_config.json` | `~/.vocalpro_config.json` | `code/config.py:120` |
| **Backend Config (v1 legacy)** | `%USERPROFILE%\.vocal_remover_pro_config.json` | `~/.vocal_remover_pro_config.json` | `code/config.py:121` |
| **Separation History** | `%APPDATA%\VocalPro\separation_history.json` | `~/.config/VocalPro/separation_history.json` (or `~/Library/Application Support/VocalPro/separation_history.json`) | `code/_shared.py:21-30` |
| **Download History** | `%APPDATA%\VocalPro\download_history.json` | `~/.config/VocalPro/download_history.json` | `code/_shared.py:29` |
| **Presets Directory** | `%APPDATA%\VocalPro\presets\*.json` | `~/.config/VocalPro/presets/*.json` | `code/_shared.py:31` |
| **Window Settings** | `%APPDATA%\VocalPro\window_settings.json` | `%APPDATA%/VocalPro/window_settings.json` | `flutter_app/lib/utils/window_service.dart:11,105` |
| **Flutter Locale Settings** | `%APPDATA%\VocalPro\flutter_settings.json` | `%APPDATA%/VocalPro/flutter_settings.json` | `flutter_app/lib/l10n/locale_provider.dart:24` |
| **Marker Files** | `%APPDATA%\VocalPro\.version`<br>`%APPDATA%\VocalPro\.shortcut_created`<br>`%APPDATA%\VocalPro\.associations_registered` | Same under data dir | `changelog.dart:49`, `shortcut.dart:23`, `file_associations.dart:33` |

> **Verified Discovery (`P-15 [V]`):** The legacy Python backend wrote config to `~/.vocalpro_config.json` (`Path.home() / ".vocalpro_config.json"`), whereas `_shared.py` and the Flutter client wrote history and UI settings under `%APPDATA%/VocalPro/`. The rebuild migration importer MUST check **both** `~/.vocalpro_config.json` (and `~/.vocal_remover_pro_config.json`) AND `%APPDATA%/VocalPro/config.json` so no user settings are missed.

---

## 2. `~/.vocalpro_config.json` Schema (All 39 Keys `[V]`)

Defined in `code/config.py:15-93` (`DEFAULT_CONFIG`) and validated in `code/config.py:96-117` (`_VALIDATION`):

```json
{
  "model_name": "htdemucs",
  "segment": 6,
  "overlap": 2,
  "shifts": 1,
  "output_format": "wav",
  "output_all_stems": false,
  "device": "auto",
  "large_file_threshold_minutes": 15,
  "chunk_duration_minutes": 12,
  "overlap_seconds": 5,
  "output_video": true,
  "audio_bitrate": "320k",
  "ffmpeg_faststart": true,
  "ffmpeg_path": "",
  "progress_update_interval_seconds": 0.5,
  "video_output_mode": "both",
  "include_sfx": true,
  "save_background_track": false,
  "generate_comparison_samples": false,
  "trim_silence": true,
  "enable_vocal_gate": true,
  "enable_spectral_denoise": true,
  "gate_threshold_db": -55.0,
  "gate_floor_db": -60.0,
  "denoise_strength": 0.55,
  "min_vocal_duration": 0.08,
  "enable_multiband_denoise": false,
  "denoise_band_split_hz": [250.0, 6000.0],
  "denoise_strength_low": 0.35,
  "denoise_strength_mid": 0.10,
  "denoise_strength_high": 0.25,
  "enable_noise_profile": false,
  "adaptive_gate_floor": false,
  "enable_sfx_separation": false,
  "sfx_separation_margin_db": 5.0,
  "sfx_kernel_size": 15,
  "sfx_margin_harmonic_db": 3.0,
  "sfx_margin_percussive_db": 1.0,
  "karaoke_mode": false,
  "ensemble_mode": false,
  "safe_mode": false,
  "max_threads": 0,
  "cooldown_between_chunks_seconds": 0.0,
  "auto_preview": false
}
```

### Validation Ranges (`code/config.py:96-117` `[V]`):
- `segment`: `(1, 60)`
- `overlap`: `(0.0, 30.0)`
- `shifts`: `(0, 10)`
- `large_file_threshold_minutes`: `(1, 180)`
- `chunk_duration_minutes`: `(1, 120)`
- `overlap_seconds`: `(0, 30)`
- `gate_threshold_db`: `(-70.0, -20.0)`
- `gate_floor_db`: `(-90.0, 0.0)`
- `denoise_strength`: `(0.0, 1.0)`
- `min_vocal_duration`: `(0.01, 2.0)`
- `sfx_separation_margin_db`: `(1.0, 15.0)`
- `sfx_kernel_size`: `(3, 51)` (odd integer)
- `sfx_margin_harmonic_db`: `(0.5, 15.0)`
- `sfx_margin_percussive_db`: `(0.5, 15.0)`
- `denoise_strength_low`: `(0.0, 1.0)`
- `denoise_strength_mid`: `(0.0, 1.0)`
- `denoise_strength_high`: `(0.0, 1.0)`
- `max_threads`: `(0, 64)`
- `cooldown_between_chunks_seconds`: `(0.0, 60.0)`

---

## 3. `separation_history.json` Schema (`[V]`)

Verified from `api_server/main.py:725-754` and `flutter_app/lib/screens/history_screen.dart:118-243`.
File contains a JSON array of objects:

```json
[
  {
    "files": ["C:\\Users\\User\\Music\\song.mp3"],
    "model": "htdemucs_ft",
    "device": "cuda",
    "status": "success",
    "date": "2026-03-15 14:22:10",
    "elapsed": "45.2s",
    "output_dir": "C:\\Users\\User\\Music\\output_vocals\\song"
  }
]
```

- `files`: `string[]` (array of input file paths; UI reads `(item['files'] as List?)?.join(', ')`)
- `model`: `string` (e.g., `"htdemucs"`, `"htdemucs_ft"`, `"htdemucs_6s"`)
- `device`: `string` (`"cuda"`, `"cpu"`, `"auto"`)
- `status`: `"success"` | `"error"` | `"cancelled"`
- `date`: `string` (ISO-8601 or `"YYYY-MM-DD HH:MM:SS"`)
- `elapsed`: `string` or `number` (e.g., `"45.2s"` or seconds)
- `output_dir`: `string` (optional path to output folder)

---

## 4. `download_history.json` Schema (`[V]`)

Verified from `api_server/main.py:756-783` and `flutter_app/lib/screens/history_screen.dart:245-343`.
File contains a JSON array of objects:

```json
[
  {
    "title": "track.mp3",
    "url": "https://example.com/audio/track.mp3",
    "path": "C:\\Users\\User\\AppData\\Roaming\\VocalPro\\uploads\\track.mp3",
    "format": "MP3",
    "quality": "320k",
    "date": "2026-03-15 14:20:00"
  }
]
```

- `title`: `string` (filename or track title)
- `url`: `string` (source HTTP/HTTPS URL)
- `path`: `string` (local saved file path; UI supports "Open File Location" if file exists)
- `format`: `string` (e.g. `"MP3"`, `"WAV"`, `"MP4"`)
- `quality`: `string` (optional, e.g. `"Original"` or `"320k"`)
- `date`: `string`

---

## 5. `window_settings.json` & `flutter_settings.json` Schemas (`[V]`)

### `window_settings.json` (`flutter_app/lib/utils/window_service.dart:61-103`)
```json
{
  "width": 1280.0,
  "height": 820.0,
  "x": 100.0,
  "y": 100.0,
  "always_on_top": false,
  "minimize_to_tray": false
}
```

### `flutter_settings.json` (`flutter_app/lib/l10n/locale_provider.dart:24-48`)
```json
{
  "locale": "en"
}
```
Supported locale codes (`16` languages `[V]`): `en`, `es`, `fr`, `de`, `it`, `pt`, `ru`, `ja`, `zh`, `ko`, `ar`, `hi`, `tr`, `nl`, `pl`, `sv`.
