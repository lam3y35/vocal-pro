# VocalPro v3.0.0 — Blind A/B Listening Evaluation Pack

Per **Workstream B (Audio Quality Verification)** of the Verification & Hardening Pass Mandate, this directory contains neutral blind A/B vocal stems separated using the **real pretrained `htdemucs` (83.6 MB) model** on 5 diverse test tracks comparing the legacy VocalPro v2 pipeline (`code/separation_engine.py` + `code/audio_postprocess.py`) against the rebuilt VocalPro v3 pipeline (`worker/vocalpro_worker/engine.py` + `worker/vocalpro_worker/dsp.py`).

To prevent expectation bias during listening, `candidate_A_vocals.wav` and `candidate_B_vocals.wav` are randomly assigned per track using a deterministic PRNG seed (`20261107`). The sealed mapping is stored in `blind_ab_key.json` (do not open `blind_ab_key.json` until after completing the listening table below).

---

## 1. Track Manifest & Licensing

All 5 tracks are generated deterministically by `benchmarks/generate_reference_set.py` (CC0 Public Domain / MIT) so they can be committed to git without copyright restrictions:

| Track Folder | Source Track | Sample Rate / Channels | Musical & Acoustic Characteristics |
|---|---|---|---|
| `track_01/` | `track_01_pop_stereo_44k.wav` | 44.1 kHz Stereo | 220 Hz vibrato lead vocal + 5 harmonics + 55 Hz bass + 120 BPM drum transients + -45 dBFS room floor |
| `track_02/` | `track_02_mono_48k.wav` | 48.0 kHz Mono (resampled to 44.1 kHz Stereo) | 330 Hz vocal melody + 110 Hz bass harmonic |
| `track_03/` | `track_03_quiet_dynamic.wav` | 44.1 kHz Stereo | Low-level `-30 dBFS` dynamic range test |
| `track_04/` | `track_04_clipped_hot.wav` | 44.1 kHz Stereo | Hard-clipped `0.0 dBFS` master limiter test |
| `track_05/` | `track_05_silence_edges.wav` | 44.1 kHz Stereo | Alternating silence & vocal phrases (VAD gate attack/release & noise floor test) |

---

## 2. Blind A/B Listening Scorecard (For Moaz / "Lam3y" to Fill In)

Listen to `candidate_A_vocals.wav` and `candidate_B_vocals.wav` in each subfolder using studio headphones or monitors, then fill in your preference and observations before checking `blind_ab_key.json`:

| Track ID | Candidate A File | Candidate B File | Preferred (`A` / `B` / `Identical`) | Vocal Clarity (1–5) | Bleed / Artifact Suppression (1–5) | Gate Tails & Silence Floor Notes |
|---|---|---|---|---|---|---|
| `track_01` | `track_01/candidate_A_vocals.wav` | `track_01/candidate_B_vocals.wav` | `[ ] A  [ ] B  [ ] Tie` | `___ / 5` | `___ / 5` | |
| `track_02` | `track_02/candidate_A_vocals.wav` | `track_02/candidate_B_vocals.wav` | `[ ] A  [ ] B  [ ] Tie` | `___ / 5` | `___ / 5` | |
| `track_03` | `track_03/candidate_A_vocals.wav` | `track_03/candidate_B_vocals.wav` | `[ ] A  [ ] B  [ ] Tie` | `___ / 5` | `___ / 5` | |
| `track_04` | `track_04/candidate_A_vocals.wav` | `track_04/candidate_B_vocals.wav` | `[ ] A  [ ] B  [ ] Tie` | `___ / 5` | `___ / 5` | |
| `track_05` | `track_05/candidate_A_vocals.wav` | `track_05/candidate_B_vocals.wav` | `[ ] A  [ ] B  [ ] Tie` | `___ / 5` | `___ / 5` | |

**Final Owner Sign-Off:** `[ ] Approved for Release   [ ] Hold — See Notes Above`
