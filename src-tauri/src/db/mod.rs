pub mod migration;

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::error::AppResult;
use crate::worker::protocol::StemOutput;

const MIGRATIONS_SQL: &str = include_str!("migrations.sql");

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputFolderEntry {
    pub id: String,
    pub folder_name: String,
    pub folder_path: String,
    pub source_filename: String,
    pub model: String,
    pub stems: Vec<StemOutput>,
    pub bpm: Option<f64>,
    pub musical_key: Option<String>,
    pub musical_scale: Option<String>,
    pub duration_s: Option<f64>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeparationHistoryEntry {
    pub id: String,
    pub files: Vec<String>,
    pub model: String,
    pub device: String,
    pub status: String,
    pub date: String,
    pub elapsed: String,
    pub output_dir: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadHistoryEntry {
    pub id: String,
    pub title: String,
    pub url: String,
    pub path: String,
    pub format: String,
    pub quality: String,
    pub date: String,
}

#[derive(Clone)]
pub struct AppDatabase {
    conn: Arc<Mutex<Connection>>,
    pub db_path: PathBuf,
}

pub fn default_config_map() -> serde_json::Map<String, Value> {
    let v = json!({
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
        "auto_preview": false,
        "locale": "en",
        "always_on_top": false,
        "minimize_to_tray": false
    });
    v.as_object().unwrap().clone()
}

impl AppDatabase {
    pub fn open(db_path: &Path) -> AppResult<Self> {
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(db_path)?;
        conn.execute_batch(MIGRATIONS_SQL)?;
        let db = Self {
            conn: Arc::new(Mutex::new(conn)),
            db_path: db_path.to_path_buf(),
        };
        db.seed_defaults_if_missing()?;
        Ok(db)
    }

    fn seed_defaults_if_missing(&self) -> AppResult<()> {
        let now = chrono::Utc::now().to_rfc3339();
        let defaults = default_config_map();
        let conn = self.conn.lock().unwrap();
        for (k, v) in defaults {
            let val_str = serde_json::to_string(&v)?;
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value_json, updated_at) VALUES (?1, ?2, ?3)",
                params![k, val_str, now],
            )?;
        }
        Ok(())
    }

    pub fn migrate_legacy(
        &self,
        app_data_dir: &Path,
        extra_config_paths: &[PathBuf],
        output_scan_roots: &[PathBuf],
    ) -> AppResult<migration::MigrationReport> {
        let conn = self.conn.lock().unwrap();
        migration::run_legacy_migration(&conn, app_data_dir, extra_config_paths, output_scan_roots)
    }

    pub fn get_all_settings(&self) -> AppResult<HashMap<String, Value>> {
        let mut map: HashMap<String, Value> = default_config_map().into_iter().collect();
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT key, value_json FROM settings")?;
        let rows = stmt.query_map([], |row| {
            let k: String = row.get(0)?;
            let v_str: String = row.get(1)?;
            Ok((k, v_str))
        })?;
        for r in rows {
            let (k, v_str) = r?;
            if let Ok(val) = serde_json::from_str::<Value>(&v_str) {
                map.insert(k, val);
            }
        }
        Ok(map)
    }

    pub fn update_settings(&self, updates: &HashMap<String, Value>) -> AppResult<()> {
        let now = chrono::Utc::now().to_rfc3339();
        let conn = self.conn.lock().unwrap();
        for (k, v) in updates {
            let v_str = serde_json::to_string(v)?;
            conn.execute(
                "INSERT INTO settings (key, value_json, updated_at) VALUES (?1, ?2, ?3)
                 ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at",
                params![k, v_str, now],
            )?;
        }
        Ok(())
    }

    pub fn reset_settings_to_default(&self) -> AppResult<HashMap<String, Value>> {
        let now = chrono::Utc::now().to_rfc3339();
        let defaults = default_config_map();
        {
            let conn = self.conn.lock().unwrap();
            conn.execute("DELETE FROM settings", [])?;
            for (k, v) in &defaults {
                let v_str = serde_json::to_string(v)?;
                conn.execute(
                    "INSERT INTO settings (key, value_json, updated_at) VALUES (?1, ?2, ?3)",
                    params![k, v_str, now],
                )?;
            }
        }
        Ok(defaults.into_iter().collect())
    }

    pub fn record_output_folder(
        &self,
        job_id: Option<&str>,
        folder_name: &str,
        folder_path: &str,
        source_filename: &str,
        model: &str,
        stems: &[StemOutput],
        duration_s: Option<f64>,
    ) -> AppResult<()> {
        let now = chrono::Utc::now().to_rfc3339();
        let id = uuid::Uuid::new_v4().to_string();
        let stems_json = serde_json::to_string(stems)?;
        let conn = self.conn.lock().unwrap();
        if let Some(jid) = job_id {
            conn.execute(
                "INSERT OR IGNORE INTO jobs (id, input_path, output_dir, model, output_mode, options_json, status, created_at, finished_at)
                 VALUES (?1, ?2, ?3, ?4, 'vocals', '{}', 'done', ?5, ?5)",
                params![jid, source_filename, folder_path, model, now],
            )?;
        }
        conn.execute(
            "INSERT INTO outputs (id, job_id, folder_name, folder_path, source_filename, model, stems_json, duration_s, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
             ON CONFLICT(folder_path) DO UPDATE SET
                stems_json = excluded.stems_json,
                model = excluded.model,
                duration_s = excluded.duration_s,
                created_at = excluded.created_at",
            params![id, job_id, folder_name, folder_path, source_filename, model, stems_json, duration_s, now],
        )?;
        Ok(())
    }

    pub fn update_output_analysis(
        &self,
        folder_path: &str,
        bpm: f64,
        musical_key: &str,
        musical_scale: &str,
        duration_s: f64,
    ) -> AppResult<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "UPDATE outputs SET bpm = ?1, musical_key = ?2, musical_scale = ?3, duration_s = ?4 WHERE folder_path = ?5",
            params![bpm, musical_key, musical_scale, duration_s, folder_path],
        )?;
        Ok(())
    }

    pub fn list_outputs(&self) -> AppResult<Vec<OutputFolderEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, folder_name, folder_path, source_filename, model, stems_json, bpm, musical_key, musical_scale, duration_s, created_at
             FROM outputs ORDER BY created_at DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            let stems_str: String = row.get(5)?;
            let stems: Vec<StemOutput> = serde_json::from_str(&stems_str).unwrap_or_default();
            Ok(OutputFolderEntry {
                id: row.get(0)?,
                folder_name: row.get(1)?,
                folder_path: row.get(2)?,
                source_filename: row.get(3)?,
                model: row.get(4)?,
                stems,
                bpm: row.get(6)?,
                musical_key: row.get(7)?,
                musical_scale: row.get(8)?,
                duration_s: row.get(9)?,
                created_at: row.get(10)?,
            })
        })?;
        let mut list = Vec::new();
        for r in rows {
            list.push(r?);
        }
        Ok(list)
    }

    pub fn record_separation_history(
        &self,
        files: &[String],
        model: &str,
        device: &str,
        status: &str,
        elapsed_s: f64,
        output_dir: Option<&str>,
    ) -> AppResult<()> {
        let id = uuid::Uuid::new_v4().to_string();
        let files_json = serde_json::to_string(files)?;
        let date = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let elapsed = format!("{:.1}s", elapsed_s);
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO separation_history (id, files_json, model, device, status, date, elapsed, output_dir)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![id, files_json, model, device, status, date, elapsed, output_dir],
        )?;
        Ok(())
    }

    pub fn list_separation_history(&self) -> AppResult<Vec<SeparationHistoryEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, files_json, model, device, status, date, elapsed, output_dir
             FROM separation_history ORDER BY date DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            let f_str: String = row.get(1)?;
            let files: Vec<String> = serde_json::from_str(&f_str).unwrap_or_default();
            Ok(SeparationHistoryEntry {
                id: row.get(0)?,
                files,
                model: row.get(2)?,
                device: row.get(3)?,
                status: row.get(4)?,
                date: row.get(5)?,
                elapsed: row.get(6)?,
                output_dir: row.get(7)?,
            })
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    }

    pub fn clear_separation_history(&self) -> AppResult<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM separation_history", [])?;
        Ok(())
    }

    pub fn record_download_history(
        &self,
        title: &str,
        url: &str,
        output_path: &str,
        format: &str,
        quality: &str,
    ) -> AppResult<()> {
        let id = uuid::Uuid::new_v4().to_string();
        let date = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S").to_string();
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO download_history (id, title, url, output_path, format, quality, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![id, title, url, output_path, format, quality, date],
        )?;
        Ok(())
    }

    pub fn list_download_history(&self) -> AppResult<Vec<DownloadHistoryEntry>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, title, url, output_path, format, quality, created_at
             FROM download_history ORDER BY created_at DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(DownloadHistoryEntry {
                id: row.get(0)?,
                title: row.get(1)?,
                url: row.get(2)?,
                path: row.get(3)?,
                format: row.get(4)?,
                quality: row.get(5)?,
                date: row.get(6)?,
            })
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    }

    pub fn clear_download_history(&self) -> AppResult<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM download_history", [])?;
        Ok(())
    }

    pub fn list_presets(&self) -> AppResult<Vec<(String, Value)>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare("SELECT name, config_json FROM presets ORDER BY name ASC")?;
        let rows = stmt.query_map([], |row| {
            let name: String = row.get(0)?;
            let cfg_str: String = row.get(1)?;
            let val: Value = serde_json::from_str(&cfg_str).unwrap_or(Value::Null);
            Ok((name, val))
        })?;
        let mut out = Vec::new();
        for r in rows {
            out.push(r?);
        }
        Ok(out)
    }

    pub fn save_preset(&self, name: &str, config: &Value) -> AppResult<()> {
        let now = chrono::Utc::now().to_rfc3339();
        let cfg_str = serde_json::to_string(config)?;
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO presets (name, config_json, updated_at) VALUES (?1, ?2, ?3)
             ON CONFLICT(name) DO UPDATE SET config_json = excluded.config_json, updated_at = excluded.updated_at",
            params![name, cfg_str, now],
        )?;
        Ok(())
    }

    pub fn delete_preset(&self, name: &str) -> AppResult<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM presets WHERE name = ?1", params![name])?;
        Ok(())
    }
}
