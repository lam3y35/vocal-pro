# VocalPro v3.0.0 — Blind A/B Listening Evaluation Pack

Per **Workstream B (Audio Quality Verification)** of the Verification & Hardening Pass Mandate, this directory contains neutral blind A/B vocal stems separated using the **real pretrained `htdemucs` (83.6 MB) model** on 5 diverse test tracks comparing the legacy VocalPro v2 pipeline (`code/separation_engine.py` + `code/audio_postprocess.py`) against the rebuilt VocalPro v3 pipeline (`worker/vocalpro_worker/engine.py` + `worker/vocalpro_worker/dsp.py`).

To prevent expectation bias during listening, `candidate_A_vocals.wav` and `candidate_B_vocals.wav` are randomly assigned per track using a deterministic PRNG seed (`20261107`). The sealed mapping is stored in `blind_ab_key.json` (do not open `blind_ab_key.json` until after completing the listening table below).

---

## 1. Track Manifest & Licensing

All 5 tracks are real music recordings sourced from Wikimedia Commons under Creative Commons / Public Domain licenses (manifest details in `benchmarks/reference-real/MANIFEST.json` and `docs/licenses/THIRD_PARTY.md`):

| Track Folder | Title & Artist | License | Format & Excerpt | Musical & Acoustic Characteristics |
|---|---|---|---|---|
| `track_01/` | *The Shelby Blues* — David Mumford | CC BY 4.0 | 44.1 kHz Stereo, 30s excerpt (20s–50s) | Blues vocal + acoustic guitar band; warm vocal lead, dynamic picking transients |
| `track_02/` | *The Vistas Missing Views* — The Rope River Blues Band | CC BY 3.0 US | 44.1 kHz Stereo, 30s excerpt (40s–70s) | Rock/blues band; aggressive electric guitar, drums, upfront male vocal |
| `track_03/` | *Rainy weather blues* — Bessie Smith (1920s) | Public domain | 48.0 kHz Mono (resampled to 44.1k Stereo), 30s excerpt (20s–50s) | Historic 1920s shellac recording; shellac surface noise floor, high-dynamic vintage vocal |
| `track_04/` | *Skyscrapers* — Airmen of Note (US Air Force Band) | Public domain | 44.1 kHz Stereo, 30s excerpt (30s–60s) | Dense big-band jazz orchestra; powerful brass section, complex harmonic overlap |
| `track_05/` | *Friendly Evil Gangsta Synth Hip Hop* — Mesostic | CC0 Public Domain | 44.1 kHz Stereo, 30s excerpt (20s–50s) | Electronic synth hip-hop; sub-bass 808s, synthetic punch drums, hard vocal/lead lines |

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
