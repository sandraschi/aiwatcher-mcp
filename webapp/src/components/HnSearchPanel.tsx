import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Flame, MessageSquare, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { apiFetch } from "../utils/api";

interface HnHit {
  hn_id: number;
  title: string;
  url?: string | null;
  author?: string | null;
  points?: number | null;
  comments?: number | null;
  created_at?: string | null;
  hn_url: string;
}

async function searchHn(
  q: string,
  signal?: AbortSignal,
): Promise<{ items: HnHit[]; count: number }> {
  const r = await apiFetch(
    `/api/hn/search?q=${encodeURIComponent(q)}&limit=25`,
    { signal },
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || `HN search failed (${r.status})`);
  }
  return r.json();
}

/** Live Algolia search over all of HN - results are not ingested or stored. */
export function HnSearchPanel({
  onOpenThread,
}: {
  onOpenThread: (hnId: number) => void;
}) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 400);
    return () => clearTimeout(t);
  }, [text]);

  const { data, isFetching, error } = useQuery({
    queryKey: ["hn-live-search", q],
    queryFn: ({ signal }) => searchHn(q, signal),
    enabled: q.length > 0,
    staleTime: 60_000,
  });

  return (
    <div
      data-testid="hn-search-panel"
      className="rounded-2xl border border-white/10 bg-zinc-900/40 p-4 space-y-3"
    >
      <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-zinc-950 px-3 py-2 focus-within:border-orange-500/50">
        <Search className="w-4 h-4 text-zinc-500" />
        <input
          data-testid="hn-search-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Search all of Hacker News (live Algolia, nothing is stored)..."
          className="flex-1 bg-transparent text-sm text-zinc-300 outline-none"
        />
        {text && (
          <button
            type="button"
            onClick={() => setText("")}
            className="text-zinc-500 hover:text-zinc-300"
            title="Clear"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
      {isFetching && <p className="text-xs text-zinc-500">Searching...</p>}
      {error && (
        <p data-testid="hn-search-error" className="text-xs text-rose-400">
          {(error as Error).message}
        </p>
      )}
      {data && q && (
        <>
          <p data-testid="hn-search-count" className="text-xs text-zinc-600">
            {data.count} results for "{q}" (by relevance)
          </p>
          <ul className="space-y-2">
            {data.items.map((h) => (
              <li
                key={h.hn_id}
                data-testid="hn-search-result"
                className="flex items-start gap-3 rounded-xl px-3 py-2 hover:bg-white/[0.03]"
              >
                <div className="flex-1 min-w-0">
                  <a
                    href={h.url || h.hn_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-zinc-200 hover:text-orange-300 inline-flex items-center gap-1.5"
                  >
                    {h.title}
                    <ExternalLink className="w-3 h-3 shrink-0 opacity-60" />
                  </a>
                  <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] text-zinc-500">
                    <span className="inline-flex items-center gap-1 text-orange-300">
                      <Flame className="w-3 h-3" />
                      {h.points ?? 0}
                    </span>
                    <span>{h.author}</span>
                    <span>{(h.created_at || "").slice(0, 10)}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onOpenThread(h.hn_id)}
                  className="shrink-0 inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md border border-orange-500/30 text-orange-300 hover:bg-orange-500/10"
                >
                  <MessageSquare className="w-3 h-3" />
                  {h.comments ?? 0}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
