import React, { useState } from "react";
import {
  AudioWaveform,
  BookmarkPlus,
  Download,
  FileAudio,
  FileVideo,
  FolderOutput,
  Layers,
  Play,
  Plus,
  Sparkles,
  Terminal,
  Trash2,
} from "lucide-react";
import { DeviceOption, ModelName, OutputFormat, OutputMode, VideoOutputMode } from "../bindings";
import { CanvasWaveform } from "../components/CanvasWaveform";
import { JobQueueBar } from "../components/JobQueueBar";
import { TRANSLATIONS } from "../i18n/translations";
import { useJobsStore, useLibraryStore, useSystemStore } from "../state/appStores";

export const SeparationScreen: React.FC = () => {
  const locale = useSystemStore((s) => s.locale);
  const models = useSystemStore((s) => s.models);
  const t = TRANSLATIONS[locale];

  const selectedFiles = useJobsStore((s) => s.selectedFiles);
  const addFiles = useJobsStore((s) => s.addFiles);
  const removeFile = useJobsStore((s) => s.removeFile);
  const clearFiles = useJobsStore((s) => s.clearFiles);
  const options = useJobsStore((s) => s.options);
  const setOptions = useJobsStore((s) => s.setOptions);
  const toggleSongMode = useJobsStore((s) => s.toggleSongMode);
  const customOutputDir = useJobsStore((s) => s.customOutputDir);
  const setCustomOutputDir = useJobsStore((s) => s.setCustomOutputDir);
  const parallelWorkers = useJobsStore((s) => s.parallelWorkers);
  const setParallelWorkers = useJobsStore((s) => s.setParallelWorkers);
  const autoOpenFolder = useJobsStore((s) => s.autoOpenFolder);
  const setAutoOpenFolder = useJobsStore((s) => s.setAutoOpenFolder);
  const previewWaveform = useJobsStore((s) => s.previewWaveform);
  const startSeparationBatch = useJobsStore((s) => s.startSeparationBatch);
  const logs = useJobsStore((s) => s.logs);
  const jobs = useJobsStore((s) => s.jobs);

  const presets = useLibraryStore((s) => s.presets);
  const savePreset = useLibraryStore((s) => s.savePreset);
  const deletePreset = useLibraryStore((s) => s.deletePreset);
  const downloadMediaUrl = useLibraryStore((s) => s.downloadMediaUrl);

  const [newFilePath, setNewFilePath] = useState("");
  const [downloadUrlInput, setDownloadUrlInput] = useState("");
  const [presetNameInput, setPresetNameInput] = useState("");
  const [previewRatio, setPreviewRatio] = useState(0.22);

  return (
    <div className="space-y-5 pb-10">
      {/* Multi-Job Tab Strip & Live Per-Segment Progress (JobTabCard + RunCard parity) */}
      <JobQueueBar />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Left Column: File Queue + Waveform Preview + URL Downloader + Logs */}
        <div className="xl:col-span-5 space-y-5">
          {/* 1. File Queue Card (FileCard parity + per-file progress) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-3.5">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <FileAudio className="w-4 h-4 text-[#6C63FF]" />
                <span>Input Audio &amp; Video Queue ({selectedFiles.length})</span>
              </h2>
              {selectedFiles.length > 0 && (
                <button
                  type="button"
                  onClick={clearFiles}
                  className="text-[11px] text-[#FF5E7E] hover:underline"
                >
                  Clear All
                </button>
              )}
            </div>

            {/* Add Local Path / Drag & Drop Zone */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newFilePath}
                onChange={(e) => setNewFilePath(e.target.value)}
                placeholder="Paste audio/video path (.mp3, .wav, .flac, .mp4, .mkv)..."
                className="flex-1 bg-[#0F1016] border border-[#25293A] rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-[#6C63FF]"
              />
              <button
                type="button"
                onClick={() => {
                  if (newFilePath.trim()) {
                    addFiles([newFilePath.trim()]);
                    setNewFilePath("");
                  }
                }}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#6C63FF] text-white text-xs font-semibold hover:bg-[#6C63FF]/90 transition"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </div>

            {/* Queued Files List with Per-File Progress */}
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {selectedFiles.map((filePath) => {
                const isVideo = /\.(mp4|mkv|avi|mov|webm|flv|wmv)$/i.test(filePath);
                const matchingJob = jobs.find((j) => j.input_path === filePath);
                return (
                  <div
                    key={filePath}
                    className="rounded-lg bg-[#0F1016] border border-[#25293A] p-2.5 space-y-1.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {isVideo ? (
                          <FileVideo className="w-4 h-4 text-[#FFB800] shrink-0" />
                        ) : (
                          <FileAudio className="w-4 h-4 text-[#00D4AA] shrink-0" />
                        )}
                        <span className="text-xs text-slate-200 truncate font-mono">
                          {filePath.split(/[\\/]/).pop()}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#161822] text-slate-400 uppercase font-mono">
                          {isVideo ? "VIDEO" : "AUDIO"}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(filePath)}
                        className="text-slate-500 hover:text-[#FF5E7E] transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    {matchingJob && (
                      <div className="w-full h-1.5 rounded-full bg-[#161822] overflow-hidden">
                        <div
                          className="h-full bg-[#00D4AA] transition-all duration-200"
                          style={{ width: `${matchingJob.percent}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 2. Waveform Preview Card (Fixes P-16: WaveformCard rendered visibly on SeparationScreen!) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <AudioWaveform className="w-4 h-4 text-[#00D4AA]" />
                <span>Native Rust 8,000-Point Input Waveform Preview</span>
              </span>
              <span className="text-[11px] font-mono text-[#00D4AA]">
                Symphonia Decode &lt; 25 ms
              </span>
            </div>
            <CanvasWaveform
              peaks={previewWaveform}
              progressRatio={previewRatio}
              height={72}
              onSeekRatio={setPreviewRatio}
            />
          </div>

          {/* 3. Direct Media URL Downloader Card (DownloadCard parity) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Download className="w-4 h-4 text-[#6C63FF]" />
              <span>{t.download_card_title}</span>
            </h3>
            <div className="flex gap-2">
              <input
                type="url"
                value={downloadUrlInput}
                onChange={(e) => setDownloadUrlInput(e.target.value)}
                placeholder="https://example.com/audio/track.mp3"
                className="flex-1 bg-[#0F1016] border border-[#25293A] rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-[#6C63FF]"
              />
              <button
                type="button"
                onClick={() => {
                  if (downloadUrlInput.trim()) {
                    downloadMediaUrl(downloadUrlInput.trim());
                    setDownloadUrlInput("");
                  }
                }}
                className="px-3 py-1.5 rounded-lg bg-[#00D4AA] text-slate-950 text-xs font-bold hover:opacity-90 transition"
              >
                Fetch &amp; Queue
              </button>
            </div>
          </div>

          {/* 4. Engine & Worker Live Log Card (LogCard parity) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-[#FFB800]" />
              <span>{t.log_card_title}</span>
            </h3>
            <div className="rounded-lg bg-[#0F1016] border border-[#25293A] p-3 h-36 overflow-y-auto font-mono text-[11px] text-slate-300 space-y-1">
              {logs.map((line, idx) => (
                <div key={idx} className="leading-relaxed">
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: SongModeCard + ModelCard + OptionsCard + Run Button */}
        <div className="xl:col-span-7 space-y-5">
          {/* 1. Song Mode 1-Click Studio Preset Card (SongModeCard parity) */}
          <div className="rounded-xl bg-gradient-to-r from-[#6C63FF]/15 to-[#00D4AA]/10 border border-[#6C63FF]/40 p-4 flex items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <Sparkles className="w-4 h-4 text-[#00D4AA]" />
                <span>{t.song_mode_title}</span>
              </div>
              <p className="text-[11px] text-slate-300">{t.song_mode_desc}</p>
            </div>
            <input
              type="checkbox"
              checked={options.song_mode}
              onChange={(e) => toggleSongMode(e.target.checked)}
              className="w-5 h-5 accent-[#00D4AA] cursor-pointer"
            />
          </div>

          {/* 2. AI Model & Ensemble Selector Card (ModelCard parity) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#6C63FF]" />
                <span>AI Separation Model &amp; Ensemble Mode</span>
              </h2>
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.ensemble_mode}
                  onChange={(e) => setOptions({ ensemble_mode: e.target.checked })}
                  className="accent-[#6C63FF]"
                />
                <span>Ensemble Mode (Average htdemucs_ft + mdx_extra)</span>
              </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {models.map((m) => {
                const selected = options.model === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() =>
                      setOptions({
                        model: m.id as ModelName,
                        output_all_stems: m.id === "htdemucs_6s" ? true : options.output_all_stems,
                      })
                    }
                    className={`text-left rounded-xl p-3 border transition ${
                      selected
                        ? "bg-[#6C63FF]/20 border-[#6C63FF] text-white"
                        : "bg-[#0F1016] border-[#25293A] text-slate-300 hover:border-slate-600"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-xs">{m.id}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#161822] text-[#00D4AA] font-mono">
                        {m.stems.length} stems
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1 line-clamp-1">
                      {m.display_name}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. Comprehensive Job Options & DSP Post-Processing Card (OptionsCard parity) */}
          <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 space-y-4">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Output Mode, Format, Inference &amp; Vocal Post-Processing
            </h2>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <label className="space-y-1">
                <span className="text-slate-400">Output Mode</span>
                <select
                  value={options.output_mode}
                  onChange={(e) => setOptions({ output_mode: e.target.value as OutputMode })}
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                >
                  <option value="vocals">Vocals Primary</option>
                  <option value="background">Background / Music</option>
                  <option value="karaoke">Karaoke Instrumental</option>
                  <option value="all_stems">All Stems (4/6 Stems)</option>
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Audio Format</span>
                <select
                  value={options.output_format}
                  onChange={(e) => setOptions({ output_format: e.target.value as OutputFormat })}
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                >
                  <option value="wav">WAV (16-bit PCM)</option>
                  <option value="flac">FLAC (Lossless)</option>
                  <option value="mp3">MP3 (LAME)</option>
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Device</span>
                <select
                  value={options.device}
                  onChange={(e) => setOptions({ device: e.target.value as DeviceOption })}
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                >
                  <option value="auto">Auto (CUDA / CPU)</option>
                  <option value="cuda">NVIDIA CUDA GPU</option>
                  <option value="cpu">CPU Only</option>
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Video Remux Mode</span>
                <select
                  value={options.video_output_mode}
                  onChange={(e) =>
                    setOptions({ video_output_mode: e.target.value as VideoOutputMode })
                  }
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                >
                  <option value="both">Both (Clean MP4 + Audio)</option>
                  <option value="video_only">Clean Video Only (_clean.mp4)</option>
                  <option value="audio_only">Audio Stems Only</option>
                </select>
              </label>
            </div>

            {/* Shifts, Segment, Overlap, Parallel Workers */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <label className="space-y-1">
                <span className="text-slate-400">Random Shifts ({options.shifts})</span>
                <input
                  type="range"
                  min={0}
                  max={10}
                  step={1}
                  value={options.shifts}
                  onChange={(e) => setOptions({ shifts: parseInt(e.target.value, 10) })}
                  className="w-full accent-[#6C63FF]"
                />
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Segment ({options.segment ?? 6}s)</span>
                <input
                  type="range"
                  min={2}
                  max={30}
                  step={1}
                  value={options.segment ?? 6}
                  onChange={(e) => setOptions({ segment: parseFloat(e.target.value) })}
                  className="w-full accent-[#6C63FF]"
                />
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Overlap ({options.overlap})</span>
                <input
                  type="range"
                  min={0.1}
                  max={0.75}
                  step={0.05}
                  value={options.overlap > 1 ? 0.25 : options.overlap}
                  onChange={(e) => setOptions({ overlap: parseFloat(e.target.value) })}
                  className="w-full accent-[#6C63FF]"
                />
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Parallel Workers ({parallelWorkers})</span>
                <input
                  type="range"
                  min={1}
                  max={4}
                  step={1}
                  value={parallelWorkers}
                  onChange={(e) => setParallelWorkers(parseInt(e.target.value, 10))}
                  className="w-full accent-[#00D4AA]"
                />
              </label>
            </div>

            {/* DSP & Stem Toggles */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs pt-1">
              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.output_all_stems}
                  onChange={(e) => setOptions({ output_all_stems: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>Save All Instrument Stems (SEP-09)</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.enable_vocal_gate}
                  onChange={(e) => setOptions({ enable_vocal_gate: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>VAD Vocal Activity Gate</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.enable_spectral_denoise}
                  onChange={(e) => setOptions({ enable_spectral_denoise: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>Spectral Denoise + 8kHz Air</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.enable_multiband_denoise}
                  onChange={(e) => setOptions({ enable_multiband_denoise: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>3-Band Multi-Band Denoise</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.enable_sfx_separation}
                  onChange={(e) => setOptions({ enable_sfx_separation: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>HPSS SFX Separation</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.include_sfx}
                  onChange={(e) => setOptions({ include_sfx: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>Mix SFX Back (0.95v + 0.70sfx)</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.save_background_track}
                  onChange={(e) => setOptions({ save_background_track: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>Save Background Music Track</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.karaoke_mode}
                  onChange={(e) => setOptions({ karaoke_mode: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>Save Karaoke Track (_karaoke.wav)</span>
              </label>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={options.generate_comparison_samples}
                  onChange={(e) => setOptions({ generate_comparison_samples: e.target.checked })}
                  className="accent-[#00D4AA]"
                />
                <span>Generate 3 A/B Comparison Clips</span>
              </label>
            </div>

            {/* Custom Output Directory & Auto-Open Folder */}
            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[#25293A] text-xs">
              <div className="flex items-center gap-2 flex-1 min-w-[240px]">
                <FolderOutput className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  type="text"
                  value={customOutputDir}
                  onChange={(e) => setCustomOutputDir(e.target.value)}
                  placeholder="Default: <input_folder>/output_vocals/<track_name>"
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-200 font-mono text-[11px]"
                />
              </div>
              <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoOpenFolder}
                  onChange={(e) => setAutoOpenFolder(e.target.checked)}
                  className="accent-[#6C63FF]"
                />
                <span>Auto-open folder when done</span>
              </label>
            </div>

            {/* Presets Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#25293A] text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-slate-400 mr-1">Presets:</span>
                {presets.map((p) => (
                  <div key={p.name} className="inline-flex items-center rounded-lg bg-[#0F1016] border border-[#25293A]">
                    <button
                      type="button"
                      onClick={() => setOptions(p.options)}
                      className="px-2.5 py-1 text-[11px] text-slate-200 hover:text-[#00D4AA]"
                    >
                      {p.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => deletePreset(p.name)}
                      className="px-1.5 py-1 text-slate-500 hover:text-[#FF5E7E] border-l border-[#25293A]"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  value={presetNameInput}
                  onChange={(e) => setPresetNameInput(e.target.value)}
                  placeholder="New preset name..."
                  className="bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1 text-[11px] text-slate-200 w-36"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (presetNameInput.trim()) {
                      savePreset(presetNameInput.trim(), options);
                      setPresetNameInput("");
                    }
                  }}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#6C63FF]/20 border border-[#6C63FF]/40 text-[#6C63FF] text-[11px] font-semibold"
                >
                  <BookmarkPlus className="w-3.5 h-3.5" />
                  Save
                </button>
              </div>
            </div>
          </div>

          {/* Primary Start Separation CTA */}
          <button
            type="button"
            onClick={startSeparationBatch}
            disabled={selectedFiles.length === 0}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-[#6C63FF] to-[#00D4AA] text-slate-950 font-bold text-sm shadow-lg shadow-[#6C63FF]/30 hover:opacity-95 disabled:opacity-40 flex items-center justify-center gap-2 transition"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>
              {t.btn_start_separation} ({selectedFiles.length}{" "}
              {selectedFiles.length === 1 ? "File" : "Files"} • {options.model})
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};
