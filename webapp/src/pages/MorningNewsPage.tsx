import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ExternalLink, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { apiFetch } from "../utils/api";

interface NewsItem {
  id: number;
  title: string;
  url: string;
  feed_name?: string;
  source?: string;
  distilled_summary?: string;
  summary?: string;
  urgency_score?: number;
  tags?: string | string[];
  fetched_at?: string;
}

async function fetchMorningNews(hours: number) {
  const r = await apiFetch(`/api/morning-news?hours=${hours}&limit=20`);
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || "Failed to fetch morning news");
  }
  return r.json();
}

function parseTags(raw: string | string[] | undefined): string[] {
  if (!raw) return [];
  const arr = Array.isArray(raw)
    ? raw
    : (() => {
        try {
          const p = JSON.parse(raw);
          return Array.isArray(p) ? p : [];
        } catch {
          return [];
        }
      })();
  return [...new Set(arr)];
}

function ItemCard({ item, rank }: { item: NewsItem; rank: number }) {
  const tags = parseTags(item.tags);
  const summary = item.distilled_summary || item.summary || item.title;
  const urgency = item.urgency_score;
  const scoreWidth = urgency != null ? `${Math.min(urgency, 10) * 10}%` : "0%";
  const date = item.fetched_at?.slice(0, 10) || "";

  return (
    <div className="p-5 rounded-2xl border border-white/10 bg-zinc-900/40 backdrop-blur-md hover:border-white/20 transition-all">
      <div className="flex items-start gap-4">
        <span className="text-lg font-bold text-zinc-600 mt-0.5 w-6 shrink-0">
          {rank}
        </span>
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-white leading-snug">
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-indigo-400 transition-colors inline-flex items-center gap-1.5"
              >
                {item.title}
                <ExternalLink className="w-3 h-3 shrink-0 opacity-60" />
              </a>
            ) : (
              item.title
            )}
          </h3>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-400 uppercase tracking-wider">
              {item.feed_name || item.source || "unknown"}
            </span>
            {tags.slice(0, 4).map((t, ti) => (
              <span
                key={`${t}-${ti}`}
                className="text-[11px] px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400"
              >
                {t}
              </span>
            ))}
            {urgency != null && (
              <span
                className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                  urgency >= 7
                    ? "bg-rose-500/15 text-rose-400"
                    : urgency >= 4
                      ? "bg-amber-500/15 text-amber-400"
                      : "bg-zinc-800 text-zinc-400"
                }`}
              >
                {urgency.toFixed(1)}
              </span>
            )}
          </div>
          <p className="text-sm text-zinc-400 mt-2 leading-relaxed line-clamp-2">
            {summary}
          </p>
          <div className="flex items-center gap-3 mt-3">
            {urgency != null && (
              <div className="flex-1 h-1 rounded-full bg-zinc-800 overflow-hidden max-w-[120px]">
                <div
                  className="h-full rounded-full bg-indigo-500"
                  style={{ width: scoreWidth }}
                />
              </div>
            )}
            {date && (
              <span className="text-xs text-zinc-600 ml-auto">{date}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function MorningNewsPage() {
  const [hours, setHours] = useState(24);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["morning-news", hours],
    queryFn: () => fetchMorningNews(hours),
    retry: false,
  });

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Morning News</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Top AI news from the last {hours} hours — aiwatcher-mcp picks
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-zinc-300 outline-none focus:border-indigo-500 transition-colors"
          >
            <option value={6}>Last 6 Hours</option>
            <option value={24}>Last 24 Hours</option>
            <option value={72}>Last 3 Days</option>
            <option value={168}>Last 7 Days</option>
          </select>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-all disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-bold text-sm">Failed to load</p>
            <p className="text-xs opacity-80 mt-1">{(error as any).message}</p>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-28 rounded-2xl bg-white/5 animate-pulse"
            />
          ))}
        </div>
      ) : data?.items?.length > 0 ? (
        <div className="space-y-3">
          {data.generated_at && (
            <p className="text-xs text-zinc-600 text-right">
              Generated: {data.generated_at}
            </p>
          )}
          {data.items.map((item: NewsItem, i: number) => (
            <ItemCard key={item.id || i} item={item} rank={i + 1} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center rounded-3xl border border-dashed border-white/10 bg-white/[0.02]">
          <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4 text-indigo-400">
            <Sparkles className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-semibold text-white">No items found</h2>
          <p className="text-zinc-500 mt-2 max-w-sm">
            No news items from the last {hours} hours. Try a wider time window
            or check that feeds are being polled.
          </p>
        </div>
      )}
    </div>
  );
}
