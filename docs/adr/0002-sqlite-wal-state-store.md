# ADR-0002: Replace Raw JSON Files with SQLite WAL Database and Automatic Legacy Migration

- **Status:** Accepted (`[V]`)
- **Date:** 2026-11-07
- **Fixes:** `P-06`, `P-13`, `P-14`, `P-15`

## Context
In the legacy application:
1. Configuration and history were scattered across multiple unlocked JSON files:
   - `~/.vocalpro_config.json` (and `~/.vocal_remover_pro_config.json`) (`code/config.py:120-121`)
   - `%APPDATA%/VocalPro/separation_history.json` (`code/_shared.py:30`)
   - `%APPDATA%/VocalPro/download_history.json` (`code/_shared.py:29`)
   - `%APPDATA%/VocalPro/window_settings.json` (`window_service.dart:11`)
   - `%APPDATA%/VocalPro/flutter_settings.json` (`locale_provider.dart:24`)
2. **Bug `P-14 [V]`:** `api_server/main.py` read and deleted `separation_history.json` and `download_history.json`, but **never wrote new entries** to either file when jobs or downloads completed!
3. **Bug `P-06 [V]`:** `GET /api/outputs` (`api_server/main.py:806-814`) appended the folder object *inside* the `for f in os.listdir(entry_path):` loop, duplicating each output folder once per file inside it.

## Decision
1. Store all persistent state in `%APPDATA%/VocalPro/vocalpro.db` (or `$XDG_DATA_HOME/VocalPro/vocalpro.db` on Linux) using SQLite with `PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL; PRAGMA foreign_keys = ON;`.
2. Tables: `schema_version`, `settings`, `jobs`, `outputs`, `separation_history`, `download_history`, `presets`.
3. On first startup (`migration.rs`):
   - Back up legacy JSON files to `%APPDATA%/VocalPro/backup-v1-<timestamp>/` without modifying originals.
   - Import settings from `~/.vocalpro_config.json`, `~/.vocal_remover_pro_config.json`, `%APPDATA%/VocalPro/config.json`, `window_settings.json`, and `flutter_settings.json`.
   - Import `separation_history.json` and `download_history.json`.
   - Scan existing output folders (`output_vocals/` and custom output dirs) and index each unique output folder and its stems into `outputs` (eliminating `P-06`).
4. Automatically insert rows into `separation_history` and `outputs` on job completion, and into `download_history` on URL download completion (fixing `P-14`).

## Consequences
- Atomic, crash-safe transactions; zero JSON corruption under concurrent access.
- Instantaneous library/history queries and zero duplicate entries in `/api/outputs`.
