import React from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Cpu,
  Loader2,
  OctagonX,
  Pause,
  Play,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { JobPriority } from "../bindings";
import { useJobsStore, useSystemStore } from "../state/appStores";

export const JobQueueBar: React.FC = () => {
  const jobs = useJobsStore((s) => s.jobs);
  const activeJobId = useJobsStore((s) => s.activeJobId);
  const parallelWorkers = useJobsStore((s) => s.parallelWorkers);
  const queuePaused = useJobsStore((s) => s.queuePaused);
  const setActiveJobId = useJobsStore((s) => s.setActiveJobId);
  const cancelJob = useJobsStore((s) => s.cancelJob);
  const toggleQueuePaused = useJobsStore((s) => s.toggleQueuePaused);
  const setJobPriority = useJobsStore((s) => s.setJobPriority);
  const reorderJob = useJobsStore((s) => s.reorderJob);
  const retryFailedJob = useJobsStore((s) => s.retryFailedJob);
  const clearCompletedJobs = useJobsStore((s) => s.clearCompletedJobs);
  const exportDiagnosticBundle = useSystemStore((s) => s.exportDiagnosticBundle);

  if (jobs.length === 0) return null;

  const activeJob = jobs.find((j) => j.job_id === activeJobId) || jobs[0];
  const runningCount = jobs.filter(
    (j) => !["done", "cancelled", "failed"].includes(j.status)
  ).length;

  return (
    <div
      data-testid="job-queue-bar"
      className="rounded-xl bg-[#161822] border border-[#25293A] p-3.5 space-y-3"
    >
      {/* Multi-job horizontal tab strip with Worker Process Slot & Priority badges */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {jobs.map((job) => {
            const fname = job.input_path.split(/[\\/]/).pop() || job.job_id;
            const isSelected = job.job_id === activeJob.job_id;
            const slotNum = (job.worker_slot ?? 0) + 1;
            const prio = job.priority || "normal";
            return (
              <button
                key={job.job_id}
                type="button"
                onClick={() => setActiveJobId(job.job_id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border shrink-0 transition ${
                  isSelected
                    ? "bg-[#6C63FF]/20 border-[#6C63FF] text-white"
                    : "bg-[#0F1016] border-[#25293A] text-slate-400 hover:text-slate-200"
                }`}
              >
                {job.status === "done" ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#00D4AA]" />
                ) : job.status === "cancelled" ? (
                  <OctagonX className="w-3.5 h-3.5 text-[#FFB800]" />
                ) : job.status === "failed" ? (
                  <AlertTriangle className="w-3.5 h-3.5 text-[#FF5E7E]" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 text-[#6C63FF] animate-spin" />
                )}
                <span className="px-1.5 py-0.5 rounded bg-[#00D4AA]/15 text-[#00D4AA] font-mono text-[10px]">
                  W#{slotNum}
                </span>
                {prio !== "normal" && (
                  <span
                    className={`px-1.5 py-0.5 rounded font-mono text-[9px] uppercase ${
                      prio === "high"
                        ? "bg-[#FF5E7E]/20 text-[#FF5E7E]"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {prio}
                  </span>
                )}
                <span className="max-w-[150px] truncate">{fname}</span>
                <span className="font-mono text-[11px] opacity-80">{job.percent}%</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={toggleQueuePaused}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-semibold transition ${
              queuePaused
                ? "bg-[#FFB800]/20 border-[#FFB800] text-[#FFB800]"
                : "bg-[#0F1016] border-[#25293A] text-slate-300 hover:text-white"
            }`}
          >
            {queuePaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            <span>{queuePaused ? "Resume Queue" : "Pause Queue"}</span>
          </button>

          <button
            type="button"
            onClick={clearCompletedJobs}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#0F1016] border border-[#25293A] text-[11px] text-slate-400 hover:text-white transition"
            title="Clear completed and cancelled jobs"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Done</span>
          </button>

          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#0F1016] border border-[#25293A] text-[11px] font-mono text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-[#00D4AA]" />
            <span>
              Pool: {runningCount}/{parallelWorkers} Processes Active
            </span>
          </div>
        </div>
      </div>

      {/* Active job real-time per-segment telemetry, Priority, Reorder & <500ms cancel */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-[#6C63FF]/20 border border-[#6C63FF]/40 text-[#6C63FF] font-mono uppercase text-[10px]">
              {activeJob.phase}
            </span>
            <span className="px-2 py-0.5 rounded bg-[#00D4AA]/15 border border-[#00D4AA]/30 text-[#00D4AA] font-mono text-[10px]">
              Worker Process #{(activeJob.worker_slot ?? 0) + 1}
            </span>
            <select
              aria-label="Job Priority"
              value={activeJob.priority || "normal"}
              onChange={(e) => setJobPriority(activeJob.job_id, e.target.value as JobPriority)}
              className="bg-[#0F1016] border border-[#25293A] rounded px-2 py-0.5 text-[11px] text-slate-200 font-mono"
            >
              <option value="high">Priority: HIGH</option>
              <option value="normal">Priority: NORMAL</option>
              <option value="low">Priority: LOW</option>
            </select>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label="Move job up in queue"
                onClick={() => reorderJob(activeJob.job_id, "up")}
                className="p-1 rounded bg-[#0F1016] border border-[#25293A] text-slate-400 hover:text-white"
              >
                <ArrowUp className="w-3 h-3" />
              </button>
              <button
                type="button"
                aria-label="Move job down in queue"
                onClick={() => reorderJob(activeJob.job_id, "down")}
                className="p-1 rounded bg-[#0F1016] border border-[#25293A] text-slate-400 hover:text-white"
              >
                <ArrowDown className="w-3 h-3" />
              </button>
            </div>
            <span className="text-slate-200 font-medium">{activeJob.message}</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-slate-400 font-mono text-[11px]">
              Seg {activeJob.segment_index}/{activeJob.segment_total} • Sub-Model{" "}
              {activeJob.sub_model_index + 1}/{activeJob.sub_model_total}
              {activeJob.eta_s !== null && activeJob.eta_s > 0
                ? ` • ETA ${activeJob.eta_s}s`
                : ""}
            </span>
            {!["done", "cancelled", "failed"].includes(activeJob.status) && (
              <button
                type="button"
                onClick={() => cancelJob(activeJob.job_id)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-[#FF5E7E]/20 border border-[#FF5E7E]/50 text-[#FF5E7E] hover:bg-[#FF5E7E] hover:text-white text-xs font-semibold transition"
              >
                <OctagonX className="w-3.5 h-3.5" />
                Cancel (&lt;500ms)
              </button>
            )}
          </div>
        </div>

        {/* Structured Error Recovery Card (Workstream G & H) */}
        {activeJob.status === "failed" && (
          <div
            data-testid="job-error-card"
            role="alert"
            className="rounded-lg bg-[#FF5E7E]/15 border border-[#FF5E7E]/50 p-3 flex flex-wrap items-center justify-between gap-3 text-xs"
          >
            <div className="space-y-0.5">
              <div className="font-bold text-[#FF5E7E] flex items-center gap-1.5 font-mono">
                <AlertTriangle className="w-4 h-4" />
                <span>[{activeJob.error_code || "ENGINE_ERROR"}] Separation Job Failed</span>
              </div>
              <p className="text-slate-200">
                {activeJob.error_message || activeJob.message}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => retryFailedJob(activeJob.job_id)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#00D4AA] text-slate-950 font-bold hover:opacity-90 transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Retry Job</span>
              </button>
              <button
                type="button"
                onClick={exportDiagnosticBundle}
                className="px-3 py-1.5 rounded-lg bg-[#0F1016] border border-[#25293A] text-slate-200 hover:border-[#6C63FF] transition"
              >
                Export Diagnostics
              </button>
            </div>
          </div>
        )}

        <div className="w-full h-2 rounded-full bg-[#0F1016] overflow-hidden border border-[#25293A]">
          <div
            className="h-full transition-all duration-200 rounded-full"
            style={{
              width: `${activeJob.percent}%`,
              background:
                activeJob.status === "done"
                  ? "#00D4AA"
                  : activeJob.status === "cancelled"
                  ? "#FFB800"
                  : activeJob.status === "failed"
                  ? "#FF5E7E"
                  : "linear-gradient(90deg, #6C63FF 0%, #00D4AA 100%)",
            }}
          />
        </div>
      </div>
    </div>
  );
};
