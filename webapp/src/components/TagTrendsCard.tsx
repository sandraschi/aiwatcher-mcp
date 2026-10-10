import { useQuery } from "@tanstack/react-query";
import { Hash } from "lucide-react";
import { useState } from "react";
import { apiFetch } from "../utils/api";

interface TagTrend {
  tag: string;
  count: number;
}

async function fetchTrends(
  days: number,
  signal?: AbortSignal,
): Promise<{ days: number; trends: TagTrend[] }> {
  const r = await apiFetch(`/api/trends?days=${days}`, { signal });
  if (!r.ok) throw new Error(`Trends failed (${r.status})`);
  return r.json();
}

const TOP_N = 15;

export function TagTrendsCard() {
  const [days, setDays] = useState(7);
  const { data, isLoading, error } = useQuery({
    queryKey: ["trends", days],
    queryFn: ({ signal }) => fetchTrends(days, signal),
    refetchInterval: 300_000,
  });
  const trends = (data?.trends ?? []).slice(0, TOP_N);
  const max = Math.max(1, ...trends.map((t) => t.count));

  return (
    <div
      data-testid="trends-card"
      className="rounded-xl border overflow-hidden"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
    >
      <div
        className="px-5 py-4 border-b flex items-center justify-between"
        style={{ borderColor: "var(--border)" }}
      >
        <span
          className="text-sm font-semibold flex items-center gap-2"
          style={{ color: "var(--text-primary)" }}
        >
          <Hash className="w-4 h-4" style={{ color: "var(--accent-amber)" }} />
          Tag Trends
        </span>
        <select
          data-testid="trends-days"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="text-xs rounded-lg px-2 py-1 border outline-none"
          style={{
            background: "var(--bg-primary)",
            color: "var(--text-secondary)",
            borderColor: "var(--border)",
          }}
        >
          <option value={1}>24h</option>
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
        </select>
      </div>
      <div className="px-5 py-4 space-y-1.5">
        {isLoading && (
          <div className="h-40 rounded-lg animate-pulse bg-white/5" />
        )}
        {error && (
          <p className="text-xs text-rose-400">{(error as Error).message}</p>
        )}
        {!isLoading && !error && trends.length === 0 && (
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            No tagged items in the last {days} day(s)
          </p>
        )}
        {trends.map((t) => (
          <div
            key={t.tag}
            data-testid="trend-row"
            className="flex items-center gap-3"
          >
            <span
              className="w-44 shrink-0 truncate text-xs"
              style={{ color: "var(--text-secondary)" }}
              title={t.tag}
            >
              {t.tag}
            </span>
            <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(t.count / max) * 100}%`,
                  background: "var(--accent-amber)",
                  opacity: 0.7,
                }}
              />
            </div>
            <span
              className="w-12 text-right text-xs font-mono"
              style={{ color: "var(--text-muted)" }}
            >
              {t.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
