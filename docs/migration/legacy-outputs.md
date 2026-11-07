# Legacy Output Tree & File Naming Specification

**Status:** `[V]` Verified against `code/separation_engine.py`, `api_server/main.py`, and `code/utils.py` in `lam3y35/vocal-pro`.

---

## 1. Root Output Directory Layout

By default (`output_dir` not overridden in request):
- **Output root:** `<input_file_parent_dir>/output_vocals/<base_name>/`
  - Where `<base_name> = os.path.splitext(os.path.basename(input_path))[0]` (`code/separation_engine.py:423-427`).
- When `output_dir` is explicitly provided in `SeparationRequest`:
  - **Output root:** `<output_dir>/<base_name>/` (`code/separation_engine.py:425`).

---

## 2. Separation Job Output Files (`code/separation_engine.py:587-835`)

Inside `<output_root>/<base_name>/`:

| Output Mode / Setting | Filename Pattern | Format / Codec / Sample Rate | Source (`file:line`) | Notes & Verified Bugs |
|---|---|---|---|---|
| **Primary Vocals** (always produced) | `<base_name>_vocals.<ext>` | `.wav` (`PCM_16`, `44100 Hz`), `.flac` (`44100 Hz`), or `.mp3` (`libmp3lame`, `audio_bitrate` default `320k`) | `separation_engine.py:617,720-738` | Post-processed with VAD gate, spectral denoise, high-frequency restore, loudness normalization (-16 dBFS RMS), and optional SFX re-mix (`0.95 * vocals + 0.70 * sfx`). |
| **Karaoke / Instrumental** (`karaoke_mode = true`) | `<base_name>_karaoke.wav` | `.wav` (`PCM_16`, `44100 Hz`) | `separation_engine.py:663-664` | Always `.wav` in legacy code (`drums + bass + other [+ guitar + piano]`, normalized if peak > 1.0). |
| **Background Music** (`save_background_track = true` or `enable_sfx_separation = true`) | `<base_name>_background.wav` | `.wav` (`PCM_16`, `44100 Hz`) | `separation_engine.py:687-688,718` | Sum of non-vocal stems (`drums + bass + other...`). If `enable_sfx_separation = true`, replaced by HPSS harmonic component (`music_harmonic`). |
| **Individual Instrument Stems** (`output_all_stems = true` or `htdemucs_6s`) | `<base_name>_drums.<ext>`<br>`<base_name>_bass.<ext>`<br>`<base_name>_other.<ext>`<br>`<base_name>_guitar.<ext>` (6s)<br>`<base_name>_piano.<ext>` (6s) | Same `<ext>` as `output_format` (`.wav`, `.mp3`, `.flac`), `44100 Hz` | `separation_engine.py:587-777` (**Bug P-07 `[V]`**) | **Legacy bug P-07:** `_run_demucs_on_file` computes all stems in `raw_stems`, and `config.py:24` defines `"output_all_stems": False`, plus `ResultsScreen` / `GET /api/outputs/{folder}/stems` searches for `vocals, drums, bass, guitar, piano, other, instrumental, karaoke, background`. However, `_postprocess_and_save` never writes `drums`, `bass`, `guitar`, `piano`, or `other` to disk! **Rebuild fix (SEP-09):** Always save all model stems when `output_all_stems=true` or `htdemucs_6s` is used (and optionally by default so Stem Mixer always has all 4 or 6 stems). |
| **Video Remux** (when input is video `.mp4/.mkv/.avi/.mov/.webm/.flv/.wmv` and `video_output_mode` is `"both"` or `"video_only"`) | `<base_name>_clean.mp4` | Video stream copied (`-c:v copy`), audio stream `aac` (`-b:a <audio_bitrate>`, default `320k`), `-movflags +faststart` if `ffmpeg_faststart=true`, `-shortest` | `separation_engine.py:823-857`, `utils.py:113-155` | When `video_output_mode == "video_only"`, `<base_name>_vocals.<ext>` is deleted after muxing (`separation_engine.py:833-835`). |
| **Comparison Samples** (`generate_comparison_samples = true`) | `samples/sample_1_music.wav`<br>`samples/sample_1_no_music.wav`<br>`samples/sample_2_music.wav`<br>`samples/sample_2_no_music.wav`<br>`samples/sample_3_music.wav`<br>`samples/sample_3_no_music.wav` | `.wav` (`PCM_16`, `44100 Hz`), up to 3 segments of `10.0s` each | `separation_engine.py:1132-1193` | Picks up to 3 regions where background music RMS is highest (`hop = 5s`, `sample_duration = 10s`) and saves original vs. isolated vocals clips. |

---

## 3. Stem Mixer & MIDI Export Files (`api_server/main.py:995-1277`)

Inside `<output_root>/<folder_name>/`:

| Endpoint / Action | Filename Pattern | Format / Details | Source (`file:line`) |
|---|---|---|---|
| **Stem Preview** (`POST /api/outputs/{folder}/stem_preview`) | In-memory `stem_preview.wav` (streamed in legacy; live `cpal` mixer in rebuild) | `44100 Hz` `PCM_16` WAV | `api_server/main.py:995-1068` |
| **Export Mixed Audio** (`POST /api/outputs/{folder}/stem_export`) | `stem_mix.<ext>` (where `<ext>` is `wav`, `mp3`, or `flac`) | Mixed sum of stems weighted by `volumes: Record<string, float>` (`0.0` to `2.0`), soft-normalized if peak > `0.99` (`mixed = mixed / peak * 0.99`). MP3 uses `-b:a <bitrate>` (`128k`, `192k`, `256k`, `320k`). | `api_server/main.py:1071-1142` |
| **Export Adjusted Stems Separately** (`POST /api/outputs/{folder}/stem_export_separate`) | `<stem_base>_custom.<ext>` (e.g. `<base_name>_vocals_custom.wav`) | Each stem with `vol > 0.0` scaled by `vol`, peak-limited if `peak > 0.99`, encoded to `wav`, `mp3`, or `flac`. | `api_server/main.py:1145-1196` |
| **Stem to MIDI** (`POST /api/outputs/{folder}/stem_to_midi`) | `<stem_base>.mid` (e.g. `<base_name>_vocals.mid`) | Standard MIDI File (Format 0, 1 track, 480 ticks/beat, 120 BPM = `500000` us/beat) generated from `librosa.pyin(fmin=C2, fmax=C7, sr=22050, hop_length=512)` with median filter (`kernel_size=5`) and min note duration `3` frames (`~69.7 ms`). | `api_server/main.py:1199-1277` |

---

## 4. Stem Discovery Heuristic (`api_server/main.py:820-865`)

When scanning an output folder `<folder_name>` for stems:
1. Exclude files starting with `stem_mix` or `stem_preview`, or ending with `_custom.<ext>`.
2. Only include files ending with `.wav`, `.mp3`, or `.flac`.
3. Match stem name by checking if `<stem>` (`vocals`, `drums`, `bass`, `guitar`, `piano`, `other`, `instrumental`, `karaoke`, `background`) appears in `filename.lower()`, otherwise fallback to `os.path.splitext(filename)[0]`.
