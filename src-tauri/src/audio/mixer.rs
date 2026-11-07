use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicUsize, Ordering};
use std::sync::Arc;

use serde::{Deserialize, Serialize};

use crate::audio::decode::decode_audio_file;
use crate::error::{AppError, AppResult};

pub struct AtomicF32(AtomicU32);

impl AtomicF32 {
    pub fn new(val: f32) -> Self {
        Self(AtomicU32::new(val.to_bits()))
    }
    pub fn load(&self) -> f32 {
        f32::from_bits(self.0.load(Ordering::Relaxed))
    }
    pub fn store(&self, val: f32) {
        self.0.store(val.to_bits(), Ordering::Relaxed);
    }
}

pub struct StemTrack {
    pub name: String,
    pub path: PathBuf,
    pub samples_interleaved: Vec<f32>,
    pub gain: AtomicF32,
    pub mute: AtomicBool,
    pub solo: AtomicBool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StemTrackInfo {
    pub name: String,
    pub path: String,
    pub gain: f32,
    pub mute: bool,
    pub solo: bool,
    pub duration_s: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MixerSnapshot {
    pub folder_path: String,
    pub sample_rate: u32,
    pub channels: usize,
    pub total_frames: usize,
    pub playhead_frame: usize,
    pub playing: bool,
    pub stems: Vec<StemTrackInfo>,
}

pub struct LiveStemMixer {
    pub folder_path: PathBuf,
    pub sample_rate: u32,
    pub channels: usize,
    pub total_frames: usize,
    pub playhead_frame: AtomicUsize,
    pub playing: AtomicBool,
    pub stems: Vec<Arc<StemTrack>>,
}

impl LiveStemMixer {
    pub fn load_stems(stem_paths: Vec<(String, PathBuf)>, folder_path: PathBuf) -> AppResult<Self> {
        if stem_paths.is_empty() {
            return Err(AppError::InvalidInput(
                "No stem files provided to mixer".to_string(),
            ));
        }

        let mut loaded_stems = Vec::with_capacity(stem_paths.len());
        let mut target_sr = 44100_u32;
        let channels = 2_usize;
        let mut max_frames = 0_usize;

        for (idx, (name, path)) in stem_paths.into_iter().enumerate() {
            let decoded = decode_audio_file(&path)?;
            if idx == 0 {
                target_sr = decoded.sample_rate;
            }
            // Ensure 2-channel interleaved
            let mut stereo_samples = Vec::with_capacity(decoded.frames * 2);
            if decoded.channels == 1 {
                for &s in &decoded.samples_interleaved {
                    stereo_samples.push(s);
                    stereo_samples.push(s);
                }
            } else {
                for frame in decoded.samples_interleaved.chunks_exact(decoded.channels) {
                    stereo_samples.push(frame[0]);
                    stereo_samples.push(frame[1]);
                }
            }
            let frames = stereo_samples.len() / 2;
            max_frames = max_frames.max(frames);

            loaded_stems.push(Arc::new(StemTrack {
                name,
                path,
                samples_interleaved: stereo_samples,
                gain: AtomicF32::new(1.0),
                mute: AtomicBool::new(false),
                solo: AtomicBool::new(false),
            }));
        }

        Ok(Self {
            folder_path,
            sample_rate: target_sr,
            channels,
            total_frames: max_frames,
            playhead_frame: AtomicUsize::new(0),
            playing: AtomicBool::new(false),
            stems: loaded_stems,
        })
    }

    pub fn set_stem_gain(&self, stem_name: &str, gain: f32) -> bool {
        let clamped = gain.clamp(0.0, 2.0);
        for s in &self.stems {
            if s.name == stem_name {
                s.gain.store(clamped);
                return true;
            }
        }
        false
    }

    pub fn set_stem_mute(&self, stem_name: &str, mute: bool) -> bool {
        for s in &self.stems {
            if s.name == stem_name {
                s.mute.store(mute, Ordering::Relaxed);
                return true;
            }
        }
        false
    }

    pub fn set_stem_solo(&self, stem_name: &str, solo: bool) -> bool {
        for s in &self.stems {
            if s.name == stem_name {
                s.solo.store(solo, Ordering::Relaxed);
                return true;
            }
        }
        false
    }

    pub fn apply_volumes_map(&self, volumes: &HashMap<String, f32>) {
        for s in &self.stems {
            if let Some(&vol) = volumes.get(&s.name) {
                s.gain.store(vol.clamp(0.0, 2.0));
                s.mute.store(vol <= 0.0, Ordering::Relaxed);
            }
        }
    }

    pub fn seek_seconds(&self, seconds: f64) {
        let frame = ((seconds.max(0.0) * self.sample_rate as f64) as usize).min(self.total_frames);
        self.playhead_frame.store(frame, Ordering::Relaxed);
    }

    pub fn play(&self) {
        self.playing.store(true, Ordering::Relaxed);
    }

    pub fn pause(&self) {
        self.playing.store(false, Ordering::Relaxed);
    }

    /// Lock-free, zero-allocation real-time audio callback renderer.
    pub fn render_interleaved_frames(&self, out: &mut [f32]) {
        out.fill(0.0);
        if !self.playing.load(Ordering::Relaxed) || self.total_frames == 0 {
            return;
        }

        let any_solo = self
            .stems
            .iter()
            .any(|s| s.solo.load(Ordering::Relaxed));

        let num_frames = out.len() / self.channels;
        let start_frame = self.playhead_frame.load(Ordering::Relaxed);

        for f_offset in 0..num_frames {
            let cur_frame = start_frame + f_offset;
            if cur_frame >= self.total_frames {
                self.playing.store(false, Ordering::Relaxed);
                break;
            }
            let base_idx = cur_frame * self.channels;
            let mut l = 0.0_f32;
            let mut r = 0.0_f32;

            for stem in &self.stems {
                let is_solo = stem.solo.load(Ordering::Relaxed);
                let is_mute = stem.mute.load(Ordering::Relaxed);
                if (any_solo && !is_solo) || (!any_solo && is_mute) {
                    continue;
                }
                let g = stem.gain.load();
                if g <= 0.0 {
                    continue;
                }
                if base_idx + 1 < stem.samples_interleaved.len() {
                    l += stem.samples_interleaved[base_idx] * g;
                    r += stem.samples_interleaved[base_idx + 1] * g;
                }
            }

            out[f_offset * 2] = l.clamp(-0.99, 0.99);
            out[f_offset * 2 + 1] = r.clamp(-0.99, 0.99);
        }

        let next_frame = (start_frame + num_frames).min(self.total_frames);
        self.playhead_frame.store(next_frame, Ordering::Relaxed);
    }

    /// Render the entire mixed buffer offline using the exact same summing + peak soft-limit math.
    pub fn render_full_mix(&self, max_duration_s: Option<f64>) -> Vec<f32> {
        let frames_to_render = match max_duration_s {
            Some(sec) => ((sec * self.sample_rate as f64) as usize).min(self.total_frames),
            None => self.total_frames,
        };
        let mut mixed = vec![0.0_f32; frames_to_render * self.channels];
        let any_solo = self
            .stems
            .iter()
            .any(|s| s.solo.load(Ordering::Relaxed));

        for stem in &self.stems {
            let is_solo = stem.solo.load(Ordering::Relaxed);
            let is_mute = stem.mute.load(Ordering::Relaxed);
            if (any_solo && !is_solo) || (!any_solo && is_mute) {
                continue;
            }
            let g = stem.gain.load();
            if g <= 0.0 {
                continue;
            }
            let limit = mixed.len().min(stem.samples_interleaved.len());
            for i in 0..limit {
                mixed[i] += stem.samples_interleaved[i] * g;
            }
        }

        let peak = mixed.iter().fold(0.0_f32, |acc, &x| acc.max(x.abs()));
        if peak > 0.99 {
            let scale = 0.99 / peak;
            for x in &mut mixed {
                *x *= scale;
            }
        }
        mixed
    }

    pub fn snapshot(&self) -> MixerSnapshot {
        let dur = if self.sample_rate > 0 {
            (self.total_frames as f64 / self.sample_rate as f64 * 1000.0).round() / 1000.0
        } else {
            0.0
        };
        let stems = self
            .stems
            .iter()
            .map(|s| StemTrackInfo {
                name: s.name.clone(),
                path: s.path.to_string_lossy().to_string(),
                gain: s.gain.load(),
                mute: s.mute.load(Ordering::Relaxed),
                solo: s.solo.load(Ordering::Relaxed),
                duration_s: dur,
            })
            .collect();

        MixerSnapshot {
            folder_path: self.folder_path.to_string_lossy().to_string(),
            sample_rate: self.sample_rate,
            channels: self.channels,
            total_frames: self.total_frames,
            playhead_frame: self.playhead_frame.load(Ordering::Relaxed),
            playing: self.playing.load(Ordering::Relaxed),
            stems,
        }
    }
}

/// Discover stems inside an output folder matching `api_server/main.py:820-865` heuristic.
pub fn discover_stems_in_folder(folder_path: &Path) -> AppResult<Vec<(String, PathBuf)>> {
    if !folder_path.is_dir() {
        return Err(AppError::InvalidInput(format!(
            "Output folder not found: {}",
            folder_path.display()
        )));
    }

    let known_stems = [
        "vocals",
        "drums",
        "bass",
        "guitar",
        "piano",
        "other",
        "instrumental",
        "karaoke",
        "background",
    ];
    let valid_exts = ["wav", "mp3", "flac"];
    let mut found: Vec<(String, PathBuf)> = Vec::new();

    let mut entries: Vec<_> = std::fs::read_dir(folder_path)?
        .filter_map(|e| e.ok())
        .collect();
    entries.sort_by_key(|e| e.file_name());

    for entry in entries {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let Some(fname) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };
        let lower = fname.to_lowercase();
        if lower.starts_with("stem_mix")
            || lower.starts_with("stem_preview")
            || lower.contains("_custom.")
        {
            continue;
        }
        let Some(ext) = path.extension().and_then(|e| e.to_str()) else {
            continue;
        };
        if !valid_exts.contains(&ext.to_lowercase().as_str()) {
            continue;
        }

        let mut matched_name = None;
        for &k in &known_stems {
            if lower.contains(k) {
                matched_name = Some(k.to_string());
                break;
            }
        }
        let stem_name = matched_name.unwrap_or_else(|| {
            path.file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("stem")
                .to_string()
        });
        // Avoid duplicate stem keys if multiple formats exist
        if !found.iter().any(|(k, _)| k == &stem_name) {
            found.push((stem_name, path));
        }
    }

    Ok(found)
}
