import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Activity, AlertTriangle, Rss, Tag } from "lucide-react";
import { apiFetch } from "../utils/api";

type BundleHealth = {
  bundle_id: number;
  name: string;
  topic: string;
  enabled: boolean;
  items_scored: number;
  avg_urgency: number;
  avg_relevance: number;
  last_distilled: string | null;
  top_tags: string[];
  source_feeds: Array<{
    name: string;
    feed_id: number;
    items: number;
    avg_urgency: number;
  }>;
};

export function BundleHealthPanel({ bundleId }: { bundleId: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["bundle-health", bundleId],
    queryFn: () =>
      apiFetch(`/api/bundles/${bundleId}/health`).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<BundleHealth>;
      }),
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div
        className="rounded-xl border p-4 animate-pulse h-28"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border)",
        }}
      />
    );
  }

  if (isError || !data) {
    return (
      <div
        className="rounded-xl border p-4 flex items-center gap-2 text-sm text-red-400"
        style={{
          borderColor: "var(--border)",
          background: "var(--bg-surface)",
        }}
      >
        <AlertTriangle className="w-4 h-4 shrink-0" />
        Could not load bundle health metrics.
      </div>
    );
  }

  const stale =
    !data.last_distilled ||
    Date.now() - new Date(data.last_distilled).getTime() > 24 * 60 * 60 * 1000;

  return (
    <div
      className="rounded-xl border p-4 space-y-4"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity
            className="w-4 h-4"
            style={{ color: "var(--accent-amber)" }}
          />
          <span
            className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: "var(--text-muted)" }}
          >
            Bundle health
          </span>
        </div>
        {stale && data.items_scored > 0 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20">
            No distill in 24h
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Scored items" value={String(data.items_scored)} />
        <Metric label="Avg urgency" value={data.avg_urgency.toFixed(1)} />
        <Metric label="Avg relevance" value={data.avg_relevance.toFixed(1)} />
        <Metric
          label="Last distill"
          value={
            data.last_distilled
              ? formatDistanceToNow(new Date(data.last_distilled), {
                  addSuffix: true,
                })
              : "Never"
          }
        />
      </div>

      {data.top_tags.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Tag className="w-3 h-3" style={{ color: "var(--text-muted)" }} />
          {data.top_tags.slice(0, 8).map((tag) => (
            <span
              key={tag}
              className="text-[10px] px-1.5 py-0.5 rounded border"
              style={{
                borderColor: "var(--border)",
                color: "var(--text-secondary)",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {data.source_feeds.length > 0 && (
        <div className="space-y-1.5">
          <div
            className="text-[10px] font-bold uppercase flex items-center gap-1"
            style={{ color: "var(--text-muted)" }}
          >
            <Rss className="w-3 h-3" />
            Feed contribution
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {data.source_feeds.map((f) => (
              <div
                key={f.feed_id}
                className="flex justify-between text-[11px] px-2 py-1 rounded"
                style={{ background: "rgba(255,255,255,0.02)" }}
              >
                <span style={{ color: "var(--text-primary)" }}>{f.name}</span>
                <span style={{ color: "var(--text-muted)" }}>
                  {f.items} items · u={f.avg_urgency.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        className="text-[10px] uppercase"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </div>
      <div
        className="text-sm font-semibold"
        style={{ color: "var(--text-primary)" }}
      >
        {value}
      </div>
    </div>
  );
}
