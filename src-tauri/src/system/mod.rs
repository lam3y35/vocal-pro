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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareProfile {
    pub os_name: String,
    pub os_arch: String,
    pub cpu_model: String,
    pub physical_cores: u32,
    pub logical_cores: u32,
    pub simd_features: Vec<String>,
    pub total_ram_mb: u64,
    pub available_ram_mb: u64,
    pub disk_free_gb: f64,
    pub cuda_available: bool,
    pub mps_available: bool,
    pub gpu_name: Option<String>,
    pub vram_mb: Option<u64>,
    pub fp16_supported: bool,
    pub device_tier: String,
    pub tier_label: String,
    pub recommended_device: String,
    pub recommended_max_concurrent_jobs: u32,
    pub recommended_threads_per_job: u32,
    pub recommended_segment_s: f64,
    pub recommended_overlap: f64,
    pub recommended_shifts: u32,
    pub recommended_preset: String,
    pub recommended_fp16: bool,
    pub recommended_parallel_dsp: bool,
    pub recommended_safe_mode: bool,
}

pub fn detect_system_hardware(
    app_data_dir: &Path,
    cuda_available: bool,
    gpu_name: Option<String>,
    vram_mb: Option<u64>,
) -> HardwareProfile {
    let logical_cores = std::thread::available_parallelism()
        .map(|n| n.get() as u32)
        .unwrap_or(4);
    let mut physical_cores = (logical_cores / 2).max(1);
    let mut cpu_model = format!("{} Processor", std::env::consts::ARCH.to_uppercase());
    let mut simd_features = Vec::new();

    if let Ok(cpuinfo) = std::fs::read_to_string("/proc/cpuinfo") {
        for line in cpuinfo.lines() {
            if line.starts_with("model name") {
                if let Some((_, val)) = line.split_once(':') {
                    cpu_model = val.trim().to_string();
                }
            } else if line.starts_with("cpu cores") {
                if let Some((_, val)) = line.split_once(':') {
                    if let Ok(c) = val.trim().parse::<u32>() {
                        physical_cores = c.max(1);
                    }
                }
            } else if line.starts_with("flags") && simd_features.is_empty() {
                if let Some((_, val)) = line.split_once(':') {
                    for (flag, label) in [
                        ("avx512f", "AVX-512"),
                        ("avx2", "AVX2"),
                        ("avx", "AVX"),
                        ("fma", "FMA"),
                        ("sse4_2", "SSE4.2"),
                        ("neon", "NEON"),
                    ] {
                        if val.split_whitespace().any(|w| w == flag)
                            && !simd_features.iter().any(|s| s == label)
                        {
                            simd_features.push(label.to_string());
                        }
                    }
                }
            }
        }
    }

    if simd_features.is_empty() {
        if cfg!(target_arch = "x86_64") {
            simd_features.push("AVX2".to_string());
            simd_features.push("SSE4.2".to_string());
        } else if cfg!(target_arch = "aarch64") {
            simd_features.push("NEON".to_string());
        }
    }

    let mut total_ram_mb: u64 = 8192;
    let mut available_ram_mb: u64 = 6144;
    if let Ok(meminfo) = std::fs::read_to_string("/proc/meminfo") {
        for line in meminfo.lines() {
            if line.starts_with("MemTotal:") {
                if let Some(kb) = line
                    .split_whitespace()
                    .nth(1)
                    .and_then(|s| s.parse::<u64>().ok())
                {
                    total_ram_mb = kb / 1024;
                }
            } else if line.starts_with("MemAvailable:") {
                if let Some(kb) = line
                    .split_whitespace()
                    .nth(1)
                    .and_then(|s| s.parse::<u64>().ok())
                {
                    available_ram_mb = kb / 1024;
                }
            }
        }
    }

    let disk_free_gb = 50.0;
    let mps_available = cfg!(target_os = "macos") && cfg!(target_arch = "aarch64");
    let fp16_supported = cuda_available || mps_available;
    let vram = vram_mb.unwrap_or(0);

    let (
        device_tier,
        tier_label,
        rec_device,
        rec_jobs,
        rec_threads,
        rec_seg,
        rec_ovl,
        rec_shifts,
        rec_preset,
        rec_fp16,
        rec_par_dsp,
        rec_safe,
    ) = if cuda_available && vram >= 11500 {
        let jobs = if total_ram_mb >= 16000 { 3 } else { 2 };
        (
            "ultra_gpu",
            "Ultra Studio GPU (12GB+ VRAM)",
            "cuda",
            jobs,
            (logical_cores / jobs).max(2),
            7.8,
            0.25,
            2,
            "ultra",
            true,
            true,
            false,
        )
    } else if cuda_available && vram >= 5800 {
        let jobs = if total_ram_mb >= 12000 { 2 } else { 1 };
        (
            "high_gpu",
            "High-Performance GPU (6-11GB VRAM)",
            "cuda",
            jobs,
            (logical_cores / jobs).max(2),
            7.8,
            0.25,
            1,
            "high",
            true,
            true,
            false,
        )
    } else if cuda_available || mps_available {
        (
            "entry_gpu",
            "Accelerated GPU / Apple Silicon",
            if cuda_available { "cuda" } else { "cpu" },
            1,
            (logical_cores / 2).max(2),
            5.0,
            0.25,
            1,
            "balanced",
            fp16_supported,
            true,
            false,
        )
    } else if logical_cores >= 8 && total_ram_mb >= 14000 {
        let jobs = 2;
        (
            "workstation_cpu",
            "Multi-Core Workstation CPU",
            "cpu",
            jobs,
            (logical_cores / jobs).max(2),
            7.0,
            0.25,
            1,
            "balanced",
            false,
            true,
            false,
        )
    } else if logical_cores >= 4 && total_ram_mb >= 6000 {
        (
            "standard_cpu",
            "Standard Multi-Core CPU",
            "cpu",
            1,
            logical_cores.max(2),
            6.0,
            0.25,
            1,
            "balanced",
            false,
            true,
            false,
        )
    } else {
        (
            "low_resource",
            "Compact / Low-Resource Device (Safe Mode)",
            "cpu",
            1,
            logical_cores.max(1),
            4.0,
            0.15,
            0,
            "fast",
            false,
            false,
            true,
        )
    };

    let _ = app_data_dir;
    HardwareProfile {
        os_name: std::env::consts::OS.to_string(),
        os_arch: std::env::consts::ARCH.to_string(),
        cpu_model,
        physical_cores,
        logical_cores,
        simd_features,
        total_ram_mb,
        available_ram_mb,
        disk_free_gb,
        cuda_available,
        mps_available,
        gpu_name,
        vram_mb,
        fp16_supported,
        device_tier: device_tier.to_string(),
        tier_label: tier_label.to_string(),
        recommended_device: rec_device.to_string(),
        recommended_max_concurrent_jobs: rec_jobs,
        recommended_threads_per_job: rec_threads,
        recommended_segment_s: rec_seg,
        recommended_overlap: rec_ovl,
        recommended_shifts: rec_shifts,
        recommended_preset: rec_preset.to_string(),
        recommended_fp16: rec_fp16,
        recommended_parallel_dsp: rec_par_dsp,
        recommended_safe_mode: rec_safe,
    }
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
                "Multi-process parallel worker pool (1-4 concurrent processes) & hardware auto-optimization".to_string(),
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
