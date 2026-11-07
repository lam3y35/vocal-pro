use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Instant;

use serde_json::json;
use tempfile::TempDir;

use vocalpro_lib::audio::waveform::compute_waveform_8000;
use vocalpro_lib::worker::protocol::JobOptions;
use vocalpro_lib::AppContext;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}

#[test]
fn test_legacy_migration_imports_all_files_and_deduplicates_outputs() {
    let tmp = TempDir::new().unwrap();
    let app_data = tmp.path().join("VocalPro");
    std::fs::create_dir_all(&app_data).unwrap();

    // 1. Write legacy ~/.vocalpro_config.json
    let home_cfg = tmp.path().join(".vocalpro_config.json");
    std::fs::write(
        &home_cfg,
        serde_json::to_string_pretty(&json!({
            "model_name": "htdemucs_ft",
            "shifts": 3,
            "denoise_strength": 0.65,
            "enable_sfx_separation": true
        }))
        .unwrap(),
    )
    .unwrap();

    // 2. Write legacy separation_history.json and download_history.json
    std::fs::write(
        app_data.join("separation_history.json"),
        serde_json::to_string_pretty(&json!([
            {
                "files": ["C:\\Music\\song1.mp3"],
                "model": "htdemucs_ft",
                "device": "cuda",
                "status": "success",
                "date": "2026-03-10 12:00:00",
                "elapsed": "31.4s",
                "output_dir": "C:\\Music\\output_vocals\\song1"
            }
        ]))
        .unwrap(),
    )
    .unwrap();

    std::fs::write(
        app_data.join("download_history.json"),
        serde_json::to_string_pretty(&json!([
            {
                "title": "demo.mp3",
                "url": "https://example.com/demo.mp3",
                "path": "C:\\Users\\Demo\\uploads\\demo.mp3",
                "format": "MP3",
                "quality": "320k",
                "date": "2026-03-10 11:55:00"
            }
        ]))
        .unwrap(),
    )
    .unwrap();

    // 3. Create an existing output folder with 4 stem files to verify P-06 deduplication
    let out_root = tmp.path().join("output_vocals");
    let song_dir = out_root.join("track_01");
    std::fs::create_dir_all(&song_dir).unwrap();
    let ref_wav = repo_root()
        .join("benchmarks")
        .join("reference-set")
        .join("track_01_pop_stereo_44k.wav");
    std::fs::copy(&ref_wav, song_dir.join("track_01_vocals.wav")).unwrap();
    std::fs::copy(&ref_wav, song_dir.join("track_01_drums.wav")).unwrap();
    std::fs::copy(&ref_wav, song_dir.join("track_01_bass.wav")).unwrap();
    std::fs::copy(&ref_wav, song_dir.join("track_01_other.wav")).unwrap();

    let db = vocalpro_lib::db::AppDatabase::open(&app_data.join("vocalpro.db")).unwrap();
    let report = db
        .migrate_legacy(&app_data, &[home_cfg], &[out_root])
        .unwrap();

    assert!(!report.already_migrated);
    assert!(report.backup_dir.is_some());
    assert!(report.settings_imported >= 4);
    assert_eq!(report.separation_history_imported, 1);
    assert_eq!(report.download_history_imported, 1);
    // P-06 verification: 4 files inside 1 folder must produce exactly 1 output folder entry!
    assert_eq!(report.outputs_indexed, 1);
    assert_eq!(db.list_outputs().unwrap().len(), 1);

    // Second run must be idempotent
    let report2 = db.migrate_legacy(&app_data, &[], &[]).unwrap();
    assert!(report2.already_migrated);
}

#[test]
fn test_native_symphonia_waveform_under_300ms_and_live_stem_mixer() {
    let ref_dir = repo_root().join("benchmarks").join("reference-set");
    let track = ref_dir.join("track_01_pop_stereo_44k.wav");

    let t0 = Instant::now();
    let wf = compute_waveform_8000(&track).unwrap();
    let elapsed_ms = t0.elapsed().as_secs_f64() * 1000.0;

    assert_eq!(wf.peaks.len(), 8000);
    assert_eq!(wf.sample_rate, 44100);
    assert_eq!(wf.channels, 2);
    assert!(
        elapsed_ms < 300.0,
        "Waveform took {:.2}ms (> 300ms budget)",
        elapsed_ms
    );

    // Test lock-free LiveStemMixer & export
    let tmp = TempDir::new().unwrap();
    let folder = tmp.path().join("mix_test");
    std::fs::create_dir_all(&folder).unwrap();
    std::fs::copy(
        ref_dir.join("track_01_clean_vocal_ref.wav"),
        folder.join("song_vocals.wav"),
    )
    .unwrap();
    std::fs::copy(
        ref_dir.join("track_01_clean_music_ref.wav"),
        folder.join("song_other.wav"),
    )
    .unwrap();

    let stems = vocalpro_lib::audio::mixer::discover_stems_in_folder(&folder).unwrap();
    assert_eq!(stems.len(), 2);

    let mixer = vocalpro_lib::audio::mixer::LiveStemMixer::load_stems(stems, folder.clone()).unwrap();
    mixer.play();
    mixer.set_stem_gain("vocals", 1.2);
    mixer.set_stem_gain("other", 0.5);

    let mut callback_buf = vec![0.0_f32; 512 * 2];
    mixer.render_interleaved_frames(&mut callback_buf);
    let energy: f32 = callback_buf.iter().map(|x| x.abs()).sum();
    assert!(energy > 0.1, "Expected non-zero audio output from mixer callback");

    let mut vols = HashMap::new();
    vols.insert("vocals".to_string(), 1.0_f32);
    vols.insert("other".to_string(), 0.8_f32);
    let mix_path =
        vocalpro_lib::audio::export::export_stem_mix(&folder, &vols, "wav", "320k").unwrap();
    assert!(mix_path.is_file());
}

#[tokio::test]
async fn test_rust_supervisor_and_python_worker_end_to_end() {
    let tmp = TempDir::new().unwrap();
    let app_data = tmp.path().join("VocalPro");
    let python_bin = PathBuf::from("/home/antigravity/.venv/bin/python");
    let worker_dir = repo_root().join("worker");

    let ctx = AppContext::new(app_data.clone(), python_bin, worker_dir, true).unwrap();
    let health = ctx.start_worker().unwrap();
    assert!(health.running);
    assert_eq!(health.worker_version, "3.0.0");

    // Submit 6-stem separation job via Rust supervisor -> Python stdio worker
    let ref_wav = repo_root()
        .join("benchmarks")
        .join("reference-set")
        .join("track_01_pop_stereo_44k.wav");
    let out_dir = tmp.path().join("sep_out");

    let mut opts = JobOptions::default();
    opts.model = "htdemucs_6s".to_string();
    opts.output_mode = "all_stems".to_string();
    opts.output_all_stems = true;
    opts.shifts = 0;
    opts.segment = Some(4.0);
    opts.enable_vocal_gate = false;
    opts.enable_spectral_denoise = false;

    let job_rec = ctx
        .submit_separation_job(
            ref_wav.to_string_lossy().to_string(),
            out_dir.to_string_lossy().to_string(),
            opts,
        )
        .await
        .unwrap();

    assert_eq!(
        job_rec.status,
        vocalpro_lib::worker::job_queue::JobStatus::Done
    );
    assert_eq!(job_rec.stems.len(), 6);

    // Verify outputs & separation_history were automatically persisted in SQLite (Fixes P-06 & P-14)
    let outputs = ctx.list_outputs().unwrap();
    assert_eq!(outputs.len(), 1);
    assert_eq!(outputs[0].stems.len(), 6);

    let history = ctx.list_separation_history().unwrap();
    assert_eq!(history.len(), 1);
    assert_eq!(history[0].status, "success");

    // Verify diagnostic log bundle export (SYS-03)
    let diag_zip = tmp.path().join("diagnostics.zip");
    ctx.export_diagnostics(&diag_zip).unwrap();
    assert!(diag_zip.is_file() && diag_zip.metadata().unwrap().len() > 100);
}
