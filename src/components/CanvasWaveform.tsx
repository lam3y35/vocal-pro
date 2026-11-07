import React, { useEffect, useRef } from "react";

interface CanvasWaveformProps {
  peaks: number[];
  progressRatio?: number;
  height?: number;
  accentColor?: string;
  onSeekRatio?: (ratio: number) => void;
}

export const CanvasWaveform: React.FC<CanvasWaveformProps> = ({
  peaks,
  progressRatio = 0.25,
  height = 84,
  accentColor = "#00D4AA",
  onSeekRatio,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 640;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const numBars = Math.min(peaks.length || 120, Math.floor(width / 4));
    const step = Math.max(1, Math.floor(peaks.length / numBars));
    const barWidth = Math.max(2, width / numBars - 1.5);
    const midY = height / 2;

    for (let i = 0; i < numBars; i++) {
      const val = Math.max(0.05, Math.min(1.0, peaks[i * step] ?? 0.2));
      const barH = val * (height * 0.84);
      const x = i * (width / numBars);
      const isPlayed = i / numBars <= progressRatio;

      ctx.fillStyle = isPlayed ? accentColor : "#2E3348";
      ctx.beginPath();
      ctx.roundRect(x, midY - barH / 2, barWidth, barH, 2);
      ctx.fill();
    }

    // Playhead line
    const playX = Math.max(1, Math.min(width - 1, progressRatio * width));
    ctx.strokeStyle = "#6C63FF";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(playX, 2);
    ctx.lineTo(playX, height - 2);
    ctx.stroke();
  }, [peaks, progressRatio, height, accentColor]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onSeekRatio || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    onSeekRatio(ratio);
  };

  return (
    <canvas
      ref={canvasRef}
      onClick={handleClick}
      style={{ height: `${height}px` }}
      className="w-full cursor-pointer rounded-lg bg-[#0F1016]/90 border border-[#25293A] transition hover:border-[#6C63FF]/60"
    />
  );
};
