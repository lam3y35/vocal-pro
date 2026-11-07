import React from "react";
import { CheckCircle2, Loader2, OctagonX, AlertTriangle } from "lucide-react";
import { useJobsStore } from "../state/appStores";

export const JobQueueBar: React.FC = () => {
  const jobs = useJobsStore((s) => s.jobs);
  const activeJobId = useJobsStore((s) => s.activeJobId);
  const setActiveJobId = useJobsStore((s) => s.setActiveJobId);
  const cancelJob = useJobsStore((s) => s.cancelJob);

  if (jobs.length === 0) return null;

  const activeJob = jobs.find((j) => j.job_id === activeJobId) || jobs[0];

  return (
    <div className="rounded-xl bg-[#161822] border border-[#25293A] p-3.5 space-y-3">
      {/* Multi-job horizontal tab strip (JobTabCard parity) */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {jobs.map((job) => {
          const fname = job.input_path.split(/[\\/]/).pop() || job.job_id;
          const isSelected = job.job_id === activeJob.job_id;
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
              <span className="max-w-[160px] truncate">{fname}</span>
              <span className="font-mono text-[11px] opacity-80">{job.percent}%</span>
            </button>
          );
        })}
      </div>

      {/* Active job real-time per-segment telemetry & <500ms cancel */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center gap-2.5">
            <span className="px-2 py-0.5 rounded bg-[#6C63FF]/20 border border-[#6C63FF]/40 text-[#6C63FF] font-mono uppercase text-[10px]">
              {activeJob.phase}
            </span>
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
