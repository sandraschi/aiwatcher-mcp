import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ExternalLink,
  Flame,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Sparkles,
  Star,
  X,
} from "lucide-react";
import { useCallback, useState } from "react";
import { HnThreadDrawer } from "../components/HnThreadDrawer";
import { UrgencyBadge } from "../components/UrgencyBadge";
import { apiFetch } from "../utils/api";

interface HnItem {
  id: number;
  hn_id?: number | null;
  title: string;
  url: string;
  feed_name?: string;
  summary?: string;
  distilled_summary?: string;
  urgency_score?: number;
  relevance_score?: number;
  tags?: string;
  fetched_at?: string;
  published_at?: string;
}

interface HnDashboard {
  watchlist: string[];
  config: {
    hn_enabled: boolean;
    poll_interval_minutes: number;
    min_points: number;
    min_star_velocity: number;
  };
  feeds: Array<{ id: number; name: string; feed_type: string }>;
  items: HnItem[];
  count: number;
  hours: number;
}

async function fetchDashboard(hours: number): Promise<HnDashboard> {
  const r = await apiFetch(`/api/hn/dashboard?hours=${hours}&limit=80`);
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || "Failed to load HN dashboard");
  }
  return r.json();
}

function parseTags(raw: string | undefined): string[] {
  if (!raw) return [];
  try {
    const p = JSON.parse(raw);
    return Array.isArray(p) ? p : [];
  } catch {
    return [];
  }
}

function parseHnStats(summary: string | undefined): {
  points: number | null;
  comments: number | null;
  stars: string | null;
  velocity: string | null;
} {
  const out = { points: null, comments: null, stars: null, velocity: null } as {
    points: number | null;
    comments: number | null;
    stars: string | null;
    velocity: string | null;
  };
  if (!summary) return out;
  const hn = summary.match(/HN: (\d+) points, (\d+) comments/);
  if (hn) {
    out.points = Number(hn[1]);
    out.comments = Number(hn[2]);
  }
  const gh = summary.match(/GitHub: ([\d,]+) stars \(([\d,]+)\/day\)/);
  if (gh) {
    out.stars = gh[1];
    out.velocity = gh[2];
  }
  return out;
}

function StoryCard({
  item,
  onOpenThread,
}: {
  item: HnItem;
  onOpenThread: (hnId: number) => void;
}) {
  const tags = parseTags(item.tags);
  const summary = item.distilled_summary || item.summary || "";
  const stats = parseHnStats(item.summary);
  const date = (item.published_at || item.fetched_at || "").slice(0, 10);
  const isWatchlist = tags.includes("hn-watchlist");

  return (
    <article className="rounded-2xl border border-orange-500/15 bg-zinc-900/50 backdrop-blur-sm hover:border-orange-500/30 transition-all overflow-hidden">
      <div className="p-5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 w-9 h-9 rounded-xl flex items-center justify-center shrink-0 bg-orange-500/15 text-orange-400">
            <Flame className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-white leading-snug">
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-orange-300 transition-colors inline-flex items-center gap-1.5"
                >
                  {item.title}
                  <ExternalLink className="w-3 h-3 shrink-0 opacity-60" />
                </a>
              ) : (
                item.title
              )}
            </h3>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              {item.feed_name && (
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-400">
                  {item.feed_name.replace("HN ", "")}
                </span>
              )}
              {isWatchlist && (
                <span className="text-[11px] px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400">
                  watchlist
                </span>
              )}
              {stats.points != null && (
                <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-orange-500/10 text-orange-300">
                  <Flame className="w-3 h-3" />
                  {stats.points}
                </span>
              )}
              {stats.comments != null &&
                (item.hn_id ? (
                  <a
                    href={`https://news.ycombinator.com/item?id=${item.hn_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-testid="hn-comments-link"
                    title="Open comments on news.ycombinator.com"
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-orange-300 transition-colors"
                  >
                    <MessageSquare className="w-3 h-3" />
                    {stats.comments}
                  </a>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300">
                    <MessageSquare className="w-3 h-3" />
                    {stats.comments}
                  </span>
                ))}
              {item.hn_id ? (
                <button
                  type="button"
                  data-testid="hn-thread-open"
                  onClick={() => onOpenThread(item.hn_id as number)}
                  className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md border border-orange-500/30 text-orange-300 hover:bg-orange-500/10 transition-colors"
                >
                  <MessageSquare className="w-3 h-3" />
                  Thread
                </button>
              ) : null}
              {stats.stars && (
                <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300">
                  <Star className="w-3 h-3" />
                  {stats.stars} ({stats.velocity}/day)
                </span>
              )}
              {item.urgency_score != null && (
                <UrgencyBadge score={item.urgency_score} />
              )}
            </div>
            {summary && (
              <p className="text-sm text-zinc-400 mt-2 leading-relaxed line-clamp-3">
                {summary}
              </p>
            )}
            {date && <p className="text-xs text-zinc-600 mt-2">{date}</p>}
          </div>
        </div>
      </div>
    </article>
  );
}

export function HnPage() {
  const [hours, setHours] = useState(72);
  const [newTerm, setNewTerm] = useState("");
  const [threadId, setThreadId] = useState<number | null>(null);
  const openThread = useCallback((hnId: number) => setThreadId(hnId), []);
  const closeThread = useCallback(() => setThreadId(null), []);
  const qc = useQueryClient();

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["hn-dashboard", hours],
    queryFn: () => fetchDashboard(hours),
    refetchInterval: 120_000,
  });

  const pollMutation = useMutation({
    mutationFn: async () => {
      const r = await apiFetch("/api/hn/poll", { method: "POST" });
      if (!r.ok) throw new Error(`Poll failed (${r.status})`);
      return r.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hn-dashboard"] }),
  });

  const watchlistMutation = useMutation({
    mutationFn: async (payload: { action: string; terms: string }) => {
      const r = await apiFetch("/api/hn/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${r.status}`);
      }
      return r.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hn-dashboard"] }),
  });

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center">
              <Flame className="w-4 h-4 text-orange-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Hacker News</h1>
          </div>
          <p className="text-sm text-zinc-500 mt-1 max-w-xl">
            Release-velocity discovery — Algolia front page, term watchlist,
            GitHub stars/day enrichment. The scored complement to keyword RSS.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-zinc-300 outline-none focus:border-orange-500/50"
          >
            <option value={24}>Last 24h</option>
            <option value={72}>Last 3 days</option>
            <option value={168}>Last 7 days</option>
          </select>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm border border-white/10 text-zinc-300 hover:bg-white/5 disabled:opacity-50"
          >
            <RefreshCw
              className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
          <button
            onClick={() => pollMutation.mutate()}
            disabled={pollMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-orange-500 hover:bg-orange-400 text-zinc-950 transition-all disabled:opacity-50"
          >
            {pollMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            Poll HN
          </button>
        </div>
      </div>

      {data?.config && (
        <div className="rounded-2xl border border-white/10 bg-zinc-900/40 p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={`px-2 py-1 rounded-md font-medium ${
                data.config.hn_enabled
                  ? "bg-green-500/10 text-green-400"
                  : "bg-rose-500/10 text-rose-400"
              }`}
            >
              {data.config.hn_enabled ? "Polling on" : "Polling off"}
            </span>
            <span className="text-zinc-500">
              every {data.config.poll_interval_minutes}m
            </span>
            <span className="px-2 py-1 rounded-md bg-orange-500/10 text-orange-300">
              gate: {data.config.min_points} pts or{" "}
              {data.config.min_star_velocity}
              /day
            </span>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
              Search-term watchlist
            </p>
            <div className="flex flex-wrap gap-2">
              {(data.watchlist ?? []).map((term) => (
                <span
                  key={term}
                  className="inline-flex items-center gap-1 pl-3 pr-1.5 py-1 rounded-full text-sm bg-orange-500/10 text-orange-300 border border-orange-500/20"
                >
                  {term}
                  <button
                    type="button"
                    onClick={() =>
                      watchlistMutation.mutate({
                        action: "remove",
                        terms: term,
                      })
                    }
                    className="p-0.5 rounded-full hover:bg-orange-500/20 text-orange-400/70"
                    title={`Remove ${term}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {(data.watchlist ?? []).length === 0 && (
                <span className="text-sm text-zinc-600">
                  No terms — set HN_WATCHLIST or add below
                </span>
              )}
            </div>
            <form
              className="flex gap-2 mt-3"
              onSubmit={(e) => {
                e.preventDefault();
                const t = newTerm.trim();
                if (!t) return;
                watchlistMutation.mutate({ action: "add", terms: t });
                setNewTerm("");
              }}
            >
              <input
                value={newTerm}
                onChange={(e) => setNewTerm(e.target.value)}
                placeholder="Add term e.g. GGUF"
                className="flex-1 max-w-xs bg-zinc-950 border border-white/10 rounded-xl px-3 py-2 text-sm text-zinc-300 outline-none focus:border-orange-500/50"
              />
              <button
                type="submit"
                disabled={watchlistMutation.isPending || !newTerm.trim()}
                className="flex items-center gap-1 px-3 py-2 rounded-xl text-sm border border-white/10 text-zinc-300 hover:bg-white/5 disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                Add
              </button>
            </form>
          </div>
        </div>
      )}

      {pollMutation.isSuccess && (
        <div className="text-xs text-green-400 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20">
          Poll complete —{" "}
          {(pollMutation.data as { total_new?: number })?.total_new ?? 0} new
          stories
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
          <p className="text-sm">{(error as Error).message}</p>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-32 rounded-2xl bg-white/5 animate-pulse"
            />
          ))}
        </div>
      ) : (data?.items?.length ?? 0) > 0 ? (
        <div className="space-y-3">
          <p className="text-xs text-zinc-600 text-right">
            {data?.count} stories · last {hours}h
          </p>
          {data!.items.map((item) => (
            <StoryCard key={item.id} item={item} onOpenThread={openThread} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center rounded-3xl border border-dashed border-orange-500/20 bg-orange-500/[0.02]">
          <div className="w-16 h-16 rounded-2xl bg-orange-500/10 flex items-center justify-center mb-4">
            <Flame className="w-7 h-7 text-orange-400" />
          </div>
          <h2 className="text-xl font-semibold text-white">
            No Hacker News stories yet
          </h2>
          <p className="text-zinc-500 mt-2 max-w-md text-sm">
            Hit Poll HN to pull the current front page plus watchlist terms.
            Stories meeting the points or stars/day gate appear here.
          </p>
          <button
            onClick={() => pollMutation.mutate()}
            disabled={pollMutation.isPending}
            className="mt-6 flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-orange-500 hover:bg-orange-400 text-zinc-950 disabled:opacity-50"
          >
            {pollMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            Poll now
          </button>
        </div>
      )}

      {threadId != null && (
        <HnThreadDrawer itemId={threadId} onClose={closeThread} />
      )}
    </div>
  );
}
