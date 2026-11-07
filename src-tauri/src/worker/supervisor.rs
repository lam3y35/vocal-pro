use std::collections::{HashMap, VecDeque};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use tokio::sync::{broadcast, oneshot};

use crate::error::{AppError, AppResult};
use crate::worker::job_queue::{JobQueue, JobRecord};
use crate::worker::protocol::{HostCommand, HostCommandPayload, JobOptions, WorkerEvent};

const MAX_LOG_LINES: usize = 500;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct WorkerHealth {
    pub running: bool,
    pub worker_version: String,
    pub torch_version: String,
    pub cuda_available: bool,
    pub gpu_name: Option<String>,
    pub vram_mb: Option<u64>,
    pub restart_count: u32,
}

struct SupervisorInner {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
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
    event_tx: broadcast::Sender<WorkerEvent>,
}

impl WorkerSupervisor {
    pub fn new(python_bin: PathBuf, worker_pythonpath: PathBuf, fast_test_model: bool) -> Self {
        let (event_tx, _) = broadcast::channel(512);
        let inner = SupervisorInner {
            child: None,
            stdin: None,
            health: WorkerHealth {
                running: false,
                worker_version: String::new(),
                torch_version: String::new(),
                cuda_available: false,
                gpu_name: None,
                vram_mb: None,
                restart_count: 0,
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
            event_tx,
        }
    }

    pub fn subscribe(&self) -> broadcast::Receiver<WorkerEvent> {
        self.event_tx.subscribe()
    }

    pub fn start(&self) -> AppResult<WorkerHealth> {
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
                "Failed to spawn python worker ({:?}): {}",
                self.python_bin, e
            ))
        })?;

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

        // Read initial ready handshake synchronously or via reader thread
        let mut stdout_reader = BufReader::new(stdout);
        let mut first_line = String::new();
        stdout_reader.read_line(&mut first_line)?;
        let initial_ev: WorkerEvent = serde_json::from_str(first_line.trim()).map_err(|e| {
            AppError::System(format!(
                "Invalid startup handshake from worker ({:?}): {}",
                first_line, e
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
            guard.stdin = Some(stdin);
            guard.child = Some(child);
        }

        // Spawn stdout reader thread
        let inner_out = Arc::clone(&self.inner);
        let tx_out = self.event_tx.clone();
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
                    g.logs.push_back(format!("[stdout-unparsed] {}", trimmed));
                    continue;
                };

                let _ = tx_out.send(ev.clone());

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
                        if let Some(waiter) = g.pending.remove(id) {
                            let _ = waiter.send(ev);
                        }
                    }
                    WorkerEvent::JobCancelled { id, job_id } => {
                        g.queue.mark_cancelled(job_id);
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
                        g.logs.push_back(format!("[{}] {}", level, message));
                    }
                    _ => {}
                }
            }

            let mut g = inner_out.lock().unwrap();
            g.health.running = false;
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
                g.logs.push_back(format!("[stderr] {}", line));
            }
        });

        Ok(self.health())
    }

    pub fn health(&self) -> WorkerHealth {
        self.inner.lock().unwrap().health.clone()
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

    fn send_raw_command(&self, cmd: &HostCommand) -> AppResult<()> {
        let mut line = serde_json::to_string(cmd)?;
        line.push('\n');
        let mut guard = self.inner.lock().unwrap();
        let stdin = guard
            .stdin
            .as_mut()
            .ok_or_else(|| AppError::System("Worker stdin is not connected".to_string()))?;
        stdin.write_all(line.as_bytes())?;
        stdin.flush()?;
        Ok(())
    }

    pub async fn request(&self, payload: HostCommandPayload) -> AppResult<WorkerEvent> {
        let id = uuid::Uuid::new_v4().to_string();
        let cmd = HostCommand::new(id.clone(), payload);
        let (tx, rx) = oneshot::channel();
        {
            let mut guard = self.inner.lock().unwrap();
            guard.pending.insert(id, tx);
        }
        self.send_raw_command(&cmd)?;
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
        self.request(HostCommandPayload::Separate {
            job_id,
            input_path,
            output_dir,
            options,
        })
        .await
    }

    pub fn cancel_job(&self, job_id: &str) -> AppResult<()> {
        let id = uuid::Uuid::new_v4().to_string();
        let cmd = HostCommand::new(
            id,
            HostCommandPayload::Cancel {
                job_id: job_id.to_string(),
            },
        );
        self.send_raw_command(&cmd)
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
        let id = uuid::Uuid::new_v4().to_string();
        let cmd = HostCommand::new(id, HostCommandPayload::Shutdown);
        let _ = self.send_raw_command(&cmd);
        let mut guard = self.inner.lock().unwrap();
        guard.stdin.take();
        if let Some(mut child) = guard.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        guard.health.running = false;
    }
}

impl Drop for WorkerSupervisor {
    fn drop(&mut self) {
        if Arc::strong_count(&self.inner) == 1 {
            self.shutdown();
        }
    }
}
