import React from "react";
import {
  Activity,
  Download,
  FolderOpen,
  Pause,
  Play,
  RotateCcw,
  Sliders,
  Sparkles,
} from "lucide-react";
import { CanvasWaveform } from "../components/CanvasWaveform";
import { StemMixerStrip } from "../components/StemMixerStrip";
import { TRANSLATIONS } from "../i18n/translations";
import { invokeCommand } from "../ipc";
import { useJobsStore, useLibraryStore, useMixerStore, useSystemStore } from "../state/appStores";

export const ResultsScreen: React.FC = () => {
  const locale = useSystemStore((s) => s.locale);
  const t = TRANSLATIONS[locale];

  const outputs = useLibraryStore((s) => s.outputs);
  const selectedOutputId = useLibraryStore((s) => s.selectedOutputId);
  const selectOutput = useLibraryStore((s) => s.selectOutput);
  const analysisByFolder = useLibraryStore((s) => s.analysisByFolder);
  const runAnalysisForFolder = useLibraryStore((s) => s.runAnalysisForFolder);

  const stems = useMixerStore((s) => s.stems);
  const playing = useMixerStore((s) => s.playing);
  const playheadSec = useMixerStore((s) => s.playheadSec);
  const durationSec = useMixerStore((s) => s.durationSec);
  const exportFormat = useMixerStore((s) => s.exportFormat);
  const exportBitrate = useMixerStore((s) => s.exportBitrate);
  const lastExportMessage = useMixerStore((s) => s.lastExportMessage);
  const setStemGain = useMixerStore((s) => s.setStemGain);
  const toggleMute = useMixerStore((s) => s.toggleMute);
  const toggleSolo = useMixerStore((s) => s.toggleSolo);
  const resetStems = useMixerStore((s) => s.resetStems);
  const togglePlay = useMixerStore((s) => s.togglePlay);
  const seek = useMixerStore((s) => s.seek);
  const setExportFormat = useMixerStore((s) => s.setExportFormat);
  const setExportBitrate = useMixerStore((s) => s.setExportBitrate);
  const exportMix = useMixerStore((s) => s.exportMix);
  const exportSeparateStems = useMixerStore((s) => s.exportSeparateStems);
  const exportStemMidi = useMixerStore((s) => s.exportStemMidi);

  const previewWaveform = useJobsStore((s) => s.previewWaveform);

  const activeOutput = outputs.find((o) => o.id === selectedOutputId) || outputs[0];
  const analysis = activeOutput ? analysisByFolder[activeOutput.folder_path] : undefined;

  return (
    <div className="space-y-5 pb-10">
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Left Sidebar: Deduplicated Output Folders Library (LIB-01, LIB-02, Fixes P-06) */}
        <div className="xl:col-span-4 rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-[#6C63FF]" />
              <span>Outputs Library ({outputs.length})</span>
            </h2>
            <span className="text-[10px] font-mono text-[#00D4AA]">SQLite Indexed</span>
          </div>

          <div className="space-y-2 max-h-[540px] overflow-y-auto pr-1">
            {outputs.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#25293A] p-6 text-center text-slate-500 text-xs">
                No separated outputs yet.
                <br />
                Add an audio track in the Separation tab to get started!
              </div>
            ) : (
              outputs.map((out) => {
                const selected = out.id === activeOutput?.id;
                return (
                  <button
                    key={out.id}
                    type="button"
                    onClick={() => selectOutput(out.id)}
                    className={`w-full text-left rounded-xl p-3 border transition space-y-1.5 ${
                      selected
                        ? "bg-[#6C63FF]/20 border-[#6C63FF] text-white"
                        : "bg-[#0F1016] border-[#25293A] text-slate-300 hover:border-slate-600"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-xs truncate">{out.folder_name}</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#161822] text-[#00D4AA]">
                        {out.stems.length} stems
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {out.stems.map((s) => (
                        <span
                          key={s.name}
                          className="text-[9px] uppercase font-mono px-1.5 py-0.5 rounded bg-[#161822] text-slate-400"
                        >
                          {s.name}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right Main Area: Audio Analysis + Live Multi-Stem Mixer + Export */}
        <div className="xl:col-span-8 space-y-5">
          {/* 1. Audio Analysis & Master Transport Card (ANA-01) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-3.5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-[#00D4AA]" />
                  <span>{activeOutput?.folder_name || "No Output Selected"}</span>
                </h2>
                {activeOutput?.folder_path && (
                  <div className="flex items-center gap-2">
                    <p className="text-[11px] font-mono text-slate-400 truncate max-w-md">
                      {activeOutput.folder_path}
                    </p>
                    <button
                      type="button"
                      onClick={() => invokeCommand("open_folder", { path: activeOutput.folder_path })}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#0F1016] border border-[#25293A] hover:border-[#00D4AA] text-[#00D4AA] text-[10px] transition shrink-0"
                    >
                      <FolderOpen className="w-3 h-3" />
                      <span>Open Folder</span>
                    </button>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2">
                <div className="px-3 py-1.5 rounded-lg bg-[#0F1016] border border-[#25293A] text-xs font-mono">
                  <span className="text-slate-400">BPM: </span>
                  <span className="text-[#00D4AA] font-bold">
                    {analysis?.bpm ?? activeOutput?.bpm ?? "—"}
                  </span>
                </div>
                <div className="px-3 py-1.5 rounded-lg bg-[#0F1016] border border-[#25293A] text-xs font-mono">
                  <span className="text-slate-400">Key: </span>
                  <span className="text-[#6C63FF] font-bold">
                    {analysis?.key ?? activeOutput?.musical_key ?? "—"}
                  </span>
                </div>
                {activeOutput && (
                  <button
                    type="button"
                    onClick={() => runAnalysisForFolder(activeOutput.folder_path)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6C63FF]/20 border border-[#6C63FF]/40 text-[#6C63FF] hover:bg-[#6C63FF] hover:text-white text-xs font-semibold transition"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>{t.btn_analyze}</span>
                  </button>
                )}
              </div>
            </div>

            {/* Interactive Master Transport & 8,000-Point Waveform */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={togglePlay}
                className="h-10 w-10 rounded-xl bg-gradient-to-br from-[#6C63FF] to-[#00D4AA] text-slate-950 flex items-center justify-center shrink-0 shadow-md"
              >
                {playing ? (
                  <Pause className="w-4 h-4 fill-current" />
                ) : (
                  <Play className="w-4 h-4 fill-current" />
                )}
              </button>
              <div className="flex-1">
                <CanvasWaveform
                  peaks={analysis?.waveform ?? previewWaveform}
                  progressRatio={durationSec > 0 ? playheadSec / durationSec : 0}
                  height={68}
                  onSeekRatio={(r) => seek(r * durationSec)}
                />
              </div>
              <div className="text-xs font-mono text-slate-300 w-24 text-right shrink-0">
                {playheadSec.toFixed(1)}s / {durationSec.toFixed(1)}s
              </div>
            </div>
          </div>

          {/* 2. Real-Time Lock-Free Rust Multi-Stem Mixer (MIX-01, MIX-02, MIX-03) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#6C63FF]" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                  Real-Time Lock-Free Rust Multi-Stem Mixer (&lt; 15 ms Latency)
                </h3>
              </div>
              <button
                type="button"
                onClick={resetStems}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#0F1016] border border-[#25293A] text-xs text-slate-300 hover:text-white transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Gains (100%)
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {stems.map((stem) => (
                <StemMixerStrip
                  key={stem.name}
                  stem={stem}
                  onGainChange={(g) => setStemGain(stem.name, g)}
                  onToggleMute={() => toggleMute(stem.name)}
                  onToggleSolo={() => toggleSolo(stem.name)}
                  onExportMidi={() => exportStemMidi(stem.name)}
                />
              ))}
            </div>

            {/* Export Mix & Export Separate Adjusted Stems Bar (MIX-03) */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-[#25293A] text-xs">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Export Format:</span>
                <select
                  value={exportFormat}
                  onChange={(e) => setExportFormat(e.target.value as "wav" | "flac" | "mp3")}
                  className="bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                >
                  <option value="wav">WAV (16-bit PCM)</option>
                  <option value="flac">FLAC (Lossless)</option>
                  <option value="mp3">MP3 (LAME)</option>
                </select>

                {exportFormat === "mp3" && (
                  <select
                    value={exportBitrate}
                    onChange={(e) =>
                      setExportBitrate(e.target.value as "128k" | "192k" | "256k" | "320k")
                    }
                    className="bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                  >
                    <option value="128k">128 kbps</option>
                    <option value="192k">192 kbps</option>
                    <option value="256k">256 kbps</option>
                    <option value="320k">320 kbps</option>
                  </select>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={exportSeparateStems}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#0F1016] border border-[#25293A] hover:border-[#6C63FF] text-slate-200 font-semibold transition"
                >
                  <Download className="w-3.5 h-3.5 text-[#6C63FF]" />
                  <span>{t.btn_export_separate} (*_custom.{exportFormat})</span>
                </button>

                <button
                  type="button"
                  onClick={exportMix}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-[#6C63FF] to-[#00D4AA] text-slate-950 font-bold transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>
                    {t.btn_export_mix} (stem_mix.{exportFormat})
                  </span>
                </button>
              </div>
            </div>

            {lastExportMessage && (
              <div className="rounded-lg bg-[#00D4AA]/15 border border-[#00D4AA]/40 px-3 py-2 text-xs text-[#00D4AA] font-mono">
                {lastExportMessage}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
