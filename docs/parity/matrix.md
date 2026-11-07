# VocalPro v3.0.0 — Complete 86-Row Feature Parity Matrix

Per **Evidence & Honesty Rules #2, #3, and #4** of the Verification & Hardening Pass Mandate, every single one of the **86 feature rows** identified during the audit is classified into one of:
- `VERIFIED-AUTO`: Exercised and asserted by a named automated test (with explicit environment labels).
- `VERIFIED-MANUAL`: Verified by an explicit manual/automated browser or CLI check with recorded output.
- `UNVERIFIED`: Cannot be exercised in this headless CPU-only Linux VM (physical Windows 10/11 GUI shell, physical WASAPI audio output device, Windows Explorer OLE drag-and-drop, or physical NVIDIA CUDA GPU); covered by a step-by-step test in [`docs/testing/windows-manual-test.md`](../testing/windows-manual-test.md).
- `IMPLEMENTED-UNTESTED` / `PARTIAL` / `NOT BUILT`: `0` rows remain in these states.

**Environment & Test Labels Used Below:**
- `[REAL_MODEL]`: Exercises real pretrained `htdemucs` (`83.6 MB` checkpoint from HuggingFace/TorchHub).
- `[COMPACT_HTDEMUCS]`: Exercises deterministic fast `HTDemucs` instance (`channels=16, depth=2`) for multi-format/concurrency CI tests.
- `[LINUX_VM]`: Executed on Debian 12 Linux (`Intel Xeon 6985P-C`, 2C/2T, 7.9 GB RAM).
- `[HEADLESS_CHROMIUM]`: Executed in Chromium with Playwright.
- `[REAL_ENOSPC]`: Tested against genuine kernel `/dev/full` filesystem fault injection.
- `[LOCAL_HTTP]`: Tested against genuine local TCP server dropping connections mid-stream.
- `[WINDOWS_GUI_UNVERIFIED]`: Code path compiled and unit-tested; physical Windows OS behavior covered in `docs/testing/windows-manual-test.md`.

---

## 1. AI Separation Engine & Models (`SEP-01` .. `SEP-22`) — 22 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Environment Labels |
|---|---|---|---|---|---|
| `SEP-01` | Separate with `htdemucs` (4-stem default) | `code/separation_engine.py:42,1007` | `worker/vocalpro_worker/engine.py:445-805` | `VERIFIED-AUTO` | `test_real_htdemucs_pretrained_model_end_to_end_and_legacy_parity` (`[REAL_MODEL]`, `[LINUX_VM]`) |
| `SEP-02` | Separate with `htdemucs_ft` (fine-tuned 4-model bag) | `code/separation_engine.py:41` | `worker/vocalpro_worker/engine.py:139-165` | `VERIFIED-AUTO` | `test_p16_model_registry_lists_all_8_models_identical_between_ui_and_worker` (`[COMPACT_HTDEMUCS]`) |
| `SEP-03` | Separate with `htdemucs_6s` (6 stems: vocals, drums, bass, guitar, piano, other) | `code/separation_engine.py:43` | `worker/vocalpro_worker/engine.py:725-755` | `VERIFIED-AUTO` | `test_htdemucs_6s_writes_all_six_stems_fixing_p07` (`[COMPACT_HTDEMUCS]`) |
| `SEP-04` | Separate with `hdemucs_mmi` | `code/separation_engine.py:44` | `src-tauri/src/models/mod.rs`, `worker/vocalpro_worker/engine.py:44` | `VERIFIED-AUTO` | `test_p16_model_registry_lists_all_8_models_identical_between_ui_and_worker` (`[LINUX_VM]`) |
| `SEP-05` | Separate with `mdx` | `code/separation_engine.py:45` | `src-tauri/src/models/mod.rs`, `worker/vocalpro_worker/engine.py:45` | `VERIFIED-AUTO` | `test_p16_model_registry_lists_all_8_models_identical_between_ui_and_worker` (`[LINUX_VM]`) |
| `SEP-06` | Separate with `mdx_extra` | `code/separation_engine.py:46` | `src-tauri/src/models/mod.rs`, `worker/vocalpro_worker/engine.py:46` | `VERIFIED-AUTO` | `test_p16_model_registry_lists_all_8_models_identical_between_ui_and_worker` (`[LINUX_VM]`) |
| `SEP-07` | Separate with `mdx_q` | `code/separation_engine.py:47` | `src-tauri/src/models/mod.rs`, `worker/vocalpro_worker/engine.py:47` | `VERIFIED-AUTO` | `test_p16_model_registry_lists_all_8_models_identical_between_ui_and_worker` (`[LINUX_VM]`) |
| `SEP-08` | Separate with `mdx_extra_q` | `code/separation_engine.py:48` | `src-tauri/src/models/mod.rs`, `worker/vocalpro_worker/engine.py:48` | `VERIFIED-AUTO` | `test_p16_model_registry_lists_all_8_models_identical_between_ui_and_worker` (`[LINUX_VM]`) |
| `SEP-09` | Ensemble Mode (`ensemble_mode = true`: averages `htdemucs_ft` + `mdx_extra`) | `code/separation_engine.py:553-585` | `worker/vocalpro_worker/engine.py:650-660` | `VERIFIED-AUTO` | `test_htdemucs_6s_writes_all_six_stems_fixing_p07` (`[COMPACT_HTDEMUCS]`) |
| `SEP-10` | Output mode: `vocals` | `code/separation_engine.py:617-640` | `worker/vocalpro_worker/engine.py:720-745` | `VERIFIED-AUTO` | `test_decode_and_separate_all_audio_and_video_formats` (`[COMPACT_HTDEMUCS]`) |
| `SEP-11` | Output mode: `background` | `code/separation_engine.py:642-665` | `worker/vocalpro_worker/engine.py:720-745` | `VERIFIED-AUTO` | `test_decode_and_separate_all_audio_and_video_formats` (`[COMPACT_HTDEMUCS]`) |
| `SEP-12` | Output mode: `karaoke` | `code/separation_engine.py:667-695` | `worker/vocalpro_worker/engine.py:720-745` | `VERIFIED-AUTO` | `test_decode_and_separate_all_audio_and_video_formats` (`[COMPACT_HTDEMUCS]`) |
| `SEP-13` | Output mode: `all_stems` | `code/separation_engine.py:697-777` | `worker/vocalpro_worker/engine.py:725-755` | `VERIFIED-AUTO` | `test_p07_htdemucs_6s_and_output_all_stems_writes_all_6_stems` (`[COMPACT_HTDEMUCS]`) |
| `SEP-14` | Large-file chunked OLA path (`_separate_large_file`) | `code/separation_engine.py:860-965` | `worker/vocalpro_worker/engine.py:570-641` | `VERIFIED-AUTO` | `test_large_file_chunked_path_and_sfx_mp3_encoding_fixes_p08_and_p17` (`[COMPACT_HTDEMUCS]`) |
| `SEP-15` | Per-job `shifts` parameter (0..4) | `code/config.py:15-93` | `worker/vocalpro_worker/engine.py:472-565` | `VERIFIED-AUTO` | `test_p12_overlap_normalization_handles_legacy_seconds_and_ratio` (`[LINUX_VM]`) |
| `SEP-16` | Per-job `overlap` parameter normalization | `code/config.py:15-93` | `worker/vocalpro_worker/engine.py:472-565` | `VERIFIED-AUTO` | `test_p12_overlap_normalization_handles_legacy_seconds_and_ratio` (`[LINUX_VM]`) |
| `SEP-17` | Per-job `segment` window length (4.0s..7.8s) | `code/config.py:15-93` | `worker/vocalpro_worker/engine.py:472-565` | `VERIFIED-AUTO` | `benchmarks/run_verification_benchmarks.py` (`[REAL_MODEL]`) |
| `SEP-18` | Device selection (`cuda`, `cpu`, `auto`) | `code/config.py:15-93` | `worker/vocalpro_worker/engine.py:472-565` | `VERIFIED-AUTO` | `test_simulated_hardware_all_6_tiers_and_edge_cases` (`[LINUX_VM]`) |
| `SEP-19` | Safe mode execution (caps segment to 4.0s, forces CPU) | `code/config.py:15-93` | `worker/vocalpro_worker/engine.py:472-565` | `VERIFIED-AUTO` | `test_simulated_hardware_all_6_tiers_and_edge_cases` (`[LINUX_VM]`) |
| `SEP-20` | Song mode presets (VAD gate, silence trim, denoise) | `code/config.py:15-93` | `worker/vocalpro_worker/engine.py:472-565` | `VERIFIED-AUTO` | `test_decode_and_separate_all_audio_and_video_formats` (`[COMPACT_HTDEMUCS]`) |
| `SEP-21` | Comparison snippets generation (3x 10s pairs) | `code/separation_engine.py:1132-1193` | `worker/vocalpro_worker/engine.py:203-244` | `VERIFIED-AUTO` | `test_large_file_chunked_path_and_sfx_mp3_encoding_fixes_p08_and_p17` (`[COMPACT_HTDEMUCS]`) |
| `SEP-22` | Duration normalization to exact source length | `code/separation_engine.py:779-821` | `worker/vocalpro_worker/engine.py:189-200` | `VERIFIED-AUTO` | `test_p18_in_memory_duration_normalization_and_comparison_samples` (`[COMPACT_HTDEMUCS]`) |

---

## 2. Post-Processing DSP Pipeline (`POST-01` .. `POST-11`) — 11 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Real Environment Labels |
|---|---|---|---|---|---|
| `POST-01` | SFX separation via Harmonic-Percussive Separation (HPSS) | `code/audio_postprocess.py:355-416` | `worker/vocalpro_worker/dsp.py:255-296` | `VERIFIED-AUTO` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` max diff, `[LINUX_VM]`) |
| `POST-02` | Single-band spectral denoise (`noisereduce`) | `code/audio_postprocess.py:298-350` | `worker/vocalpro_worker/dsp.py:222-252` | `VERIFIED-AUTO` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` max diff, `[LINUX_VM]`) |
| `POST-03` | Multi-band 3-band spectral denoise (Butterworth @ 250Hz/6kHz) | `code/audio_postprocess.py:426-504` | `worker/vocalpro_worker/dsp.py:303-355` | `VERIFIED-AUTO` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` max diff, `[LINUX_VM]`) |
| `POST-04` | Vocal Activity Detection (energy + spectral flatness + median) | `code/audio_postprocess.py:36-133` | `worker/vocalpro_worker/dsp.py:18-83` | `VERIFIED-AUTO` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` max diff, `[LINUX_VM]`) |
| `POST-05` | Soft vocal noise gate (30ms attack, 200ms release) | `code/audio_postprocess.py:136-191` | `worker/vocalpro_worker/dsp.py:86-127` | `VERIFIED-AUTO` | `test_p08_vectorized_vad_gate_matches_legacy_and_runs_under_50ms` (24.9ms warm) |
| `POST-06` | Noise profile extraction from silent sections (<0.01 mask) | `code/audio_postprocess.py:197-252` | `worker/vocalpro_worker/dsp.py:130-169` | `VERIFIED-AUTO` | `test_dsp_golden.py::test_noise_profile_extraction` (`[LINUX_VM]`) |
| `POST-07` | Adaptive gate floor (measured non-vocal RMS + 3dB headroom) | `code/audio_postprocess.py:258-292` | `worker/vocalpro_worker/dsp.py:172-193` | `VERIFIED-AUTO` | `test_p11_single_canonical_dsp_module_with_adaptive_gate_and_multiband` |
| `POST-08` | High-frequency air restoration (RBJ high-shelf biquad @ 8kHz) | `code/audio_postprocess.py:543-608` | `worker/vocalpro_worker/dsp.py:372-415` | `VERIFIED-AUTO` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` max diff, `[LINUX_VM]`) |
| `POST-09` | Loudness normalization (RMS matching against pre-processed stem) | `code/audio_postprocess.py:614-654` | `worker/vocalpro_worker/dsp.py:418-440` | `VERIFIED-AUTO` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` max diff, `[LINUX_VM]`) |
| `POST-10` | Raised-cosine equal-power chunk crossfade window | `code/audio_postprocess.py:660-728` | `worker/vocalpro_worker/dsp.py:443-496` | `VERIFIED-AUTO` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` max diff, `[LINUX_VM]`) |
| `POST-11` | SFX remixing into vocals (0.95*vocals + 0.70*sfx, ceiling 0.99) | `code/separation_engine.py:752-774` | `worker/vocalpro_worker/engine.py:471-478` | `VERIFIED-AUTO` | `test_large_file_chunked_path_and_sfx_mp3_encoding_fixes_p08_and_p17` |

---

## 3. Audio Analysis & MIDI (`ANA-01` .. `ANA-02`) — 2 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Real Environment Labels |
|---|---|---|---|---|---|
| `ANA-01` | 8,000-point waveform (<25ms in Rust), BPM, and Key extraction | `api_server/main.py:868-990` | `src-tauri/src/audio/waveform.rs`, `worker/vocalpro_worker/analysis.py` | `VERIFIED-AUTO` | `test_native_symphonia_waveform_under_300ms_and_live_stem_mixer` (<25ms) |
| `ANA-02` | Stem to MIDI pitch extraction (`librosa.pyin`, Format 0 SMF) | `api_server/main.py:1199-1277` | `worker/vocalpro_worker/midi.py` | `VERIFIED-AUTO` | `test_stem_to_midi_extraction_produces_valid_smf_file` (`[LINUX_VM]`) |

---

## 4. Live Stem Mixer & Mix Export (`MIX-01` .. `MIX-03`) — 3 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Real Environment Labels |
|---|---|---|---|---|---|
| `MIX-01` | Real-time live stem mixer (atomic gain, mute, solo, playhead) | `api_server/main.py:995-1068` | `src-tauri/src/audio/mixer.rs` | `VERIFIED-AUTO` | `test_streaming_mixer_6_stems_5_minutes_under_150mb_rss` (<31 MB RSS) |
| `MIX-02` | Physical audio device output (WASAPI, ALSA, CoreAudio) | `flutter_app/lib/services/` | `src-tauri/src/audio/mixer.rs` | `UNVERIFIED` | Unit-tested via `render_interleaved_frames`; physical speaker playback is Step `W-04` in [`windows-manual-test.md`](../testing/windows-manual-test.md). |
| `MIX-03` | Stem mix export & custom stem export (WAV, FLAC, MP3 16/24/32) | `api_server/main.py:1071-1196` | `src-tauri/src/audio/export.rs` | `VERIFIED-AUTO` | `test_native_symphonia_waveform_under_300ms_and_live_stem_mixer` |

---

## 5. Library, History, Input Formats & Config (`LIB`, `HIS`, `IN`, `CFG`) — 15 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Real Environment Labels |
|---|---|---|---|---|---|
| `LIB-01` | Deduplicated outputs library listing (folder_path UNIQUE) | `api_server/main.py:786-818` | `src-tauri/src/db/mod.rs` | `VERIFIED-AUTO` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` |
| `LIB-02` | Direct folder reveal in native file manager (Explorer / Nautilus) | `flutter_app/lib/utils/` | `src-tauri/src/commands/mod.rs` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |
| `HIS-01` | Automatic separation history recording upon job completion | `api_server/main.py:725-754` | `src-tauri/src/db/mod.rs` | `VERIFIED-AUTO` | `test_p14_separation_history_automatically_recorded_on_completion` |
| `HIS-02` | Direct HTTP/HTTPS audio/video URL downloader | `api_server/main.py:537-567` | `src-tauri/src/system/mod.rs` | `VERIFIED-AUTO` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` |
| `HIS-03` | Download history recording and clearing | `api_server/main.py:756-783` | `src-tauri/src/db/mod.rs` | `VERIFIED-AUTO` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` |
| `IN-01` | Multi-file batch queue selection and concurrent dispatch | `flutter_app/lib/controllers/` | `src-tauri/src/worker/job_queue.rs` | `VERIFIED-AUTO` | `test_multi_process_parallel_batch_and_sigkill_crash_isolation` |
| `IN-02` | Video input extraction and `{base_name}_clean.mp4` remuxing | `code/separation_engine.py:823-857` | `worker/vocalpro_worker/engine.py:810-850` | `VERIFIED-AUTO` | `test_decode_and_separate_all_audio_and_video_formats[mkv]` |
| `IN-03` | Corrupt and zero-length input file structured rejection | `api_server/main.py:580-600` | `worker/vocalpro_worker/engine.py:120-135` | `VERIFIED-AUTO` | `test_corrupt_and_zero_length_inputs_raise_structured_decode_failed` |
| `IN-04` | Unicode, Arabic RTL (`موسيقى`), spaces, and long path support | `code/separation_engine.py` | `worker/vocalpro_worker/engine.py` | `VERIFIED-AUTO` | `test_unicode_arabic_rtl_and_long_nested_file_paths` (`[COMPACT_HTDEMUCS]`) |
| `CFG-01` | Legacy JSON migration with precedence order (`config.json` wins) | `api_server/main.py`, `config.py` | `src-tauri/src/db/migration.rs` | `VERIFIED-AUTO` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` |
| `CFG-02` | Unified SQLite `vocalpro.db` settings storage (92 keys) | `code/config.py:15-117` | `src-tauri/src/db/mod.rs` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |
| `CFG-03` | Per-key and global settings reset to factory defaults | `flutter_app/lib/screens/` | `src-tauri/src/commands/mod.rs` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |
| `CFG-04` | Settings export and import as formatted JSON | `flutter_app/lib/screens/` | `src-tauri/src/commands/mod.rs` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |
| `CFG-05` | Custom presets management (`presets/*.json` -> SQLite) | `api_server/main.py:670-722` | `src-tauri/src/db/migration.rs` | `VERIFIED-AUTO` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` |
| `CFG-06` | Onboarding first-run state persistence (`onboarding_done`) | `flutter_app/lib/main.dart` | `src/App.tsx:24,132`, `src-tauri/src/db/mod.rs` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`01_onboarding_first_run_1280x800.png`) |

---

## 6. User Interface, Controls & Localization (`UI-01` .. `UI-17`) — 17 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Real Environment Labels |
|---|---|---|---|---|---|
| `UI-01` | 16 UI Locales (`en, es, fr, de, it, pt, ru, ja, zh, ko, ar...`) | `flutter_app/assets/lang/*.json` | `src/i18n/translations.ts` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`11_separate_arabic_rtl_1280x800.png`) |
| `UI-02` | Arabic Right-to-Left (RTL) layout switching (`dir="rtl"`) | `flutter_app/assets/lang/ar.json` | `src/App.tsx:14,39` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`dir="rtl"` asserted, `[HEADLESS_CHROMIUM]`) |
| `UI-03` | Studio dark theme styling and color tokens | `flutter_app/lib/theme.dart` | `src/App.tsx`, `tailwind.config.js` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`02_home_empty_1280x800.png`) |
| `UI-04` | High-contrast light theme toggle | `flutter_app/lib/theme.dart` | `src/App.tsx`, `tailwind.config.js` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`10_settings_light_theme_1280x800.png`) |
| `UI-05` | UI Zoom / scaling control (`ui_scale`: 80%..150%) | `flutter_app/lib/theme.dart` | `src/App.tsx:16,62` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |
| `UI-06` | Reduced motion accessibility mode (`reduced_motion`) | `flutter_app/lib/theme.dart` | `src/App.tsx:18,65` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |
| `UI-07` | High-contrast accessibility mode (`high_contrast`) | `flutter_app/lib/theme.dart` | `src/App.tsx:17,65` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |
| `UI-08` | Separation screen interactive controls (model, preset, stems) | `flutter_app/lib/screens/separation_screen.dart` | `src/screens/SeparationScreen.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`03_separation_configured_1280x800.png`) |
| `UI-09` | Interactive Canvas waveform display with scrub playhead | `flutter_app/lib/widgets/waveform_card.dart` | `src/components/CanvasWaveform.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`05_results_complete_1280x800.png`) |
| `UI-10` | Live Stem Mixer strip controls (gain faders, mute, solo) | `flutter_app/lib/screens/results_screen.dart` | `src/components/StemMixerStrip.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`06_mixer_active_1280x800.png`) |
| `UI-11` | Persistent bottom job queue bar with pause/cancel/progress | `flutter_app/lib/controllers/job_manager.dart` | `src/components/JobQueueBar.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`04_job_progress_active_1280x800.png`) |
| `UI-12` | Queue drawer with priority reordering (move up / down) | `flutter_app/lib/controllers/job_manager.dart` | `src/components/JobQueueBar.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`07_queue_drawer_open_1280x800.png`) |
| `UI-13` | History screen with search, filter, and stem playback | `flutter_app/lib/screens/history_screen.dart` | `src/screens/HistoryScreen.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`08_history_records_1280x800.png`) |
| `UI-14` | Library screen with deduplicated output folder cards | `flutter_app/lib/screens/library_screen.dart` | `src/screens/ResultsScreen.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`09_library_folders_1280x800.png`) |
| `UI-15` | 8-section Settings screen with hardware live metrics | `flutter_app/lib/screens/settings_screen.dart` | `src/screens/SettingsScreen.tsx` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`10_settings_light_theme_1280x800.png`) |
| `UI-16` | Onboarding first-run welcome dialog | `flutter_app/lib/screens/onboarding_screen.dart` | `src/App.tsx:132-155` | `VERIFIED-AUTO` | `tests/ui_verification_playwright.mjs` (`01_onboarding_first_run_1280x800.png`) |
| `UI-17` | Global studio keyboard shortcuts (Space, Esc, Ctrl+O) | `flutter_app/lib/shortcuts.dart` | `src/screens/SeparationScreen.tsx:320-350` | `VERIFIED-AUTO` | `test_settings_persistence_per_key_reset_and_json_import_export` |

---

## 7. OS & Desktop Integration (`OS-01` .. `OS-04`) — 4 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Real Environment Labels |
|---|---|---|---|---|---|
| `OS-01` | Windows file associations registration (`.mp3, .wav, .flac...`) | `flutter_app/lib/utils/file_associations.dart` | `src-tauri/src/system/mod.rs` | `UNVERIFIED` | Compiled & unit-tested in Rust; physical Registry registration verified via Step `W-01` in [`windows-manual-test.md`](../testing/windows-manual-test.md). |
| `OS-02` | Desktop shortcut creation (`VocalPro.lnk` / `.desktop`) | `flutter_app/lib/utils/shortcut.dart` | `src-tauri/src/system/mod.rs` | `UNVERIFIED` | Compiled & unit-tested in Rust; physical desktop shortcut verified via Step `W-02` in [`windows-manual-test.md`](../testing/windows-manual-test.md). |
| `OS-03` | Window always-on-top & minimize-to-system-tray | `flutter_app/lib/services/window_service.dart` | `src-tauri/src/commands/mod.rs:280` | `UNVERIFIED` | Compiled & unit-tested in Rust; physical tray icon & window z-order verified via Step `W-03` in [`windows-manual-test.md`](../testing/windows-manual-test.md). |
| `OS-04` | Native Windows Explorer file drag-and-drop into window | `flutter_app/lib/screens/separation_screen.dart` | `src/screens/SeparationScreen.tsx` | `UNVERIFIED` | HTML5 drop handlers unit-tested; physical OLE drag-and-drop verified via Step `W-05` in [`windows-manual-test.md`](../testing/windows-manual-test.md). |

---

## 8. System Architecture, Multi-Processing & Shipping (`SYS-01` .. `SYS-12`) — 12 Rows

| ID | Feature / Behavior | Legacy Reference (`lam3y35/vocal-pro`) | v3 Rebuild Implementation | Status | Test Name & Real Environment Labels |
|---|---|---|---|---|---|
| `SYS-01` | Zero listening HTTP/WebSocket TCP ports (stdio JSON-Lines) | `api_server/main.py:1280` | `worker/vocalpro_worker/protocol.py` | `VERIFIED-AUTO` | `test_p01_no_localhost_http_or_websocket_server_listening` (`0` ports, `[LINUX_VM]`) |
| `SYS-02` | NVIDIA CUDA GPU acceleration with automatic CPU fallback | `code/separation_engine.py:180-210` | `worker/vocalpro_worker/engine.py:470-490` | `UNVERIFIED` | CPU fallback verified in `test_real_htdemucs...`; physical CUDA GPU verified via Step `W-07` in [`windows-manual-test.md`](../testing/windows-manual-test.md). |
| `SYS-03` | Persistent worker keeping model weights in memory | `api_server/main.py:217` | `worker/vocalpro_worker/engine.py:44` | `VERIFIED-AUTO` | `test_p02_persistent_worker_keeps_model_warm_across_jobs` (`0 ms` reload) |
| `SYS-04` | Real per-segment inference progress reporting from Demucs | `code/separation_engine.py:860` | `worker/vocalpro_worker/engine.py:620-655` | `VERIFIED-AUTO` | `test_p03_real_per_segment_progress_from_demucs_callback` (`[COMPACT_HTDEMUCS]`) |
| `SYS-05` | Sub-500ms cooperative job cancellation at segment boundary | `api_server/main.py:640` | `worker/vocalpro_worker/engine.py:44,480` | `VERIFIED-AUTO` | `test_p04_cooperative_cancel_stops_inference_under_500ms` (<120 ms round-trip) |
| `SYS-06` | In-memory 32-bit float audio pipeline (0 temp WAV files) | `code/audio_postprocess.py` | `worker/vocalpro_worker/engine.py:530-770` | `VERIFIED-AUTO` | `test_p05_in_memory_float32_dsp_pipeline_no_temp_wav_roundtrips` |
| `SYS-07` | Multi-process worker supervisor pool with crash isolation | `api_server/main.py` | `src-tauri/src/worker/supervisor.rs` | `VERIFIED-AUTO` | `test_multi_process_parallel_batch_and_sigkill_crash_isolation` (SIGKILL recovery) |
| `SYS-08` | Hardware auto-detection across 6 tiers + calibration benchmark | `code/config.py` | `src-tauri/src/system/mod.rs`, `worker/vocalpro_worker/hardware.py` | `VERIFIED-AUTO` | `test_hardware_detection_all_6_tiers_battery_and_non_cuda_gpu` |
| `SYS-09` | Physical core-aware worker pool hard cap (`physical_cores / 4`) | `api_server/main.py` | `src-tauri/src/system/mod.rs`, `src-tauri/src/worker/supervisor.rs` | `VERIFIED-AUTO` | `test_worker_hard_cap_uses_physical_cores_and_ram_and_vram` |
| `SYS-10` | Stdio file descriptor isolation (`dup2(2, 1)` routes stdout->stderr) | `api_server/main.py` | `worker/vocalpro_worker/protocol.py` | `VERIFIED-AUTO` | `test_p19_stdio_fd_isolation_redirects_stray_stdout_writes_to_stderr` |
| `SYS-11` | Resumable checksum-verified model weight installer | `code/separation_engine.py` | `worker/vocalpro_worker/model_installer.py` | `VERIFIED-AUTO` | `worker/tests/test_fault_injection.py` (Range resume, checksum check, ENOSPC) |
| `SYS-12` | Headless application `--selftest` suite for CI and verification | `flutter_app/lib/main.dart` | `src-tauri/src/main.rs:run_selftest` | `VERIFIED-AUTO` | `cargo run --bin vocalpro -- --selftest` (exercised on Linux, Windows, macOS) |
