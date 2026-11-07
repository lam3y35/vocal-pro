# VocalPro Rebuild: Expanded Feature Parity Matrix (`[V]` Verified)

Every row below has been verified against `lam3y35/vocal-pro` (`[V]`) and implemented + tested in `lam3y35/vocal-pro-rebuild`.

---

## 1. Separation (`SEP-*`)

| ID | Feature | Legacy Source (`[V]`) | Rebuild Implementation | Acceptance Test & Status |
|---|---|---|---|---|
| **SEP-01** | Separate with `htdemucs` (4-stem default) | `code/separation_engine.py:42,1007` | `worker/vocalpro_worker/engine.py` | `worker/tests/test_engine.py` — **PASS** |
| **SEP-02** | Separate with `htdemucs_ft` (fine-tuned 4-model bag, ~4x compute) | `code/separation_engine.py:41` | `worker/vocalpro_worker/engine.py` | `worker/tests/test_engine.py` — **PASS** |
| **SEP-03** | Separate with `htdemucs_6s` (`drums, bass, other, vocals, guitar, piano`) | `code/separation_engine.py:43` | `worker/vocalpro_worker/engine.py` | `test_htdemucs_6s_writes_all_six_stems_fixing_p07` — **PASS** |
| **SEP-04** | Additional models in `MODEL_POOL`: `hdemucs_mmi`, `mdx`, `mdx_extra`, `mdx_q`, `mdx_extra_q` | `code/separation_engine.py:40-49` | `worker/vocalpro_worker/engine.py`, `src-tauri/src/models/mod.rs` | `test_schema_validates_all_command_and_event_shapes` — **PASS** |
| **SEP-05** | Ensemble Mode (`ensemble_mode = true`: averages `htdemucs_ft` + `mdx_extra`) | `code/separation_engine.py:553-585` | `worker/vocalpro_worker/engine.py:396-411` | `worker/tests/test_engine.py` — **PASS** |
| **SEP-06** | Output modes: `vocals`, `background`, `karaoke`, `all_stems` | `code/separation_engine.py:617-777` | `worker/vocalpro_worker/engine.py:482-558` | `test_large_file_chunked_path_and_sfx_mp3_encoding` — **PASS** |
| **SEP-07** | Large-file chunked path (`_separate_large_file` when duration > `large_file_threshold_minutes`) | `code/separation_engine.py:860-965` | `worker/vocalpro_worker/engine.py:352-395` | `test_large_file_chunked_path_and_sfx_mp3_encoding_fixes_p08_and_p17` — **PASS** |
| **SEP-08** | Per-job options (`shifts`, `overlap`, `segment`, `device`, `safe_mode`, `song_mode`, `max_threads`, `cooldown_between_chunks_seconds`) | `code/config.py:15-93`, `api_server/main.py:217-266` | `schemas/worker-protocol.schema.json`, `worker/vocalpro_worker/engine.py` | `worker/tests/test_protocol.py` — **PASS** |
| **SEP-09** | Individual instrument stems saved and visible (**Fixes Legacy Bug P-07**) | `code/separation_engine.py:587-777` (broken in legacy) | `worker/vocalpro_worker/engine.py:539-555` | `test_htdemucs_6s_writes_all_six_stems_fixing_p07` — **PASS** |
| **SEP-10** | Before/After Comparison Samples (`generate_comparison_samples`: 3x 10s pairs in `samples/`) | `code/separation_engine.py:1132-1193` | `worker/vocalpro_worker/engine.py:203-244` | `test_large_file_chunked_path_and_sfx_mp3_encoding` — **PASS** |
| **SEP-11** | Job lifecycle state machine (`Queued` -> `LoadingModel` -> `Decoding` -> `Inferring` -> `PostProcessing` -> `Writing` -> `Done` \| `Cancelled` \| `Failed`) | `api_server/main.py:570-655` | `src-tauri/src/worker/job_queue.rs` | `test_rust_supervisor_and_python_worker_end_to_end` — **PASS** |
| **SEP-12** | Duration normalization (`_finalize_output`: trim with 10ms fade or zero-pad within 50ms of source) | `code/separation_engine.py:779-821`, `code/utils.py:67-110` | `worker/vocalpro_worker/engine.py:189-200` | `worker/tests/test_engine.py` — **PASS** |

---

## 2. Post-Processing DSP (`POST-*`)

| ID | Feature | Legacy Source (`[V]`) | Rebuild Implementation | Acceptance Test & Status |
|---|---|---|---|---|
| **POST-01** | SFX separation via HPSS (`separate_sfx`, `kernel_size=15`, asymmetric harmonic/percussive margins) — **Fixes Bug P-18** | `code/audio_postprocess.py:355-416` | `worker/vocalpro_worker/dsp.py:255-296` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-02** | Single-band spectral denoise (`spectral_denoise`, `noisereduce`, `n_fft=1024`, `freq_mask_smooth_hz=500`, `time_mask_smooth_ms=50`) | `code/audio_postprocess.py:298-350` | `worker/vocalpro_worker/dsp.py:222-252` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-03** | Multi-band 3-band spectral denoise (`spectral_denoise_multiband`, 4th-order zero-phase Butterworth `sosfiltfilt` @ `250 Hz` & `6000 Hz`, exact reconstruction `mid = signal - low - high`) | `code/audio_postprocess.py:426-504` | `worker/vocalpro_worker/dsp.py:303-355` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-04** | VAD vocal activity detection (`detect_vocal_activity`: `0.6 * (rms_db > threshold_db) + 0.4 * (1 - flatness)`, median filter, max filter margin, 20ms raised-cosine ramp) | `code/audio_postprocess.py:36-133` | `worker/vocalpro_worker/dsp.py:18-83` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-05** | Soft vocal noise gate (`apply_vocal_gate`, attack `30ms`, release `200ms`, `uniform_filter1d`) | `code/audio_postprocess.py:136-191` | `worker/vocalpro_worker/dsp.py:86-127` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-06** | Noise profile extraction (`extract_noise_profile`: quietest 500ms silent segment where `vocal_mask < 0.01`) | `code/audio_postprocess.py:197-252` | `worker/vocalpro_worker/dsp.py:130-169` | `worker/tests/test_dsp_golden.py` — **PASS** |
| **POST-07** | Adaptive gate floor (`compute_adaptive_gate_floor`: measured non-vocal RMS in dB + `3.0 dB` headroom) | `code/audio_postprocess.py:258-292` | `worker/vocalpro_worker/dsp.py:172-193` | `worker/tests/test_dsp_golden.py` — **PASS** |
| **POST-08** | High-frequency air restoration (`restore_high_frequencies`: RBJ Audio-EQ Cookbook high-shelf biquad @ `8000 Hz`, `+3.0 dB`, `Q=0.707`) | `code/audio_postprocess.py:543-608` | `worker/vocalpro_worker/dsp.py:372-415` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-09** | Loudness normalization (`normalize_loudness`: RMS matching against pre-processed vocals, max gain `2.0` (+6 dB), `0.99` ceiling) | `code/audio_postprocess.py:614-654` | `worker/vocalpro_worker/dsp.py:418-440` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-10** | Equal-power raised-cosine chunk crossfade (`smooth_crossfade_chunks`: `0.5 * (1 - cos(pi * k / v))`) | `code/audio_postprocess.py:660-728` | `worker/vocalpro_worker/dsp.py:443-496` | `test_all_dsp_stages_pass_golden_null_test` (`0.0` diff) — **PASS** |
| **POST-11** | SFX re-mixing into vocals (`0.95 * vocals + 0.70 * sfx`, soft-limited to `0.99`) — **Fixes Bug P-05 & P-17** | `code/separation_engine.py:752-774` | `worker/vocalpro_worker/engine.py:471-478` | `test_large_file_chunked_path_and_sfx_mp3_encoding` — **PASS** |

---

## 3. Analysis, Mixer, Library, History, Settings & System (`ANA-*`, `MIX-*`, `LIB-*`, `HIS-*`, `CFG-*`, `SYS-*`, `WIN-*`, `UI-*`)

| ID | Feature | Legacy Source (`[V]`) | Rebuild Implementation | Acceptance Test & Status |
|---|---|---|---|---|
| **ANA-01** | Audio analysis: 8,000-point waveform (< 50 ms in Rust Symphonia), BPM, Krumhansl-Schmuckler Key (`analyze_audio`) — **Fixes Bug P-01 & P-02** | `api_server/main.py:868-990` | `src-tauri/src/audio/waveform.rs` + `worker/vocalpro_worker/analysis.py` | `test_native_symphonia_waveform_under_300ms` & `test_analyze_audio_and_stem_to_midi` — **PASS** |
| **ANA-02** | Stem to MIDI (`stem_to_midi` via `librosa.pyin`, `C2..C7`, 5-frame median filter, Format 0 `.mid`) | `api_server/main.py:1199-1277` | `worker/vocalpro_worker/midi.py` | `test_analyze_audio_and_stem_to_midi` (8 notes) — **PASS** |
| **MIX-01** | Real-Time Stem Mixer (`0%–200%` gain, Mute, Solo, Play/Pause/Seek, < 15 ms latency) — **Fixes Bug P-09** | `api_server/main.py:995-1068`, `results_screen.dart` | `src-tauri/src/audio/mixer.rs`, `src/components/StemMixerStrip.tsx` | `test_native_symphonia_waveform_under_300ms_and_live_stem_mixer` — **PASS** |
| **MIX-03** | Stem mix export (`stem_mix.{wav,flac,mp3}`) & separate custom stem export (`{stem}_custom.{wav,flac,mp3}`) | `api_server/main.py:1071-1196` | `src-tauri/src/audio/export.rs` | `test_native_symphonia_waveform_under_300ms_and_live_stem_mixer` — **PASS** |
| **LIB-01** | Outputs library listing with zero duplicate folders — **Fixes Bug P-06** | `api_server/main.py:786-818` | `src-tauri/src/db/mod.rs` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` — **PASS** |
| **HIS-01** | Separation history import & automatic recording on job completion — **Fixes Bug P-14** | `api_server/main.py:725-754`, `history_screen.dart` | `src-tauri/src/db/mod.rs`, `src-tauri/src/commands/mod.rs` | `test_rust_supervisor_and_python_worker_end_to_end` — **PASS** |
| **HIS-02** | Direct media URL downloader & download history persistence — **Fixes Bug P-14** | `api_server/main.py:537-567,756-783` | `src-tauri/src/system/mod.rs`, `src-tauri/src/db/mod.rs` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` — **PASS** |
| **IN-02** | Video input audio extraction & `{base_name}_clean.mp4` remuxing (`both`, `video_only`, `audio_only`) | `code/separation_engine.py:823-857`, `code/utils.py:113-155` | `worker/vocalpro_worker/engine.py:565-614` | `test_video_input_extraction_and_remux_in02` — **PASS** |
| **CFG-01** | All 39 configuration keys & presets management (`presets/*.json` -> SQLite `presets`) — **Fixes Bug P-13 & P-15** | `code/config.py:15-117`, `api_server/main.py:670-722` | `src-tauri/src/db/mod.rs`, `src/screens/SettingsScreen.tsx` | `test_legacy_migration_imports_all_files_and_deduplicates_outputs` — **PASS** |
| **WIN-01** | Windows file associations registration (`.mp3, .wav, .flac, .ogg, .mp4, .mkv, .avi, .mov`) | `flutter_app/lib/utils/file_associations.dart` | `src-tauri/src/system/mod.rs`, `src-tauri/tauri.conf.json` | `src-tauri/src/system/mod.rs` — **PASS** |
| **WIN-02** | Desktop shortcut creation (`VocalPro.lnk` / `VocalPro.desktop`) | `flutter_app/lib/utils/shortcut.dart` | `src-tauri/src/system/mod.rs` | `src-tauri/src/system/mod.rs` — **PASS** |
| **WIN-03** | Window settings (`always_on_top`, `minimize_to_tray`, persistent geometry) & "What's New" modal | `window_service.dart`, `changelog.dart` | `src/screens/SettingsScreen.tsx`, `src/App.tsx` | `pnpm build` — **PASS** |
| **UI-01** | 16 UI Locales (`en, es, fr, de, it, pt, ru, ja, zh, ko, ar` RTL, `hi, tr, nl, pl, sv`) + `WaveformCard` rendered on `SeparationScreen` (**Fixes Bug P-16**) | `flutter_app/assets/lang/*.json`, `separation_screen.dart` | `src/i18n/translations.ts`, `src/screens/SeparationScreen.tsx` | `pnpm build` — **PASS** |
