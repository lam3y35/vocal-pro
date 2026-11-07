use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use crate::worker::protocol::{JobOptions, StemOutput};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Queued,
    LoadingModel,
    Decoding,
    Inferring,
    PostProcessing,
    Writing,
    Done,
    Cancelled,
    Failed,
}

impl JobStatus {
    pub fn from_worker_phase(phase: &str) -> Self {
        match phase {
            "loading_model" => Self::LoadingModel,
            "decoding" => Self::Decoding,
            "inference" => Self::Inferring,
            "postprocess_sfx"
            | "postprocess_denoise"
            | "postprocess_gate"
            | "postprocess_eq"
            | "postprocess_normalize" => Self::PostProcessing,
            "writing" | "muxing_video" => Self::Writing,
            _ => Self::Inferring,
        }
    }

    pub fn is_terminal(&self) -> bool {
        matches!(self, Self::Done | Self::Cancelled | Self::Failed)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobRecord {
    pub job_id: String,
    pub input_path: String,
    pub output_dir: String,
    pub options: JobOptions,
    pub status: JobStatus,
    pub phase: String,
    pub percent: f64,
    pub segment_index: u32,
    pub segment_total: u32,
    pub sub_model_index: u32,
    pub sub_model_total: u32,
    pub eta_s: Option<f64>,
    pub message: String,
    pub stems: Vec<StemOutput>,
    pub comparison_samples: Vec<String>,
    pub error_code: Option<String>,
    pub error_message: Option<String>,
    pub created_at: String,
    pub elapsed_s: Option<f64>,
}

#[derive(Default)]
pub struct JobQueue {
    jobs: HashMap<String, JobRecord>,
    order: Vec<String>,
}

impl JobQueue {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn enqueue(
        &mut self,
        job_id: String,
        input_path: String,
        output_dir: String,
        options: JobOptions,
    ) -> JobRecord {
        let now = chrono::Utc::now().to_rfc3339();
        let rec = JobRecord {
            job_id: job_id.clone(),
            input_path,
            output_dir,
            options,
            status: JobStatus::Queued,
            phase: "queued".to_string(),
            percent: 0.0,
            segment_index: 0,
            segment_total: 1,
            sub_model_index: 0,
            sub_model_total: 1,
            eta_s: None,
            message: "Queued".to_string(),
            stems: Vec::new(),
            comparison_samples: Vec::new(),
            error_code: None,
            error_message: None,
            created_at: now,
            elapsed_s: None,
        };
        if !self.jobs.contains_key(&job_id) {
            self.order.push(job_id.clone());
        }
        self.jobs.insert(job_id, rec.clone());
        rec
    }

    pub fn update_progress(
        &mut self,
        job_id: &str,
        phase: &str,
        segment_index: u32,
        segment_total: u32,
        sub_model_index: u32,
        sub_model_total: u32,
        percent: f64,
        eta_s: Option<f64>,
        message: Option<String>,
    ) -> Option<JobRecord> {
        let rec = self.jobs.get_mut(job_id)?;
        if rec.status.is_terminal() {
            return Some(rec.clone());
        }
        rec.status = JobStatus::from_worker_phase(phase);
        rec.phase = phase.to_string();
        rec.segment_index = segment_index;
        rec.segment_total = segment_total.max(1);
        rec.sub_model_index = sub_model_index;
        rec.sub_model_total = sub_model_total.max(1);
        rec.percent = percent.clamp(0.0, 100.0);
        rec.eta_s = eta_s;
        if let Some(m) = message {
            if !m.is_empty() {
                rec.message = m;
            }
        }
        Some(rec.clone())
    }

    pub fn mark_done(
        &mut self,
        job_id: &str,
        output_dir: String,
        stems: Vec<StemOutput>,
        comparison_samples: Vec<String>,
        elapsed_s: f64,
    ) -> Option<JobRecord> {
        let rec = self.jobs.get_mut(job_id)?;
        rec.status = JobStatus::Done;
        rec.phase = "done".to_string();
        rec.percent = 100.0;
        rec.eta_s = Some(0.0);
        rec.output_dir = output_dir;
        rec.stems = stems;
        rec.comparison_samples = comparison_samples;
        rec.elapsed_s = Some(elapsed_s);
        rec.message = "Completed".to_string();
        Some(rec.clone())
    }

    pub fn mark_cancelled(&mut self, job_id: &str) -> Option<JobRecord> {
        let rec = self.jobs.get_mut(job_id)?;
        rec.status = JobStatus::Cancelled;
        rec.phase = "cancelled".to_string();
        rec.message = "Cancelled by user".to_string();
        Some(rec.clone())
    }

    pub fn mark_failed(
        &mut self,
        job_id: &str,
        code: String,
        message: String,
    ) -> Option<JobRecord> {
        let rec = self.jobs.get_mut(job_id)?;
        rec.status = JobStatus::Failed;
        rec.phase = "failed".to_string();
        rec.error_code = Some(code);
        rec.error_message = Some(message.clone());
        rec.message = message;
        Some(rec.clone())
    }

    pub fn get(&self, job_id: &str) -> Option<&JobRecord> {
        self.jobs.get(job_id)
    }

    pub fn list(&self) -> Vec<JobRecord> {
        self.order
            .iter()
            .filter_map(|id| self.jobs.get(id).cloned())
            .collect()
    }
}
