import React from "react";
import {
  Archive,
  Check,
  Cpu,
  FileCheck2,
  Gauge,
  Monitor,
  RotateCcw,
  Sliders,
  Sparkles,
  Wrench,
  Zap,
} from "lucide-react";
import { DEFAULT_JOB_OPTIONS, WavBitDepth } from "../bindings";
import { useJobsStore, useSystemStore } from "../state/appStores";

export const SettingsScreen: React.FC = () => {
  const options = useJobsStore((s) => s.options);
  const setOptions = useJobsStore((s) => s.setOptions);
  const parallelWorkers = useJobsStore((s) => s.parallelWorkers);
  const setParallelWorkers = useJobsStore((s) => s.setParallelWorkers);

  const alwaysOnTop = useSystemStore((s) => s.alwaysOnTop);
  const minimizeToTray = useSystemStore((s) => s.minimizeToTray);
  const systemBanner = useSystemStore((s) => s.systemBanner);
  const hardwareProfile = useSystemStore((s) => s.hardwareProfile);
  const health = useSystemStore((s) => s.health);
  const setAlwaysOnTop = useSystemStore((s) => s.setAlwaysOnTop);
  const setMinimizeToTray = useSystemStore((s) => s.setMinimizeToTray);
  const registerFileAssociations = useSystemStore((s) => s.registerFileAssociations);
  const createDesktopShortcut = useSystemStore((s) => s.createDesktopShortcut);
  const exportDiagnosticBundle = useSystemStore((s) => s.exportDiagnosticBundle);
  const autoOptimizeForHardware = useSystemStore((s) => s.autoOptimizeForHardware);

  return (
    <div className="space-y-5 pb-12">
      {systemBanner && (
        <div className="rounded-xl bg-[#00D4AA]/15 border border-[#00D4AA]/40 px-4 py-3 text-xs text-[#00D4AA] flex items-center gap-2 font-mono">
          <Check className="w-4 h-4 shrink-0" />
          <span>{systemBanner}</span>
        </div>
      )}

      {/* 0. Hardware Intelligence & Multi-Process Device Auto-Optimizer */}
      <div className="rounded-xl bg-gradient-to-r from-[#161822] via-[#1A1D2B] to-[#161822] border border-[#6C63FF]/40 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[#00D4AA]" />
              <span>Hardware Intelligence &amp; Multi-Process Device Optimizer</span>
              <span className="px-2 py-0.5 rounded-full bg-[#00D4AA]/15 border border-[#00D4AA]/40 text-[#00D4AA] font-mono text-[10px]">
                {hardwareProfile.tier_label}
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Automatically probes CPU cores, SIMD vector instructions, RAM, and GPU VRAM to tune
              parallel worker processes, thread affinity, and segment size for this machine.
            </p>
          </div>

          <button
            type="button"
            onClick={autoOptimizeForHardware}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#6C63FF] to-[#00D4AA] text-slate-950 font-bold text-xs shadow-lg hover:opacity-95 transition"
          >
            <Zap className="w-4 h-4" />
            <span>Auto-Optimize for This Device</span>
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="rounded-lg bg-[#0F1016] border border-[#25293A] p-3">
            <div className="text-slate-400 text-[11px]">Detected Processor</div>
            <div className="text-white font-semibold truncate mt-0.5">
              {hardwareProfile.cpu_model}
            </div>
            <div className="text-[11px] text-[#00D4AA] font-mono mt-1">
              {hardwareProfile.physical_cores}C / {hardwareProfile.logical_cores}T •{" "}
              {hardwareProfile.simd_features.join(" + ")}
            </div>
          </div>

          <div className="rounded-lg bg-[#0F1016] border border-[#25293A] p-3">
            <div className="text-slate-400 text-[11px]">GPU Accelerator</div>
            <div className="text-white font-semibold truncate mt-0.5">
              {hardwareProfile.gpu_name || "CPU AVX2 Vector Engine"}
            </div>
            <div className="text-[11px] text-[#6C63FF] font-mono mt-1">
              {hardwareProfile.vram_mb ? `${hardwareProfile.vram_mb} MB VRAM` : "Shared RAM"} •
              FP16 {hardwareProfile.fp16_supported ? "Supported" : "N/A"}
            </div>
          </div>

          <div className="rounded-lg bg-[#0F1016] border border-[#25293A] p-3">
            <div className="text-slate-400 text-[11px]">System Memory &amp; Disk</div>
            <div className="text-white font-semibold mt-0.5">
              {(hardwareProfile.total_ram_mb / 1024).toFixed(1)} GB RAM (
              {(hardwareProfile.available_ram_mb / 1024).toFixed(1)} GB Free)
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-1">
              Disk Free: {hardwareProfile.disk_free_gb} GB
            </div>
          </div>

          <div className="rounded-lg bg-[#0F1016] border border-[#25293A] p-3">
            <div className="text-slate-400 text-[11px]">Simultaneous Worker Processes</div>
            <div className="flex items-center gap-1.5 mt-1">
              {[1, 2, 3, 4].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setParallelWorkers(n)}
                  className={`px-2.5 py-1 rounded font-mono text-xs font-bold border transition ${
                    parallelWorkers === n
                      ? "bg-[#00D4AA]/20 border-[#00D4AA] text-[#00D4AA]"
                      : "bg-[#161822] border-[#25293A] text-slate-400 hover:text-white"
                  }`}
                >
                  {n}x
                </button>
              ))}
            </div>
            <div className="text-[10px] text-slate-400 font-mono mt-1">
              Recommended: {hardwareProfile.recommended_max_concurrent_jobs}x processes (
              {health.slots?.length || parallelWorkers} warm)
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* 1. Vocal Gate, Denoise & Multi-Band DSP Parameters */}
        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-5 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
            <Sliders className="w-4 h-4 text-[#6C63FF]" />
            <span>Vocal Gate, Spectral Denoise &amp; 3-Band Crossover Parameters</span>
          </h2>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <label className="space-y-1">
              <span className="text-slate-400">
                Gate Threshold ({options.gate_threshold_db} dB)
              </span>
              <input
                type="range"
                min={-70}
                max={-20}
                step={1}
                value={options.gate_threshold_db}
                onChange={(e) => setOptions({ gate_threshold_db: parseFloat(e.target.value) })}
                className="w-full accent-[#6C63FF]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">Gate Floor ({options.gate_floor_db} dB)</span>
              <input
                type="range"
                min={-90}
                max={0}
                step={1}
                value={options.gate_floor_db}
                onChange={(e) => setOptions({ gate_floor_db: parseFloat(e.target.value) })}
                className="w-full accent-[#6C63FF]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Single-Band Denoise Strength ({options.denoise_strength})
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={options.denoise_strength}
                onChange={(e) => setOptions({ denoise_strength: parseFloat(e.target.value) })}
                className="w-full accent-[#00D4AA]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Min Vocal Duration ({options.min_vocal_duration}s)
              </span>
              <input
                type="range"
                min={0.01}
                max={0.5}
                step={0.01}
                value={options.min_vocal_duration}
                onChange={(e) => setOptions({ min_vocal_duration: parseFloat(e.target.value) })}
                className="w-full accent-[#00D4AA]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Low Band &lt;250Hz Denoise ({options.denoise_strength_low})
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={options.denoise_strength_low}
                onChange={(e) => setOptions({ denoise_strength_low: parseFloat(e.target.value) })}
                className="w-full accent-[#6C63FF]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Mid Band 250–6kHz Denoise ({options.denoise_strength_mid})
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={options.denoise_strength_mid}
                onChange={(e) => setOptions({ denoise_strength_mid: parseFloat(e.target.value) })}
                className="w-full accent-[#6C63FF]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                High Band &gt;6kHz Denoise ({options.denoise_strength_high})
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={options.denoise_strength_high}
                onChange={(e) => setOptions({ denoise_strength_high: parseFloat(e.target.value) })}
                className="w-full accent-[#6C63FF]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                8kHz High-Shelf Air Boost (+{options.hf_boost_db} dB)
              </span>
              <input
                type="range"
                min={0}
                max={6}
                step={0.5}
                value={options.hf_boost_db}
                onChange={(e) => setOptions({ hf_boost_db: parseFloat(e.target.value) })}
                className="w-full accent-[#00D4AA]"
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-4 pt-2 border-t border-[#25293A] text-xs">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={options.enable_noise_profile}
                onChange={(e) => setOptions({ enable_noise_profile: e.target.checked })}
                className="accent-[#00D4AA]"
              />
              <span>Auto-Extract VAD Silence Noise Profile</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={options.adaptive_gate_floor}
                onChange={(e) => setOptions({ adaptive_gate_floor: e.target.checked })}
                className="accent-[#00D4AA]"
              />
              <span>Adaptive Gate Floor (+3 dB Headroom)</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={options.enable_hf_restore}
                onChange={(e) => setOptions({ enable_hf_restore: e.target.checked })}
                className="accent-[#00D4AA]"
              />
              <span>RBJ High-Shelf Air Restore</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={options.enable_loudness_normalize}
                onChange={(e) => setOptions({ enable_loudness_normalize: e.target.checked })}
                className="accent-[#00D4AA]"
              />
              <span>RMS Loudness Normalization</span>
            </label>
          </div>
        </div>

        {/* 2. HPSS SFX Separation & Large-File Chunking Parameters (Fixes P-18) */}
        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-5 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#00D4AA]" />
            <span>HPSS SFX Separation &amp; Large-File OLA Chunking</span>
          </h2>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <label className="space-y-1">
              <span className="text-slate-400">
                SFX Separation Margin ({options.sfx_separation_margin_db} dB)
              </span>
              <input
                type="range"
                min={1}
                max={15}
                step={0.5}
                value={options.sfx_separation_margin_db}
                onChange={(e) =>
                  setOptions({ sfx_separation_margin_db: parseFloat(e.target.value) })
                }
                className="w-full accent-[#00D4AA]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                HPSS Median Kernel Size ({options.sfx_kernel_size})
              </span>
              <input
                type="range"
                min={3}
                max={51}
                step={2}
                value={options.sfx_kernel_size}
                onChange={(e) => setOptions({ sfx_kernel_size: parseInt(e.target.value, 10) })}
                className="w-full accent-[#00D4AA]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Harmonic Margin ({options.sfx_margin_harmonic_db} dB)
              </span>
              <input
                type="range"
                min={0.5}
                max={15}
                step={0.5}
                value={options.sfx_margin_harmonic_db}
                onChange={(e) =>
                  setOptions({ sfx_margin_harmonic_db: parseFloat(e.target.value) })
                }
                className="w-full accent-[#6C63FF]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Percussive Margin ({options.sfx_margin_percussive_db} dB)
              </span>
              <input
                type="range"
                min={0.5}
                max={15}
                step={0.5}
                value={options.sfx_margin_percussive_db}
                onChange={(e) =>
                  setOptions({ sfx_margin_percussive_db: parseFloat(e.target.value) })
                }
                className="w-full accent-[#6C63FF]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Large File Threshold ({options.large_file_threshold_minutes} min)
              </span>
              <input
                type="range"
                min={5}
                max={60}
                step={1}
                value={options.large_file_threshold_minutes}
                onChange={(e) =>
                  setOptions({ large_file_threshold_minutes: parseInt(e.target.value, 10) })
                }
                className="w-full accent-[#FFB800]"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Chunk Duration ({options.chunk_duration_minutes} min)
              </span>
              <input
                type="range"
                min={2}
                max={30}
                step={1}
                value={options.chunk_duration_minutes}
                onChange={(e) =>
                  setOptions({ chunk_duration_minutes: parseInt(e.target.value, 10) })
                }
                className="w-full accent-[#FFB800]"
              />
            </label>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-2 border-t border-[#25293A] text-xs">
            <label className="space-y-1">
              <span className="text-slate-400">Chunk Overlap ({options.overlap_seconds}s)</span>
              <input
                type="number"
                min={0}
                max={30}
                value={options.overlap_seconds}
                onChange={(e) => setOptions({ overlap_seconds: parseFloat(e.target.value) || 5 })}
                className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1 text-slate-200"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">Threads / Process (0=Auto)</span>
              <input
                type="number"
                min={0}
                max={64}
                value={options.max_threads}
                onChange={(e) => setOptions({ max_threads: parseInt(e.target.value, 10) || 0 })}
                className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1 text-slate-200"
              />
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">
                Cooldown ({options.cooldown_between_chunks_seconds}s)
              </span>
              <input
                type="number"
                min={0}
                max={60}
                value={options.cooldown_between_chunks_seconds}
                onChange={(e) =>
                  setOptions({ cooldown_between_chunks_seconds: parseFloat(e.target.value) || 0 })
                }
                className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1 text-slate-200"
              />
            </label>
          </div>
        </div>

        {/* 3. Studio Export Bit-Depth, OS File Associations & Window Behavior */}
        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-5 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
            <Monitor className="w-4 h-4 text-[#00D4AA]" />
            <span>Studio Audio Export, OS File Associations &amp; Window Behavior</span>
          </h2>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <label className="space-y-1">
              <span className="text-slate-400 flex items-center gap-1">
                <Gauge className="w-3.5 h-3.5 text-[#6C63FF]" />
                <span>WAV / FLAC Studio Bit Depth</span>
              </span>
              <select
                value={options.wav_bit_depth}
                onChange={(e) => setOptions({ wav_bit_depth: e.target.value as WavBitDepth })}
                className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-2 text-slate-200"
              >
                <option value="PCM_16">16-bit PCM (Standard CD / Broadcast)</option>
                <option value="PCM_24">24-bit PCM (Studio Mastering)</option>
                <option value="FLOAT">32-bit IEEE Float (Zero-Clip Headroom)</option>
              </select>
            </label>

            <label className="space-y-1">
              <span className="text-slate-400">Lossy Bitrate (MP3 / AAC Video)</span>
              <select
                value={options.audio_bitrate}
                onChange={(e) => setOptions({ audio_bitrate: e.target.value })}
                className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-2 text-slate-200"
              >
                <option value="128k">128 kbps (Compact)</option>
                <option value="192k">192 kbps (Standard)</option>
                <option value="256k">256 kbps (High)</option>
                <option value="320k">320 kbps (Archival CBR)</option>
              </select>
            </label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
            <button
              type="button"
              onClick={registerFileAssociations}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#0F1016] border border-[#25293A] hover:border-[#00D4AA] text-slate-200 font-semibold transition"
            >
              <FileCheck2 className="w-4 h-4 text-[#00D4AA]" />
              <span>Register File Associations (.mp3/.wav/.mp4)</span>
            </button>

            <button
              type="button"
              onClick={createDesktopShortcut}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#0F1016] border border-[#25293A] hover:border-[#6C63FF] text-slate-200 font-semibold transition"
            >
              <Monitor className="w-4 h-4 text-[#6C63FF]" />
              <span>Create Desktop Shortcut</span>
            </button>
          </div>

          <div className="flex flex-wrap gap-5 pt-2 border-t border-[#25293A] text-xs">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={alwaysOnTop}
                onChange={(e) => setAlwaysOnTop(e.target.checked)}
                className="accent-[#6C63FF]"
              />
              <span>Window Always on Top</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={minimizeToTray}
                onChange={(e) => setMinimizeToTray(e.target.checked)}
                className="accent-[#6C63FF]"
              />
              <span>Minimize to System Tray</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={options.safe_mode}
                onChange={(e) => setOptions({ safe_mode: e.target.checked })}
                className="accent-[#FFB800]"
              />
              <span>Safe Mode (CPU + 4s Seg)</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={options.auto_oom_fallback}
                onChange={(e) => setOptions({ auto_oom_fallback: e.target.checked })}
                className="accent-[#00D4AA]"
              />
              <span>Auto OOM VRAM-&gt;CPU Recovery</span>
            </label>
          </div>
        </div>

        {/* 4. FFmpeg Path, Diagnostics Bundle Export & Reset Defaults */}
        <div className="rounded-xl bg-[#161822] border border-[#25293A] p-5 space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-2">
            <Wrench className="w-4 h-4 text-[#FFB800]" />
            <span>FFmpeg Binary, Diagnostics &amp; Factory Reset</span>
          </h2>

          <div className="space-y-2 text-xs">
            <label className="block space-y-1">
              <span className="text-slate-400">Custom FFmpeg Path (optional)</span>
              <input
                type="text"
                value={options.ffmpeg_path}
                onChange={(e) => setOptions({ ffmpeg_path: e.target.value })}
                placeholder="Auto-detected on PATH (or bundled ffmpeg.exe)"
                className="w-full bg-[#0F1016] border border-[#25293A] rounded-lg px-3 py-1.5 text-slate-200 font-mono"
              />
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={options.ffmpeg_faststart}
                onChange={(e) => setOptions({ ffmpeg_faststart: e.target.checked })}
                className="accent-[#00D4AA]"
              />
              <span>Enable MP4 FastStart (-movflags +faststart)</span>
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[#25293A] text-xs">
            <button
              type="button"
              onClick={exportDiagnosticBundle}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#6C63FF]/20 border border-[#6C63FF]/40 text-[#6C63FF] hover:bg-[#6C63FF] hover:text-white font-semibold transition"
            >
              <Archive className="w-4 h-4" />
              <span>Export Diagnostic Log Bundle (.zip)</span>
            </button>

            <button
              type="button"
              onClick={() => setOptions({ ...DEFAULT_JOB_OPTIONS })}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#FF5E7E]/15 border border-[#FF5E7E]/40 text-[#FF5E7E] hover:bg-[#FF5E7E] hover:text-white font-semibold transition"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reset All 44 Settings to Default</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
