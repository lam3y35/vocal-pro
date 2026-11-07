use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::audio::export::{export_separate_custom_stems, export_stem_mix};
use crate::audio::mixer::{discover_stems_in_folder, LiveStemMixer, MixerSnapshot};
use crate::audio::waveform::{compute_waveform_8000, WaveformSummary};
use crate::db::{
    AppDatabase, DownloadHistoryEntry, OutputFolderEntry, SeparationHistoryEntry,
};
use crate::error::{AppError, AppResult};
use crate::models::{list_supported_models, ModelInfo};
use crate::system::{
    create_desktop_shortcut, download_media_url, export_diagnostic_bundle, get_changelog_releases,
    register_file_associations, ChangelogRelease,
};
use crate::worker::job_queue::JobRecord;
use crate::worker::protocol::{HostCommandPayload, JobOptions, WorkerEvent};
use crate::worker::supervisor::{WorkerHealth, WorkerSupervisor};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisResult {
    pub bpm: f64,
    pub key: String,
    pub scale: String,
    pub duration_s: f64,
    pub waveform: Vec<f64>,
}

#[derive(Clone)]
pub struct AppContext {
    pub app_data_dir: PathBuf,
    pub db: AppDatabase,
    pub worker: WorkerSupervisor,
    pub active_mixer: Arc<Mutex<Option<Arc<LiveStemMixer>>>>,
}

impl AppContext {
    pub fn new(
        app_data_dir: PathBuf,
        python_bin: PathBuf,
        worker_pythonpath: PathBuf,
        fast_test_model: bool,
    ) -> AppResult<Self> {
        std::fs::create_dir_all(&app_data_dir)?;
        let db_path = app_data_dir.join("vocalpro.db");
        let db = AppDatabase::open(&db_path)?;

        // Check home dir for legacy ~/.vocalpro_config.json and ~/.vocal_remover_pro_config.json (Fixes P-15)
        let mut extra_cfgs = Vec::new();
        if let Some(home) = dirs::home_dir() {
            extra_cfgs.push(home.join(".vocalpro_config.json"));
            extra_cfgs.push(home.join(".vocal_remover_pro_config.json"));
        }
        let default_outputs_dir = app_data_dir.join("output_vocals");
        let _ = db.migrate_legacy(&app_data_dir, &extra_cfgs, &[default_outputs_dir]);

        let worker = WorkerSupervisor::new(python_bin, worker_pythonpath, fast_test_model);

        Ok(Self {
            app_data_dir,
            db,
            worker,
            active_mixer: Arc::new(Mutex::new(None)),
        })
    }

    pub fn start_worker(&self) -> AppResult<WorkerHealth> {
        self.worker.start()
    }

    pub fn worker_health(&self) -> WorkerHealth {
        self.worker.health()
    }

    pub fn restart_worker(&self) -> AppResult<WorkerHealth> {
        self.worker.restart()
    }

    pub async fn submit_separation_job(
        &self,
        input_path: String,
        output_dir: String,
        options: JobOptions,
    ) -> AppResult<JobRecord> {
        let job_id = uuid::Uuid::new_v4().to_string();
        let model_name = options.model.clone();
        let device_name = options.device.clone();
        let source_filename = Path::new(&input_path)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("audio")
            .to_string();

        let ev = self
            .worker
            .submit_separation(job_id.clone(), input_path.clone(), output_dir, options)
            .await?;

        match ev {
            WorkerEvent::JobDone {
                output_dir: final_dir,
                stems,
                elapsed_s,
                ..
            } => {
                let folder_name = Path::new(&final_dir)
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or(&source_filename)
                    .to_string();
                let dur = stems.first().map(|s| s.duration_s);

                // Record in outputs table (Fixes P-06)
                self.db.record_output_folder(
                    Some(&job_id),
                    &folder_name,
                    &final_dir,
                    &source_filename,
                    &model_name,
                    &stems,
                    dur,
                )?;

                // Record in separation_history table (Fixes P-14!)
                self.db.record_separation_history(
                    &[input_path],
                    &model_name,
                    &device_name,
                    "success",
                    elapsed_s,
                    Some(&final_dir),
                )?;
            }
            WorkerEvent::JobCancelled { .. } => {
                self.db.record_separation_history(
                    &[input_path],
                    &model_name,
                    &device_name,
                    "cancelled",
                    0.0,
                    None,
                )?;
            }
            WorkerEvent::JobError { code, message, detail, .. } => {
                self.db.record_separation_history(
                    &[input_path],
                    &model_name,
                    &device_name,
                    "error",
                    0.0,
                    None,
                )?;
                return Err(AppError::Worker {
                    code,
                    message,
                    detail,
                });
            }
            _ => {}
        }

        self.worker
            .get_job(&job_id)
            .ok_or_else(|| AppError::System(format!("Job {} not found in queue", job_id)))
    }

    pub fn cancel_job(&self, job_id: &str) -> AppResult<()> {
        self.worker.cancel_job(job_id)
    }

    pub fn list_jobs(&self) -> Vec<JobRecord> {
        self.worker.list_jobs()
    }

    pub fn fast_waveform(&self, audio_path: &str) -> AppResult<WaveformSummary> {
        compute_waveform_8000(Path::new(audio_path))
    }

    pub async fn analyze_audio(&self, audio_path: String) -> AppResult<AnalysisResult> {
        let ev = self
            .worker
            .request(HostCommandPayload::Analyze {
                input_path: audio_path.clone(),
            })
            .await?;

        match ev {
            WorkerEvent::AnalysisDone {
                bpm,
                key,
                scale,
                duration_s,
                waveform,
                ..
            } => {
                if let Some(parent) = Path::new(&audio_path).parent() {
                    let _ = self.db.update_output_analysis(
                        &parent.to_string_lossy(),
                        bpm,
                        &key,
                        &scale,
                        duration_s,
                    );
                }
                Ok(AnalysisResult {
                    bpm,
                    key,
                    scale,
                    duration_s,
                    waveform,
                })
            }
            WorkerEvent::JobError {
                code,
                message,
                detail,
                ..
            } => Err(AppError::Worker {
                code,
                message,
                detail,
            }),
            other => Err(AppError::System(format!(
                "Unexpected worker event for analyze: {:?}",
                other
            ))),
        }
    }

    pub async fn stem_to_midi(
        &self,
        stem_path: String,
        output_midi_path: String,
    ) -> AppResult<(String, u32)> {
        let ev = self
            .worker
            .request(HostCommandPayload::StemToMidi {
                stem_path,
                output_midi_path,
            })
            .await?;

        match ev {
            WorkerEvent::MidiDone {
                output_midi_path,
                note_count,
                ..
            } => Ok((output_midi_path, note_count)),
            WorkerEvent::JobError {
                code,
                message,
                detail,
                ..
            } => Err(AppError::Worker {
                code,
                message,
                detail,
            }),
            other => Err(AppError::System(format!(
                "Unexpected worker event for stem_to_midi: {:?}",
                other
            ))),
        }
    }

    pub fn mixer_load_folder(&self, folder_path: &str) -> AppResult<MixerSnapshot> {
        let path = Path::new(folder_path);
        let stems = discover_stems_in_folder(path)?;
        let mixer = Arc::new(LiveStemMixer::load_stems(stems, path.to_path_buf())?);
        let snap = mixer.snapshot();
        *self.active_mixer.lock().unwrap() = Some(mixer);
        Ok(snap)
    }

    pub fn mixer_set_gain(&self, stem_name: &str, gain: f32) -> AppResult<MixerSnapshot> {
        let guard = self.active_mixer.lock().unwrap();
        let mixer = guard
            .as_ref()
            .ok_or_else(|| AppError::InvalidInput("No folder loaded in mixer".to_string()))?;
        mixer.set_stem_gain(stem_name, gain);
        Ok(mixer.snapshot())
    }

    pub fn mixer_set_mute(&self, stem_name: &str, mute: bool) -> AppResult<MixerSnapshot> {
        let guard = self.active_mixer.lock().unwrap();
        let mixer = guard
            .as_ref()
            .ok_or_else(|| AppError::InvalidInput("No folder loaded in mixer".to_string()))?;
        mixer.set_stem_mute(stem_name, mute);
        Ok(mixer.snapshot())
    }

    pub fn mixer_set_solo(&self, stem_name: &str, solo: bool) -> AppResult<MixerSnapshot> {
        let guard = self.active_mixer.lock().unwrap();
        let mixer = guard
            .as_ref()
            .ok_or_else(|| AppError::InvalidInput("No folder loaded in mixer".to_string()))?;
        mixer.set_stem_solo(stem_name, solo);
        Ok(mixer.snapshot())
    }

    pub fn mixer_export_mix(
        &self,
        folder_path: &str,
        volumes: &HashMap<String, f32>,
        format: &str,
        bitrate: &str,
    ) -> AppResult<String> {
        let out = export_stem_mix(Path::new(folder_path), volumes, format, bitrate)?;
        Ok(out.to_string_lossy().to_string())
    }

    pub fn mixer_export_separate(
        &self,
        folder_path: &str,
        volumes: &HashMap<String, f32>,
        format: &str,
        bitrate: &str,
    ) -> AppResult<Vec<String>> {
        let outs = export_separate_custom_stems(Path::new(folder_path), volumes, format, bitrate)?;
        Ok(outs
            .into_iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect())
    }

    pub fn list_outputs(&self) -> AppResult<Vec<OutputFolderEntry>> {
        self.db.list_outputs()
    }

    pub fn list_separation_history(&self) -> AppResult<Vec<SeparationHistoryEntry>> {
        self.db.list_separation_history()
    }

    pub fn clear_separation_history(&self) -> AppResult<()> {
        self.db.clear_separation_history()
    }

    pub fn list_download_history(&self) -> AppResult<Vec<DownloadHistoryEntry>> {
        self.db.list_download_history()
    }

    pub fn clear_download_history(&self) -> AppResult<()> {
        self.db.clear_download_history()
    }

    pub fn download_url(&self, url: &str) -> AppResult<DownloadHistoryEntry> {
        let uploads_dir = self.app_data_dir.join("uploads");
        let (title, path, format) = download_media_url(url, &uploads_dir)?;
        let path_str = path.to_string_lossy().to_string();
        self.db
            .record_download_history(&title, url, &path_str, &format, "Original")?;
        let list = self.db.list_download_history()?;
        list.into_iter()
            .next()
            .ok_or_else(|| AppError::System("Failed to read download history record".to_string()))
    }

    pub fn list_models(&self) -> Vec<ModelInfo> {
        let ckpt_dir = dirs::cache_dir().map(|d| d.join("torch/hub/checkpoints"));
        list_supported_models(ckpt_dir.as_deref())
    }

    pub fn register_associations(&self) -> AppResult<bool> {
        register_file_associations(&self.app_data_dir, None)
    }

    pub fn create_shortcut(&self) -> AppResult<String> {
        let p = create_desktop_shortcut(&self.app_data_dir, None)?;
        Ok(p.to_string_lossy().to_string())
    }

    pub fn export_diagnostics(&self, target_zip: &Path) -> AppResult<String> {
        let logs = self.worker.recent_logs();
        let settings = serde_json::to_string_pretty(&self.db.get_all_settings()?)?;
        let health = serde_json::to_string_pretty(&self.worker.health())?;
        let out = export_diagnostic_bundle(target_zip, &logs, &settings, &health)?;
        Ok(out.to_string_lossy().to_string())
    }

    pub fn changelog(&self) -> Vec<ChangelogRelease> {
        get_changelog_releases()
    }

    pub fn get_settings(&self) -> AppResult<HashMap<String, Value>> {
        self.db.get_all_settings()
    }

    pub fn save_settings(&self, updates: &HashMap<String, Value>) -> AppResult<()> {
        self.db.update_settings(updates)
    }
}
