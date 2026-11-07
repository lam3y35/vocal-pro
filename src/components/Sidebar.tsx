import React from "react";
import {
  AudioWaveform,
  Cpu,
  Globe,
  History,
  LayoutDashboard,
  RefreshCw,
  Settings,
  Sliders,
  Sparkles,
} from "lucide-react";
import { LOCALE_LABELS, SupportedLocale, TRANSLATIONS } from "../i18n/translations";
import { useJobsStore, useSystemStore } from "../state/appStores";

export type ScreenId = "home" | "separate" | "results" | "history" | "settings";

interface SidebarProps {
  activeScreen: ScreenId;
  onSelectScreen: (screen: ScreenId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeScreen, onSelectScreen }) => {
  const locale = useSystemStore((s) => s.locale);
  const setLocale = useSystemStore((s) => s.setLocale);
  const health = useSystemStore((s) => s.health);
  const restartWorker = useSystemStore((s) => s.restartWorker);
  const setShowChangelogModal = useSystemStore((s) => s.setShowChangelogModal);
  const jobs = useJobsStore((s) => s.jobs);

  const t = TRANSLATIONS[locale];
  const runningCount = jobs.filter(
    (j) => !["done", "cancelled", "failed"].includes(j.status)
  ).length;

  const navItems: { id: ScreenId; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: "home", label: t.nav_home, icon: <LayoutDashboard className="w-4 h-4" /> },
    {
      id: "separate",
      label: t.nav_separate,
      icon: <AudioWaveform className="w-4 h-4" />,
      badge: runningCount > 0 ? runningCount : undefined,
    },
    { id: "results", label: t.nav_results, icon: <Sliders className="w-4 h-4" /> },
    { id: "history", label: t.nav_history, icon: <History className="w-4 h-4" /> },
    { id: "settings", label: t.nav_settings, icon: <Settings className="w-4 h-4" /> },
  ];

  return (
    <aside className="w-64 shrink-0 bg-[#161822] border-r border-[#25293A] flex flex-col justify-between p-4 select-none">
      <div className="space-y-6">
        {/* Studio Brand Header */}
        <div className="flex items-center gap-3 px-2">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-[#6C63FF] to-[#00D4AA] flex items-center justify-center shadow-lg shadow-[#6C63FF]/25">
            <AudioWaveform className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight text-white">VocalPro</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#00D4AA]/15 text-[#00D4AA] border border-[#00D4AA]/30">
                v3.0
              </span>
            </div>
            <p className="text-[11px] text-slate-400 truncate max-w-[155px]">{t.app_subtitle}</p>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const active = activeScreen === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectScreen(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition ${
                  active
                    ? "bg-gradient-to-r from-[#6C63FF] to-[#6C63FF]/80 text-white shadow-md shadow-[#6C63FF]/25"
                    : "text-slate-400 hover:text-slate-100 hover:bg-[#0F1016]/60"
                }`}
              >
                <span className="flex items-center gap-3">
                  {item.icon}
                  <span>{item.label}</span>
                </span>
                {item.badge !== undefined && (
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-[#00D4AA] text-slate-950">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Worker Status + 16-Language Switcher + What's New */}
      <div className="space-y-3 pt-4 border-t border-[#25293A]">
        {/* Stdio Worker Telemetry Card */}
        <div className="rounded-xl bg-[#0F1016] border border-[#25293A] p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  health.running ? "bg-[#00D4AA] animate-pulse" : "bg-[#FF5E7E]"
                }`}
              />
              <span className="text-[11px] font-semibold text-slate-200">
                Stdio AI Worker {health.running ? "Ready" : "Offline"}
              </span>
            </div>
            <button
              type="button"
              onClick={restartWorker}
              title="Restart Python AI Worker"
              className="p-1 rounded hover:bg-[#161822] text-slate-400 hover:text-white transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-mono">
            <Cpu className="w-3 h-3 text-[#6C63FF] shrink-0" />
            <span className="truncate">
              Zero Ports • PyTorch {health.torch_version}
            </span>
          </div>
        </div>

        {/* 16-Language Selector */}
        <div className="flex items-center gap-2 bg-[#0F1016] border border-[#25293A] rounded-lg px-2.5 py-1.5">
          <Globe className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as SupportedLocale)}
            className="w-full bg-transparent text-xs text-slate-200 focus:outline-none cursor-pointer"
          >
            {(Object.keys(LOCALE_LABELS) as SupportedLocale[]).map((code) => (
              <option key={code} value={code} className="bg-[#161822] text-slate-100">
                {LOCALE_LABELS[code]}
              </option>
            ))}
          </select>
        </div>

        {/* What's New Changelog Button */}
        <button
          type="button"
          onClick={() => setShowChangelogModal(true)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[#6C63FF]/15 border border-[#6C63FF]/30 text-[#6C63FF] hover:bg-[#6C63FF]/25 text-xs font-medium transition"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{t.whats_new} (v3.0)</span>
        </button>
      </div>
    </aside>
  );
};
