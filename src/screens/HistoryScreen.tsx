import React, { useState } from "react";
import { CheckCircle2, Download, History, Search, Trash2, XCircle } from "lucide-react";
import { useLibraryStore } from "../state/appStores";

export const HistoryScreen: React.FC = () => {
  const separationHistory = useLibraryStore((s) => s.separationHistory);
  const clearSeparationHistory = useLibraryStore((s) => s.clearSeparationHistory);
  const downloadHistory = useLibraryStore((s) => s.downloadHistory);
  const clearDownloadHistory = useLibraryStore((s) => s.clearDownloadHistory);

  const [tab, setTab] = useState<"separation" | "downloads">("separation");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredSep = separationHistory.filter(
    (item) =>
      item.files.join(" ").toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.model.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredDl = downloadHistory.filter(
    (item) =>
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.url.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-5 pb-10">
      <div className="rounded-xl bg-[#161822] border border-[#25293A] p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setTab("separation")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition ${
              tab === "separation"
                ? "bg-[#6C63FF] text-white"
                : "bg-[#0F1016] text-slate-400 hover:text-white"
            }`}
          >
            <History className="w-4 h-4" />
            <span>Separation History ({separationHistory.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setTab("downloads")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition ${
              tab === "downloads"
                ? "bg-[#6C63FF] text-white"
                : "bg-[#0F1016] text-slate-400 hover:text-white"
            }`}
          >
            <Download className="w-4 h-4" />
            <span>Download History ({downloadHistory.length})</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 bg-[#0F1016] border border-[#25293A] rounded-lg px-3 py-1.5">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter history..."
              className="bg-transparent text-xs text-slate-200 focus:outline-none w-44"
            />
          </div>

          <button
            type="button"
            onClick={() =>
              tab === "separation" ? clearSeparationHistory() : clearDownloadHistory()
            }
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#FF5E7E]/15 border border-[#FF5E7E]/40 text-[#FF5E7E] hover:bg-[#FF5E7E] hover:text-white text-xs font-semibold transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear {tab === "separation" ? "Separation" : "Download"} History</span>
          </button>
        </div>
      </div>

      {tab === "separation" ? (
        <div className="space-y-2.5">
          {filteredSep.map((item) => (
            <div
              key={item.id}
              className="rounded-xl bg-[#161822] border border-[#25293A] p-4 flex flex-wrap items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  {item.status === "success" ? (
                    <CheckCircle2 className="w-4 h-4 text-[#00D4AA]" />
                  ) : (
                    <XCircle className="w-4 h-4 text-[#FF5E7E]" />
                  )}
                  <span className="font-semibold text-xs text-white font-mono">
                    {item.files.map((f) => f.split(/[\\/]/).pop()).join(", ")}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#6C63FF]/20 text-[#6C63FF] font-mono text-[10px]">
                    {item.model}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#0F1016] text-slate-400 font-mono text-[10px] uppercase">
                    {item.device}
                  </span>
                </div>
                {item.output_dir && (
                  <p className="text-[11px] font-mono text-slate-400">{item.output_dir}</p>
                )}
              </div>

              <div className="text-right font-mono text-xs space-y-0.5">
                <div className="text-[#00D4AA] font-bold">{item.elapsed}</div>
                <div className="text-[11px] text-slate-500">{item.date}</div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-2.5">
          {filteredDl.map((item) => (
            <div
              key={item.id}
              className="rounded-xl bg-[#161822] border border-[#25293A] p-4 flex flex-wrap items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Download className="w-4 h-4 text-[#00D4AA]" />
                  <span className="font-semibold text-xs text-white">{item.title}</span>
                  <span className="px-2 py-0.5 rounded bg-[#00D4AA]/15 text-[#00D4AA] font-mono text-[10px]">
                    {item.format} • {item.quality}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-slate-400 truncate max-w-xl">
                  {item.url} → {item.path}
                </p>
              </div>
              <div className="text-[11px] font-mono text-slate-400">{item.date}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
