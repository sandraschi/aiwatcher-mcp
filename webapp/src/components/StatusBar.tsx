import { useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, Clock, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useConnection } from "../store/connection";
import { apiFetch } from "../utils/api";
import { PipelineHealthBadge } from "./PipelineHealthCard";

// EXPERIMENTAL light mode (invert hack). Not fleet standard — see index.css.
// Toggling `.dark` off the root flips the invert filter; persisted so the
// choice survives reloads. Delete this + the CSS block to revert.
const THEME_KEY = "aiwatcher-light-mode";

function useExperimentalTheme() {
  const [light, setLight] = useState(() => {
    try {
      return localStorage.getItem(THEME_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", !light);
    try {
      localStorage.setItem(THEME_KEY, light ? "1" : "0");
    } catch {
      // ignore storage errors
    }
  }, [light]);

  return { light, toggle: () => setLight((v) => !v) };
}

async function fetchCaps() {
  const r = await apiFetch("/api/capabilities");
  return r.json();
}

export function StatusBar() {
  const { state, lastError } = useConnection();
  const { light, toggle } = useExperimentalTheme();
  const { data: caps } = useQuery({
    queryKey: ["capabilities"],
    queryFn: fetchCaps,
  });

  const keyMissing = caps?.features?.anthropic_key_configured === false;

  const statusColor =
    state === "connected"
      ? "bg-green-500"
      : state === "connecting"
        ? "bg-amber-500"
        : "bg-red-500";

  const statusLabel =
    state === "connected"
      ? "Backend connected"
      : state === "connecting"
        ? "Connecting..."
        : `Offline${lastError ? ` (${lastError.slice(0, 60)})` : ""}`;

  return (
    <header
      className="flex items-center justify-between px-6 py-3 border-b flex-shrink-0"
      style={{
        borderColor: "var(--border)",
        background: "var(--bg-secondary)",
      }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Activity
            className="w-4 h-4"
            style={{ color: "var(--text-secondary)" }}
          />
          <span
            className="text-sm font-medium"
            style={{ color: "var(--text-secondary)" }}
          >
            AI Intelligence Feed
          </span>
        </div>

        <PipelineHealthBadge />
        {keyMissing && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-[10px] font-bold text-rose-500 uppercase tracking-wider">
            <AlertCircle className="w-3 h-3" />
            No API Key
          </div>
        )}
      </div>
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggle}
          className="p-2 rounded-lg transition-colors hover:bg-zinc-800"
          style={{ color: "var(--text-muted)" }}
          title={
            light
              ? "Switch to dark (experimental light mode)"
              : "Switch to light (experimental, ugly)"
          }
          aria-label="Toggle light mode (experimental)"
        >
          {light ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${statusColor} animate-pulse-slow`}
          />
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {statusLabel}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3" style={{ color: "var(--text-muted)" }} />
          <span
            className="text-xs font-mono"
            style={{ color: "var(--text-muted)" }}
          >
            {new Date().toLocaleTimeString("de-AT")}
          </span>
        </div>
      </div>
    </header>
  );
}
