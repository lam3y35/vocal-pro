use std::fs::File;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};
use zip::write::SimpleFileOptions;
use zip::ZipWriter;

use crate::error::{AppError, AppResult};

pub const SUPPORTED_FILE_ASSOCIATION_EXTS: &[&str] =
    &[".mp3", ".wav", ".flac", ".ogg", ".mp4", ".mkv", ".avi", ".mov"];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangelogRelease {
    pub version: String,
    pub date: String,
    pub highlights: Vec<String>,
}

pub fn register_file_associations(app_data_dir: &Path, exe_path: Option<&Path>) -> AppResult<bool> {
    std::fs::create_dir_all(app_data_dir)?;
    let marker = app_data_dir.join(".associations_registered");

    if cfg!(target_os = "windows") {
        let exe = exe_path
            .map(|p| p.to_path_buf())
            .or_else(|| std::env::current_exe().ok())
            .unwrap_or_else(|| PathBuf::from("vocalpro.exe"));
        let exe_str = exe.to_string_lossy();
        let prog_id = "VocalPro.AudioFile";

        let _ = Command::new("reg")
            .args([
                "add",
                &format!("HKCU\\Software\\Classes\\{}", prog_id),
                "/ve",
                "/d",
                "VocalPro Media File",
                "/f",
            ])
            .status();

        let _ = Command::new("reg")
            .args([
                "add",
                &format!(
                    "HKCU\\Software\\Classes\\{}\\shell\\open\\command",
                    prog_id
                ),
                "/ve",
                "/d",
                &format!("\"{}\" \"%1\"", exe_str),
                "/f",
            ])
            .status();

        for ext in SUPPORTED_FILE_ASSOCIATION_EXTS {
            let _ = Command::new("reg")
                .args([
                    "add",
                    &format!("HKCU\\Software\\Classes\\{}", ext),
                    "/ve",
                    "/d",
                    prog_id,
                    "/f",
                ])
                .status();
        }
    }

    std::fs::write(&marker, "registered=true\n")?;
    Ok(true)
}

pub fn create_desktop_shortcut(app_data_dir: &Path, exe_path: Option<&Path>) -> AppResult<PathBuf> {
    std::fs::create_dir_all(app_data_dir)?;
    let marker = app_data_dir.join(".shortcut_created");
    let exe = exe_path
        .map(|p| p.to_path_buf())
        .or_else(|| std::env::current_exe().ok())
        .unwrap_or_else(|| PathBuf::from("vocalpro"));

    let desktop_dir = dirs::desktop_dir().unwrap_or_else(|| app_data_dir.to_path_buf());
    std::fs::create_dir_all(&desktop_dir)?;

    let shortcut_path = if cfg!(target_os = "windows") {
        let lnk = desktop_dir.join("VocalPro.lnk");
        let ps_script = format!(
            "$s=(New-Object -COM WScript.Shell).CreateShortcut('{}');$s.TargetPath='{}';$s.Save()",
            lnk.to_string_lossy(),
            exe.to_string_lossy()
        );
        let _ = Command::new("powershell")
            .args(["-NoProfile", "-Command", &ps_script])
            .status();
        lnk
    } else {
        let desktop_file = desktop_dir.join("VocalPro.desktop");
        let content = format!(
            "[Desktop Entry]\nType=Application\nName=VocalPro\nExec=\"{}\" %F\nIcon=vocalpro\nTerminal=false\nCategories=AudioVideo;Audio;\n",
            exe.to_string_lossy()
        );
        std::fs::write(&desktop_file, content)?;
        desktop_file
    };

    std::fs::write(&marker, "shortcut_created=true\n")?;
    Ok(shortcut_path)
}

pub fn download_media_url(url: &str, uploads_dir: &Path) -> AppResult<(String, PathBuf, String)> {
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err(AppError::InvalidInput(
            "URL must start with http:// or https://".to_string(),
        ));
    }
    std::fs::create_dir_all(uploads_dir)?;

    let raw_name = url
        .split('?')
        .next()
        .and_then(|u| u.rsplit('/').next())
        .filter(|s| !s.is_empty())
        .unwrap_or("downloaded_media.mp3");

    let safe_name: String = raw_name
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '.' || c == '_' || c == '-' {
                c
            } else {
                '_'
            }
        })
        .collect();

    let final_name = if safe_name.contains('.') {
        safe_name
    } else {
        format!("{}.mp3", safe_name)
    };
    let dest_path = uploads_dir.join(&final_name);

    let status = Command::new("curl")
        .args(["-L", "-s", "-f", "-o", &dest_path.to_string_lossy(), url])
        .status()
        .map_err(|e| AppError::System(format!("Failed to invoke curl: {}", e)))?;

    if !status.success() || !dest_path.is_file() {
        return Err(AppError::System(format!("Failed to download URL: {}", url)));
    }

    let ext = dest_path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("mp3")
        .to_uppercase();

    Ok((final_name, dest_path, ext))
}

pub fn export_diagnostic_bundle(
    target_zip: &Path,
    worker_logs: &[String],
    settings_json: &str,
    health_json: &str,
) -> AppResult<PathBuf> {
    if let Some(parent) = target_zip.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let file = File::create(target_zip)?;
    let mut zip = ZipWriter::new(file);
    let opts = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);

    zip.start_file("worker_logs.txt", opts)
        .map_err(|e| AppError::System(e.to_string()))?;
    zip.write_all(worker_logs.join("\n").as_bytes())?;

    zip.start_file("settings.json", opts)
        .map_err(|e| AppError::System(e.to_string()))?;
    zip.write_all(settings_json.as_bytes())?;

    zip.start_file("worker_health.json", opts)
        .map_err(|e| AppError::System(e.to_string()))?;
    zip.write_all(health_json.as_bytes())?;

    zip.finish().map_err(|e| AppError::System(e.to_string()))?;
    Ok(target_zip.to_path_buf())
}

pub fn get_changelog_releases() -> Vec<ChangelogRelease> {
    vec![
        ChangelogRelease {
            version: "3.0.0".to_string(),
            date: "2026-11-07".to_string(),
            highlights: vec![
                "Native Rust + Tauri v2 + React 19 architecture with zero localhost HTTP/WebSocket ports".to_string(),
                "Real per-segment Demucs progress and <500ms cooperative job cancellation".to_string(),
                "Real-time lock-free Rust multi-stem mixer with <15ms fader latency".to_string(),
                "All 6 stems saved for htdemucs_6s and output_all_stems (fixes P-07)".to_string(),
                "SQLite WAL database with automatic v1/v2 config and history migration".to_string(),
            ],
        },
        ChangelogRelease {
            version: "2.3.0".to_string(),
            date: "2026-03-01".to_string(),
            highlights: vec![
                "Multi-band spectral denoise, adaptive gate floor, and high-frequency restore".to_string(),
                "Stem-to-MIDI pitch extraction and 16-language UI localization".to_string(),
            ],
        },
    ]
}
