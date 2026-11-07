import React from "react";
import { Music, Volume2, VolumeX } from "lucide-react";
import { StemTrackInfo } from "../bindings";

interface StemMixerStripProps {
  stem: StemTrackInfo;
  onGainChange: (gain: number) => void;
  onToggleMute: () => void;
  onToggleSolo: () => void;
  onExportMidi: () => void;
}

const STEM_COLORS: Record<string, string> = {
  vocals: "#00D4AA",
  drums: "#FF5E7E",
  bass: "#FFB800",
  guitar: "#6C63FF",
  piano: "#38BDF8",
  other: "#A855F7",
  karaoke: "#10B981",
  background: "#64748B",
};

export const StemMixerStrip: React.FC<StemMixerStripProps> = ({
  stem,
  onGainChange,
  onToggleMute,
  onToggleSolo,
  onExportMidi,
}) => {
  const color = STEM_COLORS[stem.name.toLowerCase()] || "#6C63FF";
  const pct = Math.round(stem.gain * 100);
  const dbText =
    stem.mute || stem.gain <= 0.001
      ? "-∞ dB"
      : `${(20 * Math.log10(stem.gain)).toFixed(1)} dB`;

  return (
    <div className="flex flex-col gap-2.5 rounded-xl bg-[#0F1016] border border-[#25293A] p-3.5 hover:border-[#6C63FF]/50 transition">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span
            className="h-3 w-3 rounded-full shrink-0"
            style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}80` }}
          />
          <span className="font-semibold uppercase tracking-wider text-xs text-slate-100">
            {stem.name}
          </span>
          <span className="text-[11px] font-mono text-slate-400">
            {pct}% ({dbText})
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onToggleMute}
            title="Mute Stem"
            className={`px-2 py-1 rounded text-[11px] font-bold transition ${
              stem.mute
                ? "bg-[#FF5E7E] text-white"
                : "bg-[#161822] text-slate-300 border border-[#25293A] hover:border-[#FF5E7E]"
            }`}
          >
            M
          </button>
          <button
            type="button"
            onClick={onToggleSolo}
            title="Solo Stem"
            className={`px-2 py-1 rounded text-[11px] font-bold transition ${
              stem.solo
                ? "bg-[#FFB800] text-slate-950"
                : "bg-[#161822] text-slate-300 border border-[#25293A] hover:border-[#FFB800]"
            }`}
          >
            S
          </button>
          <button
            type="button"
            onClick={onExportMidi}
            title="Convert Stem Pitch to MIDI (.mid via librosa.pyin)"
            className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium bg-[#161822] text-[#00D4AA] border border-[#00D4AA]/30 hover:bg-[#00D4AA]/15 transition"
          >
            <Music className="w-3 h-3" />
            MIDI
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {stem.mute || stem.gain === 0 ? (
          <VolumeX className="w-4 h-4 text-[#FF5E7E] shrink-0" />
        ) : (
          <Volume2 className="w-4 h-4 text-slate-400 shrink-0" />
        )}
        <input
          type="range"
          min={0}
          max={2.0}
          step={0.01}
          value={stem.gain}
          onChange={(e) => onGainChange(parseFloat(e.target.value))}
          className="w-full accent-[#6C63FF] cursor-pointer h-1.5 bg-[#25293A] rounded-lg"
        />
      </div>
    </div>
  );
};
