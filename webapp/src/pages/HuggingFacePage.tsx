import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Boxes,
  ExternalLink,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { useState } from "react";
import { UrgencyBadge } from "../components/UrgencyBadge";
import { apiFetch } from "../utils/api";

type Category = "drops" | "papers" | "updates" | "all";

interface HfItem {
  id: number;
  title: string;
  url: string;
  feed_name?: string;
  summary?: string;
  body?: string;
  distilled_summary?: string;
  urgency_score?: number;
  relevance_score?: number;
  tags?: string;
  quants?: string[];
  quant_count?: number;
  fetched_at?: string;
  published_at?: string;
}

interface HfDashboard {
  watchlist: string[];
  config: {
    huggingface_enabled: boolean;
    poll_interval_minutes: number;
    discovery_enabled: boolean;
    hf_token_set: boolean;
    min_weight_bytes: number;
  };
  feeds: Array<{ id: number; name: string; feed_type: string }>;
  items: HfItem[];
  count: number;
}

async function fetchDashboard(
  hours: number,
  category: Category,
): Promise<HfDashboard> {
  const r = await apiFetch(
    `/api/huggingface/dashboard?hours=${hours}&category=${category}&limit=80`,
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || "Failed to load Hugging Face dashboard");
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

function hfAuthorFromTags(tags: string[]): string | null {
  const tag = tags.find((t) => t.startsWith("hf-author:"));
  return tag ? tag.replace("hf-author:", "") : null;
}

function ModelCard({ item }: { item: HfItem }) {
  const tags = parseTags(item.tags);
  const author = hfAuthorFromTags(tags);
  const summary = item.distilled_summary || item.body || item.summary || "";
  const quants = item.quants ?? [];
  const date = (item.published_at || item.fetched_at || "").slice(0, 10);
  const isCluster = (item.quant_count ?? 0) > 0;

  return (
    <article className="rounded-2xl border border-amber-500/15 bg-zinc-900/50 backdrop-blur-sm hover:border-amber-500/30 transition-all overflow-hidden">
      <div className="p-5">
        <div className="flex items-start gap-3">
          <div
            className={`mt-0.5 w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
              isCluster
                ? "bg-amber-500/15 text-amber-400"
                : "bg-zinc-800 text-zinc-500"
            }`}
          >
            <Boxes className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-white leading-snug">
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-amber-300 transition-colors inline-flex items-center gap-1.5"
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
                  {item.feed_name.replace("HuggingFace ", "")}
                </span>
              )}
              {author && (
                <span className="text-[11px] px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400">
                  @{author}
                </span>
              )}
              {item.urgency_score != null && (
                <UrgencyBadge score={item.urgency_score} />
              )}
              {isCluster && (
                <span className="text-[11px] px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400">
                  {item.quant_count} quants
                </span>
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
      {quants.length > 0 && (
        <div className="px-5 pb-5">
          <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
            Quant variants
          </p>
          <ul className="space-y-1.5">
            {quants.slice(0, 6).map((q) => (
              <li
                key={q}
                className="text-xs text-zinc-400 font-mono bg-zinc-950/60 rounded-lg px-3 py-2 border border-white/5"
              >
                {q}
              </li>
            ))}
            {quants.length > 6 && (
              <li className="text-xs text-zinc-600 pl-1">
                +{quants.length - 6} more
              </li>
            )}
          </ul>
        </div>
      )}
    </article>
  );
}

export function HuggingFacePage() {
  const [hours, setHours] = useState(72);
  const [category, setCategory] = useState<Category>("drops");
  const [newAuthor, setNewAuthor] = useState("");
  const qc = useQueryClient();

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["hf-dashboard", hours, category],
    queryFn: () => fetchDashboard(hours, category),
    refetchInterval: 120_000,
  });

  const pollMutation = useMutation({
    mutationFn: async () => {
      const r = await apiFetch("/api/huggingface/poll", { method: "POST" });
      if (!r.ok) throw new Error(`Poll failed (${r.status})`);
      return r.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hf-dashboard"] }),
  });

  const watchlistMutation = useMutation({
    mutationFn: async (payload: { action: string; authors: string }) => {
      const r = await apiFetch("/api/huggingface/watchlist", {
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hf-dashboard"] }),
  });

  const categories: { id: Category; label: string }[] = [
    { id: "drops", label: "Model drops" },
    { id: "papers", label: "Papers" },
    { id: "updates", label: "Updates" },
    { id: "all", label: "All" },
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-amber-400/20 flex items-center justify-center">
              <span className="text-lg">🤗</span>
            </div>
            <h1 className="text-2xl font-bold text-white">Hugging Face</h1>
          </div>
          <p className="text-sm text-zinc-500 mt-1 max-w-xl">
            Upstream model drops — author watchlist polled by{" "}
            <code className="text-amber-400/80">createdAt</code>, clustered on{" "}
            <code className="text-amber-400/80">base_model</code>, gated on
            weights
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
            className="bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-zinc-300 outline-none focus:border-amber-500/50"
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
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-amber-500 hover:bg-amber-400 text-zinc-950 transition-all disabled:opacity-50"
          >
            {pollMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            Poll HF
          </button>
        </div>
      </div>

      {data?.config && (
        <div className="rounded-2xl border border-white/10 bg-zinc-900/40 p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={`px-2 py-1 rounded-md font-medium ${
                data.config.huggingface_enabled
                  ? "bg-green-500/10 text-green-400"
                  : "bg-rose-500/10 text-rose-400"
              }`}
            >
              {data.config.huggingface_enabled ? "Polling on" : "Polling off"}
            </span>
            <span className="text-zinc-500">
              every {data.config.poll_interval_minutes}m
            </span>
            {data.config.discovery_enabled && (
              <span className="px-2 py-1 rounded-md bg-indigo-500/10 text-indigo-400">
                discovery on
              </span>
            )}
            <span
              className={`px-2 py-1 rounded-md ${
                data.config.hf_token_set
                  ? "bg-green-500/10 text-green-400"
                  : "bg-amber-500/10 text-amber-400"
              }`}
            >
              {data.config.hf_token_set ? "HF_TOKEN set" : "HF_TOKEN missing"}
            </span>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
              Author watchlist
            </p>
            <div className="flex flex-wrap gap-2">
              {(data.watchlist ?? []).map((author) => (
                <span
                  key={author}
                  className="inline-flex items-center gap-1 pl-3 pr-1.5 py-1 rounded-full text-sm bg-amber-500/10 text-amber-300 border border-amber-500/20"
                >
                  @{author}
                  <button
                    type="button"
                    onClick={() =>
                      watchlistMutation.mutate({
                        action: "remove",
                        authors: author,
                      })
                    }
                    className="p-0.5 rounded-full hover:bg-amber-500/20 text-amber-400/70"
                    title={`Remove ${author}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {(data.watchlist ?? []).length === 0 && (
                <span className="text-sm text-zinc-600">
                  No authors — set HF_WATCHLIST or add below
                </span>
              )}
            </div>
            <form
              className="flex gap-2 mt-3"
              onSubmit={(e) => {
                e.preventDefault();
                const a = newAuthor.trim();
                if (!a) return;
                watchlistMutation.mutate({ action: "add", authors: a });
                setNewAuthor("");
              }}
            >
              <input
                value={newAuthor}
                onChange={(e) => setNewAuthor(e.target.value)}
                placeholder="Add author e.g. Jackrong"
                className="flex-1 max-w-xs bg-zinc-950 border border-white/10 rounded-xl px-3 py-2 text-sm text-zinc-300 outline-none focus:border-amber-500/50"
              />
              <button
                type="submit"
                disabled={watchlistMutation.isPending || !newAuthor.trim()}
                className="flex items-center gap-1 px-3 py-2 rounded-xl text-sm border border-white/10 text-zinc-300 hover:bg-white/5 disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                Add
              </button>
            </form>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-1 p-1 rounded-xl border border-white/10 bg-zinc-900/40 w-fit">
        {categories.map((c) => (
          <button
            key={c.id}
            onClick={() => setCategory(c.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              category === c.id
                ? "bg-amber-500/15 text-amber-300"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {pollMutation.isSuccess && (
        <div className="text-xs text-green-400 px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20">
          Poll complete —{" "}
          {(pollMutation.data as { total_new?: number })?.total_new ?? 0} new
          items
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
            {data?.count} items · last {hours}h
          </p>
          {data!.items.map((item) => (
            <ModelCard key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center rounded-3xl border border-dashed border-amber-500/20 bg-amber-500/[0.02]">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/10 flex items-center justify-center mb-4 text-3xl">
            🤗
          </div>
          <h2 className="text-xl font-semibold text-white">
            No model drops yet
          </h2>
          <p className="text-zinc-500 mt-2 max-w-md text-sm">
            Set <code className="text-amber-400/80">HF_WATCHLIST</code> in .env,
            add authors above, then hit Poll HF. Drops appear here once weights
            land on the repo.
          </p>
          <button
            onClick={() => pollMutation.mutate()}
            disabled={pollMutation.isPending}
            className="mt-6 flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-amber-500 hover:bg-amber-400 text-zinc-950 disabled:opacity-50"
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
    </div>
  );
}
