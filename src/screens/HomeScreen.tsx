import React from "react";
import {
  AudioWaveform,
  Cpu,
  FolderOpen,
  HardDrive,
  Layers,
  Play,
  ShieldCheck,
  Sliders,
  Zap,
} from "lucide-react";
import { ScreenId } from "../components/Sidebar";
import { useJobsStore, useLibraryStore, useSystemStore } from "../state/appStores";

interface HomeScreenProps {
  onNavigate: (screen: ScreenId) => void;
}

export const HomeScreen: React.FC<HomeScreenProps> = ({ onNavigate }) => {
  const health = useSystemStore((s) => s.health);
  const hardwareProfile = useSystemStore((s) => s.hardwareProfile);
  const autoOptimizeForHardware = useSystemStore((s) => s.autoOptimizeForHardware);
  const models = useSystemStore((s) => s.models);
  const outputs = useLibraryStore((s) => s.outputs);
  const selectOutput = useLibraryStore((s) => s.selectOutput);
  const selectedFiles = useJobsStore((s) => s.selectedFiles);
  const parallelWorkers = useJobsStore((s) => s.parallelWorkers);

  return (
    <div className="space-y-6">
      {/* Studio Hero Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-[#161822] via-[#1C1F30] to-[#161822] border border-[#25293A] p-6 flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#00D4AA]/15 border border-[#00D4AA]/30 text-[#00D4AA] text-xs font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>100% Local Offline Studio Engine • Zero Localhost Ports</span>
            </div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#6C63FF]/15 border border-[#6C63FF]/30 text-[#6C63FF] text-xs font-mono">
              <Cpu className="w-3.5 h-3.5" />
              <span>
                {hardwareProfile.tier_label} • {parallelWorkers}x Parallel Processes
              </span>
            </div>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            VocalPro v3 — Cinema Movie &amp; Studio AI Audio Separator
          </h1>
          <p className="text-xs text-slate-300 leading-relaxed">
            Extract, isolate, and remux dialogue, score, and SFX directly from feature-length movies (MP4, MKV, AVI)
            using sequential chunked Demucs inference, 1:1 timeline synchronization, and compact perceptual studio encoding.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => onNavigate("separate")}
            className="flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-[#6C63FF] to-[#00D4AA] text-slate-950 font-bold text-xs shadow-lg shadow-[#6C63FF]/25 hover:opacity-95 transition"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>Open Separation Workstation ({selectedFiles.length} files queued)</span>
          </button>
          <button
            type="button"
            onClick={autoOptimizeForHardware}
            className="flex items-center gap-2 px-4 py-3 rounded-xl bg-[#0F1016] border border-[#00D4AA]/50 hover:bg-[#00D4AA]/10 text-[#00D4AA] font-semibold text-xs transition"
          >
            <Zap className="w-4 h-4" />
            <span>Auto-Tune for Hardware</span>
          </button>
          <button
            type="button"
            onClick={() => onNavigate("results")}
            className="flex items-center gap-2 px-4 py-3 rounded-xl bg-[#0F1016] border border-[#25293A] hover:border-[#6C63FF] text-slate-200 font-semibold text-xs transition"
          >
            <Sliders className="w-4 h-4 text-[#00D4AA]" />
            <span>Live Stem Mixer</span>
          </button>
        </div>
      </div>

      {/* 4 Telemetry Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Multi-Process Worker Pool</span>
            <Zap className="w-4 h-4 text-[#00D4AA]" />
          </div>
          <div className="text-lg font-bold text-white">
            {parallelWorkers} Parallel Processes
          </div>
          <div className="text-[11px] text-[#00D4AA]">
            Stdio JSON-Lines • 0 open TCP ports • &lt;500 ms cancel
          </div>
        </div>

        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Hardware Profile</span>
            <Cpu className="w-4 h-4 text-[#6C63FF]" />
          </div>
          <div className="text-lg font-bold text-white truncate">
            {health.cuda_available ? "CUDA + FP16 Ready" : `${hardwareProfile.logical_cores}T AVX2 CPU`}
          </div>
          <div className="text-[11px] text-slate-400 truncate">
            {hardwareProfile.cpu_model} • {(hardwareProfile.total_ram_mb / 1024).toFixed(0)} GB RAM
          </div>
        </div>

        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>AI Model Pool</span>
            <Layers className="w-4 h-4 text-[#FFB800]" />
          </div>
          <div className="text-lg font-bold text-white">{models.length} Specialist Models</div>
          <div className="text-[11px] text-slate-400">
            htdemucs, htdemucs_ft, htdemucs_6s, mdx + Ensemble
          </div>
        </div>

        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>State &amp; History Store</span>
            <HardDrive className="w-4 h-4 text-[#FF5E7E]" />
          </div>
          <div className="text-lg font-bold text-white">SQLite WAL Mode</div>
          <div className="text-[11px] text-slate-400">
            {outputs.length} indexed output folders (0 duplicates)
          </div>
        </div>
      </div>

      {/* Recent Separated Outputs & Model Pool */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-xl bg-[#161822] border border-[#25293A] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-[#6C63FF]" />
              <span>Recent Separated Output Folders</span>
            </h2>
            <button
              type="button"
              onClick={() => onNavigate("results")}
              className="text-xs text-[#00D4AA] hover:underline"
            >
              View All in Mixer →
            </button>
          </div>

          <div className="space-y-2.5">
            {outputs.map((out) => (
              <div
                key={out.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#0F1016] border border-[#25293A] p-3.5 hover:border-[#6C63FF]/50 transition"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-white">{out.folder_name}</span>
                    <span className="px-2 py-0.5 rounded bg-[#6C63FF]/20 text-[#6C63FF] font-mono text-[10px]">
                      {out.model}
                    </span>
                    {out.bpm && (
                      <span className="px-2 py-0.5 rounded bg-[#00D4AA]/15 text-[#00D4AA] font-mono text-[10px]">
                        {out.bpm} BPM • {out.musical_key}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono truncate max-w-lg">
                    {out.folder_path}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex flex-wrap gap-1">
                    {out.stems.map((s) => (
                      <span
                        key={s.name}
                        className="px-2 py-0.5 rounded bg-[#161822] border border-[#25293A] text-[10px] uppercase font-mono text-slate-300"
                      >
                        {s.name}
                      </span>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      selectOutput(out.id);
                      onNavigate("results");
                    }}
                    className="px-3 py-1.5 rounded-lg bg-[#6C63FF] text-white text-xs font-semibold hover:bg-[#6C63FF]/90 transition"
                  >
                    Open Mixer
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Model Pool Quick Reference */}
        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-5 space-y-3">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <AudioWaveform className="w-4 h-4 text-[#00D4AA]" />
            <span>Available AI Models ({models.length})</span>
          </h2>
          <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
            {models.map((m) => (
              <div
                key={m.id}
                className="rounded-lg bg-[#0F1016] border border-[#25293A] p-2.5 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-100 font-mono">{m.id}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      m.cached
                        ? "bg-[#00D4AA]/15 text-[#00D4AA]"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {m.stems.length} stems • {m.relative_compute}x
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-snug">{m.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
