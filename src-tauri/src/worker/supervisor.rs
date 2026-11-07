use std::collections::{HashMap, VecDeque};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use tokio::sync::{broadcast, oneshot, Notify};

use crate::error::{AppError, AppResult};
use crate::worker::job_queue::{JobQueue, JobRecord};
use crate::worker::protocol::{HostCommand, HostCommandPayload, JobOptions, WorkerEvent};

const MAX_LOG_LINES: usize = 500;
pub const MAX_POOL_WORKERS: usize = 4;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct WorkerSlotStatus {
    pub slot_id: u32,
    pub pid: Option<u32>,
    pub running: bool,
    pub active_job_id: Option<String>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct WorkerHealth {
    pub running: bool,
    pub worker_version: String,
    pub torch_version: String,
    pub cuda_available: bool,
    pub gpu_name: Option<String>,
    pub vram_mb: Option<u64>,
    pub restart_count: u32,
    pub max_concurrent_workers: u32,
    pub active_workers: u32,
    pub slots: Vec<WorkerSlotStatus>,
}

struct WorkerProcessSlot {
    slot_id: u32,
    pid: Option<u32>,
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    running: bool,
    active_job_id: Option<String>,
}

struct SupervisorInner {
    slots: Vec<WorkerProcessSlot>,
    max_concurrent_workers: usize,
    job_to_slot: HashMap<String, usize>,
    health: WorkerHealth,
    pending: HashMap<String, oneshot::Sender<WorkerEvent>>,
    logs: VecDeque<String>,
    pub queue: JobQueue,
}

#[derive(Clone)]
pub struct WorkerSupervisor {
    python_bin: PathBuf,
    worker_pythonpath: PathBuf,
    fast_test_model: bool,
    inner: Arc<Mutex<SupervisorInner>>,
    slot_notify: Arc<Notify>,
    event_tx: broadcast::Sender<WorkerEvent>,
}

impl WorkerSupervisor {
    pub fn new(python_bin: PathBuf, worker_pythonpath: PathBuf, fast_test_model: bool) -> Self {
        let default_concurrency = std::thread::available_parallelism()
            .map(|n| if n.get() >= 4 { 2 } else { 1 })
            .unwrap_or(2);
        let (event_tx, _) = broadcast::channel(512);
        let inner = SupervisorInner {
            slots: Vec::new(),
            max_concurrent_workers: default_concurrency,
            job_to_slot: HashMap::new(),
            health: WorkerHealth {
                running: false,
                worker_version: String::new(),
                torch_version: String::new(),
                cuda_available: false,
                gpu_name: None,
                vram_mb: None,
                restart_count: 0,
                max_concurrent_workers: default_concurrency as u32,
                active_workers: 0,
                slots: Vec::new(),
            },
            pending: HashMap::new(),
            logs: VecDeque::with_capacity(MAX_LOG_LINES),
            queue: JobQueue::new(),
        };
        Self {
            python_bin,
            worker_pythonpath,
            fast_test_model,
            inner: Arc::new(Mutex::new(inner)),
            slot_notify: Arc::new(Notify::new()),
            event_tx,
        }
    }

    pub fn set_max_concurrent_workers(&self, max_workers: usize) {
        let clamped = max_workers.clamp(1, MAX_POOL_WORKERS);
        {
            let mut guard = self.inner.lock().unwrap();
            guard.max_concurrent_workers = clamped;
            guard.health.max_concurrent_workers = clamped as u32;
        }
        self.slot_notify.notify_waiters();
    }

    pub fn max_concurrent_workers(&self) -> usize {
        self.inner.lock().unwrap().max_concurrent_workers
    }

    pub fn subscribe(&self) -> broadcast::Receiver<WorkerEvent> {
        self.event_tx.subscribe()
    }

    fn spawn_slot(&self, slot_id: usize) -> AppResult<()> {
        let mut cmd = Command::new(&self.python_bin);
        cmd.arg("-m")
            .arg("vocalpro_worker")
            .env("PYTHONPATH", &self.worker_pythonpath)
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        if self.fast_test_model {
            cmd.env("VOCALPRO_TEST_FAST_MODEL", "1");
        }

        let mut child = cmd.spawn().map_err(|e| {
            AppError::System(format!(
                "Failed to spawn python worker slot {} ({:?}): {}",
                slot_id, self.python_bin, e
            ))
        })?;

        let pid = Some(child.id());
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| AppError::System("Failed to open worker stdin".to_string()))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| AppError::System("Failed to open worker stdout".to_string()))?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| AppError::System("Failed to open worker stderr".to_string()))?;

        let mut stdout_reader = BufReader::new(stdout);
        let mut first_line = String::new();
        stdout_reader.read_line(&mut first_line)?;
        let initial_ev: WorkerEvent = serde_json::from_str(first_line.trim()).map_err(|e| {
            AppError::System(format!(
                "Invalid startup handshake from worker slot {} ({:?}): {}",
                slot_id, first_line, e
            ))
        })?;

        {
            let mut guard = self.inner.lock().unwrap();
            if let WorkerEvent::Ready {
                worker_version,
                torch_version,
                cuda_available,
                gpu_name,
                vram_mb,
                ..
            } = &initial_ev
            {
                guard.health.running = true;
                guard.health.worker_version = worker_version.clone();
                guard.health.torch_version = torch_version.clone();
                guard.health.cuda_available = *cuda_available;
                guard.health.gpu_name = gpu_name.clone();
                guard.health.vram_mb = *vram_mb;
            }

            while guard.slots.len() <= slot_id {
                let next_id = guard.slots.len() as u32;
                guard.slots.push(WorkerProcessSlot {
                    slot_id: next_id,
                    pid: None,
                    child: None,
                    stdin: None,
                    running: false,
                    active_job_id: None,
                });
            }

            guard.slots[slot_id] = WorkerProcessSlot {
                slot_id: slot_id as u32,
                pid,
                child: Some(child),
                stdin: Some(stdin),
                running: true,
                active_job_id: None,
            };
            Self::refresh_health_slots(&mut guard);
        }

        // Spawn stdout reader thread for this slot
        let inner_out = Arc::clone(&self.inner);
        let tx_out = self.event_tx.clone();
        let notify_out = Arc::clone(&self.slot_notify);
        std::thread::spawn(move || {
            for line_res in stdout_reader.lines() {
                let Ok(line) = line_res else { break };
                let trimmed = line.trim();
                if trimmed.is_empty() {
                    continue;
                }
                let Ok(ev) = serde_json::from_str::<WorkerEvent>(trimmed) else {
                    let mut g = inner_out.lock().unwrap();
                    if g.logs.len() >= MAX_LOG_LINES {
                        g.logs.pop_front();
                    }
                    g.logs
                        .push_back(format!("[slot-{}:stdout-unparsed] {}", slot_id, trimmed));
                    continue;
                };

                let _ = tx_out.send(ev.clone());

                let mut release_slot = false;
                {
                    let mut g = inner_out.lock().unwrap();
                    match &ev {
                        WorkerEvent::Progress {
                            job_id,
                            phase,
                            segment_index,
                            segment_total,
                            sub_model_index,
                            sub_model_total,
                            percent,
                            eta_s,
                            message,
                        } => {
                            g.queue.update_progress(
                                job_id,
                                phase,
                                *segment_index,
                                *segment_total,
                                *sub_model_index,
                                *sub_model_total,
                                *percent,
                                *eta_s,
                                message.clone(),
                            );
                        }
                        WorkerEvent::JobDone {
                            id,
                            job_id,
                            output_dir,
                            stems,
                            comparison_samples,
                            elapsed_s,
                        } => {
                            g.queue.mark_done(
                                job_id,
                                output_dir.clone(),
                                stems.clone(),
                                comparison_samples.clone(),
                                *elapsed_s,
                            );
                            g.job_to_slot.remove(job_id);
                            if let Some(s) = g.slots.get_mut(slot_id) {
                                if s.active_job_id.as_deref() == Some(job_id.as_str()) {
                                    s.active_job_id = None;
                                }
                            }
                            Self::refresh_health_slots(&mut g);
                            release_slot = true;
                            if let Some(waiter) = g.pending.remove(id) {
                                let _ = waiter.send(ev);
                            }
                        }
                        WorkerEvent::JobCancelled { id, job_id } => {
                            g.queue.mark_cancelled(job_id);
                            g.job_to_slot.remove(job_id);
                            if let Some(s) = g.slots.get_mut(slot_id) {
                                if s.active_job_id.as_deref() == Some(job_id.as_str()) {
                                    s.active_job_id = None;
                                }
                            }
                            Self::refresh_health_slots(&mut g);
                            release_slot = true;
                            if let Some(waiter) = g.pending.remove(id) {
                                let _ = waiter.send(ev.clone());
                            }
                            if let Some(waiter) = g.pending.remove(job_id) {
                                let _ = waiter.send(ev);
                            }
                        }
                        WorkerEvent::JobError {
                            id,
                            job_id,
                            code,
                            message,
                            ..
                        } => {
                            g.queue.mark_failed(job_id, code.clone(), message.clone());
                            g.job_to_slot.remove(job_id);
                            if let Some(s) = g.slots.get_mut(slot_id) {
                                if s.active_job_id.as_deref() == Some(job_id.as_str()) {
                                    s.active_job_id = None;
                                }
                            }
                            Self::refresh_health_slots(&mut g);
                            release_slot = true;
                            if let Some(waiter) = g.pending.remove(id) {
                                let _ = waiter.send(ev);
                            }
                        }
                        WorkerEvent::Pong { id }
                        | WorkerEvent::Capabilities { id, .. }
                        | WorkerEvent::AnalysisDone { id, .. }
                        | WorkerEvent::MidiDone { id, .. } => {
                            if let Some(waiter) = g.pending.remove(id) {
                                let _ = waiter.send(ev);
                            }
                        }
                        WorkerEvent::Ready { id: Some(id), .. } => {
                            if let Some(waiter) = g.pending.remove(id) {
                                let _ = waiter.send(ev);
                            }
                        }
                        WorkerEvent::Log { level, message } => {
                            if g.logs.len() >= MAX_LOG_LINES {
                                g.logs.pop_front();
                            }
                            g.logs
                                .push_back(format!("[slot-{}:{}] {}", slot_id, level, message));
                        }
                        _ => {}
                    }
                }
                if release_slot {
                    notify_out.notify_waiters();
                }
            }

            let mut g = inner_out.lock().unwrap();
            if let Some(s) = g.slots.get_mut(slot_id) {
                s.running = false;
                s.active_job_id = None;
            }
            Self::refresh_health_slots(&mut g);
            notify_out.notify_waiters();
        });

        // Spawn stderr ring-buffer reader thread
        let inner_err = Arc::clone(&self.inner);
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line_res in reader.lines() {
                let Ok(line) = line_res else { break };
                let mut g = inner_err.lock().unwrap();
                if g.logs.len() >= MAX_LOG_LINES {
                    g.logs.pop_front();
                }
                g.logs.push_back(format!("[slot-{}:stderr] {}", slot_id, line));
            }
        });

        Ok(())
    }

    fn refresh_health_slots(guard: &mut SupervisorInner) {
        let mut active_cnt = 0u32;
        let mut any_running = false;
        let mut slot_statuses = Vec::with_capacity(guard.slots.len());
        for s in &guard.slots {
            if s.running {
                any_running = true;
            }
            if s.active_job_id.is_some() {
                active_cnt += 1;
            }
            slot_statuses.push(WorkerSlotStatus {
                slot_id: s.slot_id,
                pid: s.pid,
                running: s.running,
                active_job_id: s.active_job_id.clone(),
            });
        }
        guard.health.running = any_running;
        guard.health.active_workers = active_cnt;
        guard.health.max_concurrent_workers = guard.max_concurrent_workers as u32;
        guard.health.slots = slot_statuses;
    }

    pub fn start(&self) -> AppResult<WorkerHealth> {
        self.spawn_slot(0)?;
        Ok(self.health())
    }

    pub fn health(&self) -> WorkerHealth {
        let mut g = self.inner.lock().unwrap();
        Self::refresh_health_slots(&mut g);
        g.health.clone()
    }

    pub fn recent_logs(&self) -> Vec<String> {
        self.inner.lock().unwrap().logs.iter().cloned().collect()
    }

    pub fn list_jobs(&self) -> Vec<JobRecord> {
        self.inner.lock().unwrap().queue.list()
    }

    pub fn get_job(&self, job_id: &str) -> Option<JobRecord> {
        self.inner.lock().unwrap().queue.get(job_id).cloned()
    }

    fn send_command_to_slot(&self, slot_id: usize, cmd: &HostCommand) -> AppResult<()> {
        let mut line = serde_json::to_string(cmd)?;
        line.push('\n');
        let mut guard = self.inner.lock().unwrap();
        let slot = guard
            .slots
            .get_mut(slot_id)
            .ok_or_else(|| AppError::System(format!("Worker slot {} does not exist", slot_id)))?;
        let stdin = slot.stdin.as_mut().ok_or_else(|| {
            AppError::System(format!("Worker slot {} stdin is not connected", slot_id))
        })?;
        stdin.write_all(line.as_bytes())?;
        stdin.flush()?;
        Ok(())
    }

    /// Acquire a free worker slot (0..max_concurrent_workers), spawning a new Python process on demand if needed.
    async fn acquire_slot_for_job(&self, job_id: &str) -> AppResult<usize> {
        loop {
            let mut need_spawn: Option<usize> = None;
            {
                let mut guard = self.inner.lock().unwrap();
                let max_w = guard.max_concurrent_workers.max(1);
                // 1. Check if any already-running slot < max_w is idle
                for idx in 0..guard.slots.len().min(max_w) {
                    if guard.slots[idx].running && guard.slots[idx].active_job_id.is_none() {
                        guard.slots[idx].active_job_id = Some(job_id.to_string());
                        guard.job_to_slot.insert(job_id.to_string(), idx);
                        guard.queue.assign_slot(job_id, idx as u32);
                        Self::refresh_health_slots(&mut guard);
                        return Ok(idx);
                    }
                }
                // 2. Check if we can spawn a new slot or respawn a stopped slot < max_w
                for idx in 0..max_w {
                    if idx >= guard.slots.len() || !guard.slots[idx].running {
                        need_spawn = Some(idx);
                        break;
                    }
                }
            }

            if let Some(slot_idx) = need_spawn {
                self.spawn_slot(slot_idx)?;
                let mut guard = self.inner.lock().unwrap();
                if slot_idx < guard.slots.len()
                    && guard.slots[slot_idx].running
                    && guard.slots[slot_idx].active_job_id.is_none()
                {
                    guard.slots[slot_idx].active_job_id = Some(job_id.to_string());
                    guard.job_to_slot.insert(job_id.to_string(), slot_idx);
                    guard.queue.assign_slot(job_id, slot_idx as u32);
                    Self::refresh_health_slots(&mut guard);
                    return Ok(slot_idx);
                }
            }

            self.slot_notify.notified().await;
        }
    }

    pub async fn request(&self, payload: HostCommandPayload) -> AppResult<WorkerEvent> {
        let ensure_slot_0 = {
            let guard = self.inner.lock().unwrap();
            guard.slots.is_empty() || !guard.slots[0].running
        };
        if ensure_slot_0 {
            self.spawn_slot(0)?;
        }

        let id = uuid::Uuid::new_v4().to_string();
        let cmd = HostCommand::new(id.clone(), payload);
        let (tx, rx) = oneshot::channel();
        {
            let mut guard = self.inner.lock().unwrap();
            guard.pending.insert(id, tx);
        }
        self.send_command_to_slot(0, &cmd)?;
        rx.await
            .map_err(|_| AppError::System("Worker channel closed before response".to_string()))
    }

    pub async fn submit_separation(
        &self,
        job_id: String,
        input_path: String,
        output_dir: String,
        options: JobOptions,
    ) -> AppResult<WorkerEvent> {
        {
            let mut guard = self.inner.lock().unwrap();
            guard.queue.enqueue(
                job_id.clone(),
                input_path.clone(),
                output_dir.clone(),
                options.clone(),
            );
        }

        let slot_idx = self.acquire_slot_for_job(&job_id).await?;
        let id = uuid::Uuid::new_v4().to_string();
        let cmd = HostCommand::new(
            id.clone(),
            HostCommandPayload::Separate {
                job_id: job_id.clone(),
                input_path,
                output_dir,
                options,
            },
        );
        let (tx, rx) = oneshot::channel();
        {
            let mut guard = self.inner.lock().unwrap();
            guard.pending.insert(id, tx);
        }

        if let Err(e) = self.send_command_to_slot(slot_idx, &cmd) {
            let mut guard = self.inner.lock().unwrap();
            guard.job_to_slot.remove(&job_id);
            if let Some(s) = guard.slots.get_mut(slot_idx) {
                s.active_job_id = None;
            }
            Self::refresh_health_slots(&mut guard);
            self.slot_notify.notify_waiters();
            return Err(e);
        }

        rx.await
            .map_err(|_| AppError::System("Worker channel closed before response".to_string()))
    }

    pub fn cancel_job(&self, job_id: &str) -> AppResult<()> {
        let target_slot = {
            let guard = self.inner.lock().unwrap();
            guard.job_to_slot.get(job_id).copied().unwrap_or(0)
        };
        let id = uuid::Uuid::new_v4().to_string();
        let cmd = HostCommand::new(
            id,
            HostCommandPayload::Cancel {
                job_id: job_id.to_string(),
            },
        );
        self.send_command_to_slot(target_slot, &cmd)
    }

    pub fn restart(&self) -> AppResult<WorkerHealth> {
        self.shutdown();
        {
            let mut guard = self.inner.lock().unwrap();
            guard.health.restart_count += 1;
        }
        self.start()
    }

    pub fn shutdown(&self) {
        let slot_count = { self.inner.lock().unwrap().slots.len() };
        for slot_idx in 0..slot_count {
            let id = uuid::Uuid::new_v4().to_string();
            let cmd = HostCommand::new(id, HostCommandPayload::Shutdown);
            let _ = self.send_command_to_slot(slot_idx, &cmd);
        }
        let mut guard = self.inner.lock().unwrap();
        for slot in &mut guard.slots {
            slot.stdin.take();
            if let Some(mut child) = slot.child.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
            slot.running = false;
            slot.active_job_id = None;
        }
        guard.job_to_slot.clear();
        Self::refresh_health_slots(&mut guard);
    }
}

impl Drop for WorkerSupervisor {
    fn drop(&mut self) {
        if Arc::strong_count(&self.inner) == 1 {
            self.shutdown();
        }
    }
}
