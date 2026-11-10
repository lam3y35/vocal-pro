import React, { useState } from "react";
import {
  AudioWaveform,
  BookmarkPlus,
  CheckCircle2,
  Download,
  FileAudio,
  FileVideo,
  Film,
  FolderOpen,
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
import { invokeCommand } from "../ipc";
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
  const [downloadCustomNameInput, setDownloadCustomNameInput] = useState("");
  const [presetNameInput, setPresetNameInput] = useState("");
  const [previewRatio, setPreviewRatio] = useState(0.22);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const handleBrowse = async () => {
    try {
      const picked = await invokeCommand<string[]>("pick_audio_files");
      if (picked && Array.isArray(picked) && picked.length > 0) {
        addFiles(picked);
        return;
      }
    } catch (e) {
      console.warn("pick_audio_files failed, falling back to input:", e);
    }
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const paths: string[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const p = (f as any).path || f.name;
      if (p) paths.push(p);
    }
    if (paths.length > 0) {
      addFiles(paths);
    }
    e.target.value = "";
  };

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

            {/* Hidden Native File Input */}
            <input
              type="file"
              ref={fileInputRef}
              multiple
              accept="audio/*,video/*,.mp3,.wav,.flac,.m4a,.aac,.ogg,.opus,.wma,.mp4,.mkv,.avi,.mov,.webm,.flv,.wmv"
              className="hidden"
              onChange={handleFileInputChange}
            />

            {/* Add Local Path / Browse Buttons */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newFilePath}
                onChange={(e) => setNewFilePath(e.target.value)}
                placeholder="Paste audio/video path or click Browse..."
                className="flex-1 bg-[#0F1016] border border-[#25293A] rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-[#6C63FF]"
              />
              <button
                type="button"
                onClick={handleBrowse}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0F1016] border border-[#25293A] hover:border-[#6C63FF] text-slate-200 text-xs font-semibold transition"
              >
                <FolderOpen className="w-3.5 h-3.5 text-[#6C63FF]" />
                <span>Browse</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  if (newFilePath.trim()) {
                    addFiles([newFilePath.trim()]);
                    setNewFilePath("");
                  } else {
                    void handleBrowse();
                  }
                }}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#6C63FF] text-white text-xs font-semibold hover:bg-[#6C63FF]/90 transition"
              >
                <Plus className="w-3.5 h-3.5" />
                Add
              </button>
            </div>

            {/* Dropzone when queue is empty */}
            {selectedFiles.length === 0 && (
              <div
                onClick={handleBrowse}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  const files = e.dataTransfer.files;
                  if (files && files.length > 0) {
                    const paths: string[] = [];
                    for (let i = 0; i < files.length; i++) {
                      const p = (files[i] as any).path || files[i].name;
                      if (p) paths.push(p);
                    }
                    if (paths.length > 0) addFiles(paths);
                  }
                }}
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${
                  isDragging
                    ? "border-[#00D4AA] bg-[#00D4AA]/10"
                    : "border-[#25293A] bg-[#0F1016]/60 hover:border-[#6C63FF]"
                }`}
              >
                <FolderOpen className="w-8 h-8 text-[#6C63FF] mx-auto mb-2 opacity-80" />
                <p className="text-xs font-semibold text-slate-200">
                  Click to browse or drag &amp; drop Movie or Audio files
                </p>
                <p className="text-[11px] text-slate-500 mt-1">
                  MP4, MKV, AVI, MOV, WEBM (Cinema Movies) • MP3, AAC, FLAC, WAV
                </p>
              </div>
            )}

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
                        aria-label={`Remove ${filePath.split(/[\\/]/).pop()} from queue`}
                        onClick={() => removeFile(filePath)}
                        className="text-slate-400 hover:text-[#FF5E7E] transition"
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
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <Download className="w-4 h-4 text-[#6C63FF]" />
                <span>{t.download_card_title}</span>
              </h3>
              <span className="text-[11px] font-mono text-slate-400">
                Preserves Original Web Media Filename
              </span>
            </div>
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="url"
                  value={downloadUrlInput}
                  onChange={(e) => setDownloadUrlInput(e.target.value)}
                  placeholder="https://example.com/movie.mp4 or direct audio URL"
                  className="flex-1 bg-[#0F1016] border border-[#25293A] rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-[#6C63FF]"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (downloadUrlInput.trim()) {
                      downloadMediaUrl(downloadUrlInput.trim(), downloadCustomNameInput.trim());
                      setDownloadUrlInput("");
                      setDownloadCustomNameInput("");
                    }
                  }}
                  className="px-3 py-1.5 rounded-lg bg-[#00D4AA] text-slate-950 text-xs font-bold hover:opacity-90 transition shrink-0"
                >
                  Fetch &amp; Queue
                </button>
              </div>
              <input
                type="text"
                value={downloadCustomNameInput}
                onChange={(e) => setDownloadCustomNameInput(e.target.value)}
                placeholder="Optional custom title/filename (auto-extracted from web server if blank)..."
                className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-3 py-1 text-[11px] text-slate-300 font-mono focus:outline-none focus:border-[#6C63FF]"
              />
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
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <Film className="w-4 h-4 text-[#00D4AA]" />
                <span>Export Target &amp; Movie Mode</span>
              </h2>
              <span className="text-[11px] font-mono text-[#00D4AA]">
                Zero Quality Loss • 1:1 Timeline Sync
              </span>
            </div>

            {/* 1. Export Target: Movie Video Only vs Audio Stems Only vs Both */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <button
                type="button"
                onClick={() => setOptions({ video_output_mode: "video_only", output_video: true })}
                className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
                  options.video_output_mode === "video_only"
                    ? "bg-[#00D4AA]/15 border-[#00D4AA] text-white"
                    : "bg-[#0F1016] border-[#25293A] text-slate-400 hover:border-slate-600"
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-bold text-xs flex items-center gap-1.5 text-white">
                    <FileVideo className="w-4 h-4 text-[#00D4AA]" />
                    <span>Clean Movie Only</span>
                  </span>
                  {options.video_output_mode === "video_only" && (
                    <span className="w-2 h-2 rounded-full bg-[#00D4AA]" />
                  )}
                </div>
                <p className="text-[10px] text-slate-400 mt-1.5 leading-snug">
                  Muxes clean audio into movie container. Purges temp stems to save disk storage.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setOptions({ video_output_mode: "audio_only", output_video: false })}
                className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
                  options.video_output_mode === "audio_only"
                    ? "bg-[#6C63FF]/20 border-[#6C63FF] text-white"
                    : "bg-[#0F1016] border-[#25293A] text-slate-400 hover:border-slate-600"
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-bold text-xs flex items-center gap-1.5 text-white">
                    <FileAudio className="w-4 h-4 text-[#6C63FF]" />
                    <span>Audio Stems Only</span>
                  </span>
                  {options.video_output_mode === "audio_only" && (
                    <span className="w-2 h-2 rounded-full bg-[#6C63FF]" />
                  )}
                </div>
                <p className="text-[10px] text-slate-400 mt-1.5 leading-snug">
                  Extracts dialogue, music, and SFX as compact audio files (~5MB). No video output.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setOptions({ video_output_mode: "both", output_video: true })}
                className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
                  options.video_output_mode === "both"
                    ? "bg-[#FFB800]/15 border-[#FFB800] text-white"
                    : "bg-[#0F1016] border-[#25293A] text-slate-400 hover:border-slate-600"
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className="font-bold text-xs flex items-center gap-1.5 text-white">
                    <Layers className="w-4 h-4 text-[#FFB800]" />
                    <span>Both Movie + Audio</span>
                  </span>
                  {options.video_output_mode === "both" && (
                    <span className="w-2 h-2 rounded-full bg-[#FFB800]" />
                  )}
                </div>
                <p className="text-[10px] text-slate-400 mt-1.5 leading-snug">
                  Produces clean remuxed movie video alongside all separated audio stems.
                </p>
              </button>
            </div>

            {/* 2. Option to Delete Original Input File */}
            <label className="flex items-center justify-between p-3 rounded-xl bg-[#0F1016] border border-[#25293A] hover:border-[#FF5E7E]/50 transition cursor-pointer">
              <div className="flex items-center gap-3">
                <Trash2 className="w-4 h-4 text-[#FF5E7E] shrink-0" />
                <div>
                  <span className="text-xs font-semibold text-slate-200">
                    Delete original input file after successful export
                  </span>
                  <p className="text-[11px] text-slate-400">
                    Safely removes original movie/audio file once output is written and verified, freeing disk space immediately.
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={Boolean(options.delete_input_file)}
                onChange={(e) => setOptions({ delete_input_file: e.target.checked })}
                className="w-4 h-4 accent-[#FF5E7E] cursor-pointer"
              />
            </label>

            {/* 3. Output Mode, Audio Format (Storage Saver), and Device */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <label className="space-y-1">
                <span className="text-slate-400">Audio / Dialogue Target</span>
                <select
                  value={options.output_mode}
                  onChange={(e) => setOptions({ output_mode: e.target.value as OutputMode })}
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                >
                  <option value="vocals">Clean Dialogue / Vocals</option>
                  <option value="background">Background Score &amp; SFX (No Dialogue)</option>
                  <option value="karaoke">Karaoke Instrumental</option>
                  <option value="all_stems">All Stems (Dialogue, Music, Drums, Bass)</option>
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Audio Format &amp; Storage Footprint</span>
                <select
                  value={options.output_format}
                  onChange={(e) => setOptions({ output_format: e.target.value as OutputFormat })}
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100 font-mono text-xs"
                >
                  <option value="mp3">MP3 320k (Studio Quality ~5-7 MB)</option>
                  <option value="aac">AAC 320k (Cinema Master ~5-7 MB)</option>
                  <option value="flac">FLAC (24-bit Lossless ~18 MB)</option>
                  <option value="wav">WAV (16-bit Uncompressed ~35 MB)</option>
                </select>
              </label>

              <label className="space-y-1">
                <span className="text-slate-400">Inference Device</span>
                <select
                  value={options.device}
                  onChange={(e) => setOptions({ device: e.target.value as DeviceOption })}
                  className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-100"
                >
                  <option value="auto">Auto (Highest Performance GPU)</option>
                  <option value="cuda">NVIDIA CUDA GPU (Fastest)</option>
                  <option value="cpu">CPU Multi-Threaded</option>
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
              <div className="flex items-center gap-2 flex-1 min-w-[280px]">
                <FolderOutput className="w-4 h-4 text-slate-400 shrink-0" />
                <input
                  type="text"
                  value={customOutputDir}
                  onChange={(e) => setCustomOutputDir(e.target.value)}
                  placeholder="Default: <Music>/VocalPro or <input_folder>/output_vocals"
                  className="flex-1 bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5 text-slate-200 font-mono text-[11px]"
                />
                <button
                  type="button"
                  onClick={async () => {
                    const picked = await invokeCommand<string | null>("pick_output_dir");
                    if (picked) setCustomOutputDir(picked);
                  }}
                  className="px-2.5 py-1.5 rounded-lg bg-[#0F1016] border border-[#25293A] hover:border-[#6C63FF] text-slate-200 text-xs font-semibold transition"
                >
                  Browse...
                </button>
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
