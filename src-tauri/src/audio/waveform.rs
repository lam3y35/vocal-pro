use crate::audio::decode::{decode_audio_file, DecodedAudio};
use crate::error::AppResult;
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaveformSummary {
    pub peaks: Vec<f32>,
    pub duration_s: f64,
    pub sample_rate: u32,
    pub channels: usize,
}

pub fn compute_waveform_from_decoded(
    decoded: &DecodedAudio,
    num_buckets: usize,
) -> WaveformSummary {
    let mono = decoded.to_mono();
    let target = num_buckets.max(1);

    let mut raw_peaks: Vec<f32> = if mono.len() > target {
        let step = mono.len() / target;
        (0..target)
            .map(|i| {
                let slice = &mono[i * step..(i + 1) * step];
                slice.iter().fold(0.0_f32, |acc, &x| acc.max(x.abs()))
            })
            .collect()
    } else {
        mono.iter().map(|&x| x.abs()).collect()
    };

    let max_val = raw_peaks.iter().copied().fold(0.0_f32, f32::max);
    if max_val > 0.0 {
        for p in &mut raw_peaks {
            *p = ((*p / max_val) * 1000.0).round() / 1000.0;
        }
    }

    WaveformSummary {
        peaks: raw_peaks,
        duration_s: (decoded.duration_s() * 1000.0).round() / 1000.0,
        sample_rate: decoded.sample_rate,
        channels: decoded.channels,
    }
}

pub fn compute_waveform_8000(path: &Path) -> AppResult<WaveformSummary> {
    let decoded = decode_audio_file(path)?;
    Ok(compute_waveform_from_decoded(&decoded, 8000))
}
