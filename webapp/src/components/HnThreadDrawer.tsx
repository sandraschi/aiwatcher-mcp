import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Loader2,
  MessageSquare,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { Component, type ReactNode, useEffect, useState } from "react";
import { apiFetch } from "../utils/api";

interface HnDistill {
  thread_summary?: string;
  positions?: Array<{ label: string; gist: string; n?: string }>;
  disagreement?: string;
  tools_mentioned?: string[];
  try_this?: string;
  distilled_comments?: number;
}

async function distillThread(id: number): Promise<HnDistill> {
  const r = await apiFetch(`/api/hn/item/${id}/distill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ max_comments: 24 }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(
      (err as { error?: string }).error || `Distill failed (${r.status})`,
    );
  }
  return r.json();
}

interface HnComment {
  id: number;
  author: string;
  created_at?: string;
  text: string; // sanitized server-side (hn_ingestion.sanitize_comment_html)
  children: HnComment[];
  truncated: boolean;
}

interface HnThread {
  id: number;
  title: string;
  url?: string | null;
  author?: string | null;
  points?: number | null;
  story_text: string;
  hn_url: string;
  comment_count: number;
  max_depth: number;
  truncated: boolean;
  comments: HnComment[];
}

async function fetchThread(
  id: number,
  refresh: boolean,
  signal?: AbortSignal,
): Promise<HnThread> {
  const r = await apiFetch(
    `/api/hn/item/${id}/comments${refresh ? "?refresh=1" : ""}`,
    { signal },
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || `Failed to load thread (${r.status})`);
  }
  return r.json();
}

function countDescendants(c: HnComment): number {
  return c.children.reduce((n, k) => n + 1 + countDescendants(k), 0);
}

function CommentNode({ c }: { c: HnComment }) {
  const [open, setOpen] = useState(true);
  const hidden = countDescendants(c);
  const when = (c.created_at || "").replace("T", " ").slice(0, 16);

  return (
    <li data-testid="hn-comment" className="mt-3">
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <button
          type="button"
          data-testid="hn-comment-toggle"
          onClick={() => setOpen((v) => !v)}
          className="p-0.5 rounded hover:bg-white/5 text-zinc-400"
          aria-expanded={open}
          title={open ? "Collapse" : "Expand"}
        >
          {open ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </button>
        <span className="font-medium text-orange-300/90">{c.author}</span>
        {when && <span>{when}</span>}
        {!open && hidden > 0 && (
          <span className="text-zinc-600">+{hidden} hidden</span>
        )}
      </div>
      {open && (
        <div className="pl-6">
          {c.text && (
            <div
              className="hn-comment-body text-sm text-zinc-300 leading-relaxed break-words mt-1"
              // biome-ignore lint/security/noDangerouslySetInnerHtml: allowlist-sanitized by the backend (sanitize_comment_html)
              dangerouslySetInnerHTML={{ __html: c.text }}
            />
          )}
          {c.truncated && (
            <a
              href={`https://news.ycombinator.com/item?id=${c.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-1 text-xs text-zinc-500 hover:text-orange-300"
            >
              more replies on HN <ExternalLink className="w-3 h-3" />
            </a>
          )}
          {c.children.length > 0 && (
            <ul className="border-l border-white/10 pl-3">
              {c.children.map((k) => (
                <CommentNode key={k.id} c={k} />
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

class ThreadErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed) {
      return (
        <p className="text-sm text-rose-400">
          This thread could not be rendered.
        </p>
      );
    }
    return this.props.children;
  }
}

export function HnThreadDrawer({
  itemId,
  onClose,
}: {
  itemId: number;
  onClose: () => void;
}) {
  const [refreshTick, setRefreshTick] = useState(0);
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["hn-thread", itemId, refreshTick],
    queryFn: ({ signal }) => fetchThread(itemId, refreshTick > 0, signal),
    staleTime: 300_000,
  });
  const distill = useMutation({ mutationFn: () => distillThread(itemId) });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const hnUrl = `https://news.ycombinator.com/item?id=${itemId}`;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close thread"
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside
        data-testid="hn-thread-drawer"
        className="relative h-full w-full max-w-2xl bg-zinc-950 border-l border-orange-500/20 shadow-2xl flex flex-col"
      >
        <header className="flex items-start gap-3 p-5 border-b border-white/10">
          <MessageSquare className="w-5 h-5 text-orange-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <h2
              data-testid="hn-thread-title"
              className="text-base font-semibold text-white leading-snug"
            >
              {data?.title || "Loading thread..."}
            </h2>
            {data && (
              <p className="text-xs text-zinc-500 mt-1">
                {data.points ?? 0} points by {data.author ?? "unknown"} ·{" "}
                <span data-testid="hn-thread-count">{data.comment_count}</span>{" "}
                comments shown
                {data.truncated && " (truncated)"}
              </p>
            )}
            <a
              href={hnUrl}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="hn-thread-open-hn"
              className="inline-flex items-center gap-1 mt-2 text-xs text-orange-300 hover:text-orange-200"
            >
              Open on news.ycombinator.com <ExternalLink className="w-3 h-3" />
            </a>
          </div>
          <button
            type="button"
            data-testid="hn-thread-distill"
            onClick={() => distill.mutate()}
            disabled={distill.isPending}
            className="inline-flex items-center gap-1 px-2 py-2 rounded-lg text-xs border border-purple-500/30 text-purple-300 hover:bg-purple-500/10 disabled:opacity-50"
            title="Summarize thread positions, disagreement and tools to try"
          >
            {distill.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            Distill
          </button>
          <button
            type="button"
            data-testid="hn-thread-refresh"
            onClick={() => setRefreshTick((t) => t + 1)}
            disabled={isFetching}
            className="p-2 rounded-lg hover:bg-white/5 text-zinc-400 disabled:opacity-50"
            title="Refetch from Algolia"
          >
            <RefreshCw
              className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`}
            />
          </button>
          <button
            type="button"
            data-testid="hn-thread-close"
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/5 text-zinc-400"
            title="Close (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-5">
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-zinc-500">
              <Loader2 className="w-4 h-4 animate-spin" /> Fetching thread from
              Algolia...
            </div>
          )}
          {error && (
            <div
              data-testid="hn-thread-error"
              className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-start gap-3"
            >
              <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
              <p className="text-sm">{(error as Error).message}</p>
            </div>
          )}
          {distill.isSuccess && distill.data && (
            <div
              data-testid="hn-thread-distill-result"
              className="mb-4 rounded-2xl border border-purple-500/20 bg-purple-500/[0.06] p-4 space-y-2"
            >
              <p className="text-[10px] font-bold uppercase tracking-wider text-purple-300">
                Thread distill · {distill.data.distilled_comments ?? 0} comments
              </p>
              {distill.data.thread_summary && (
                <p className="text-sm text-zinc-200 leading-relaxed">
                  {distill.data.thread_summary}
                </p>
              )}
              {(distill.data.positions ?? []).length > 0 && (
                <ul className="space-y-1">
                  {(distill.data.positions ?? []).map((p, i) => (
                    <li key={i} className="text-xs text-zinc-400">
                      <span className="text-purple-300 font-medium">
                        {p.label}
                      </span>
                      {p.n ? ` (${p.n})` : ""}: {p.gist}
                    </li>
                  ))}
                </ul>
              )}
              {distill.data.disagreement && (
                <p className="text-xs text-zinc-400">
                  <span className="text-zinc-200 font-medium">Fight: </span>
                  {distill.data.disagreement}
                </p>
              )}
              {(distill.data.tools_mentioned ?? []).length > 0 && (
                <p className="text-xs text-zinc-400">
                  <span className="text-zinc-200 font-medium">Try: </span>
                  {(distill.data.tools_mentioned ?? []).join(", ")}
                </p>
              )}
              {distill.data.try_this && (
                <p className="text-xs text-emerald-300">
                  → {distill.data.try_this}
                </p>
              )}
            </div>
          )}
          {distill.isError && (
            <p className="text-xs text-rose-400 mb-3">
              {(distill.error as Error).message}
            </p>
          )}
          {data && (
            <ThreadErrorBoundary>
              {data.story_text && (
                <div
                  className="hn-comment-body text-sm text-zinc-300 leading-relaxed mb-4 pb-4 border-b border-white/10"
                  // biome-ignore lint/security/noDangerouslySetInnerHtml: allowlist-sanitized by the backend (sanitize_comment_html)
                  dangerouslySetInnerHTML={{ __html: data.story_text }}
                />
              )}
              {data.comments.length === 0 ? (
                <p className="text-sm text-zinc-500">No comments yet.</p>
              ) : (
                <ul data-testid="hn-thread-comments">
                  {data.comments.map((c) => (
                    <CommentNode key={c.id} c={c} />
                  ))}
                </ul>
              )}
            </ThreadErrorBoundary>
          )}
        </div>
      </aside>
    </div>
  );
}
