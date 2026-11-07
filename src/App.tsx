import React, { useState } from "react";
import { Sparkles, X } from "lucide-react";
import { ScreenId, Sidebar } from "./components/Sidebar";
import { HistoryScreen } from "./screens/HistoryScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { SeparationScreen } from "./screens/SeparationScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { useSystemStore } from "./state/appStores";

export const App: React.FC = () => {
  const [activeScreen, setActiveScreen] = useState<ScreenId>("separate");
  const locale = useSystemStore((s) => s.locale);
  const changelog = useSystemStore((s) => s.changelog);
  const showChangelogModal = useSystemStore((s) => s.showChangelogModal);
  const setShowChangelogModal = useSystemStore((s) => s.setShowChangelogModal);

  const isRtl = locale === "ar";

  return (
    <div
      dir={isRtl ? "rtl" : "ltr"}
      className="h-screen w-screen flex bg-[#0F1016] text-slate-100 overflow-hidden"
    >
      <Sidebar activeScreen={activeScreen} onSelectScreen={setActiveScreen} />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Studio Top Status Bar */}
        <header className="h-14 shrink-0 border-b border-[#25293A] bg-[#161822]/80 px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              {activeScreen === "home" && "Studio Overview"}
              {activeScreen === "separate" && "AI Separation Workstation"}
              {activeScreen === "results" && "Outputs Library & Real-Time Stem Mixer"}
              {activeScreen === "history" && "Separation & Download History"}
              {activeScreen === "settings" && "Engine, DSP & OS Integration Settings"}
            </span>
          </div>

          <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
            <span className="px-2 py-0.5 rounded bg-[#0F1016] border border-[#25293A] text-[#00D4AA]">
              N4: 0 Listening Ports
            </span>
            <span className="px-2 py-0.5 rounded bg-[#0F1016] border border-[#25293A] text-[#6C63FF]">
              N5: &lt;500ms Cancel
            </span>
          </div>
        </header>

        {/* Scrollable Screen Container */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeScreen === "home" && <HomeScreen onNavigate={setActiveScreen} />}
          {activeScreen === "separate" && <SeparationScreen />}
          {activeScreen === "results" && <ResultsScreen />}
          {activeScreen === "history" && <HistoryScreen />}
          {activeScreen === "settings" && <SettingsScreen />}
        </div>
      </main>

      {/* What's New Changelog Modal (changelog.dart parity) */}
      {showChangelogModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-[#161822] border border-[#25293A] p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-base font-bold text-white">
                <Sparkles className="w-5 h-5 text-[#00D4AA]" />
                <span>What&apos;s New in VocalPro v3.0</span>
              </div>
              <button
                type="button"
                onClick={() => setShowChangelogModal(false)}
                className="p-1 rounded-lg hover:bg-[#0F1016] text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
              {changelog.map((rel) => (
                <div
                  key={rel.version}
                  className="rounded-xl bg-[#0F1016] border border-[#25293A] p-4 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-xs text-[#6C63FF]">
                      v{rel.version}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">{rel.date}</span>
                  </div>
                  <ul className="list-disc list-inside space-y-1 text-xs text-slate-300">
                    {rel.highlights.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={() => setShowChangelogModal(false)}
              className="w-full py-2.5 rounded-xl bg-[#6C63FF] text-white text-xs font-bold hover:bg-[#6C63FF]/90 transition"
            >
              Got It
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
