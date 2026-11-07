PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    input_path TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    model TEXT NOT NULL,
    output_mode TEXT NOT NULL,
    options_json TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    elapsed_s REAL
);

CREATE TABLE IF NOT EXISTS outputs (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    folder_name TEXT NOT NULL,
    folder_path TEXT NOT NULL UNIQUE,
    source_filename TEXT NOT NULL,
    model TEXT NOT NULL,
    stems_json TEXT NOT NULL,
    bpm REAL,
    musical_key TEXT,
    musical_scale TEXT,
    duration_s REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS separation_history (
    id TEXT PRIMARY KEY,
    files_json TEXT NOT NULL,
    model TEXT NOT NULL,
    device TEXT NOT NULL,
    status TEXT NOT NULL,
    date TEXT NOT NULL,
    elapsed TEXT NOT NULL,
    output_dir TEXT
);

CREATE TABLE IF NOT EXISTS download_history (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    output_path TEXT NOT NULL,
    format TEXT NOT NULL,
    quality TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS presets (
    name TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outputs_created ON outputs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sep_history_date ON separation_history(date DESC);
CREATE INDEX IF NOT EXISTS idx_downloads_created ON download_history(created_at DESC);
