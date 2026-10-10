import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { FileText, Inbox, Plus, Search, Upload, X } from "lucide-react";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { apiFetch } from "../utils/api";

interface InboxList {
  pending_files: string[];
  pending_analysis: string[];
  review_notes: string[];
  ingested_files: string[];
  recent_db_items: Array<{
    id: number;
    title: string;
    fetched_at: string;
    distilled_at: string | null;
  }>;
}

type Tab = "analysis" | "review" | "ingested";
const PAGE_SIZE = 20;

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await apiFetch(path, { signal });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body as T;
}

// YAML frontmatter would render as an <hr> plus a run-on paragraph
const stripFrontmatter = (md: string) =>
  md.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "");

function FilePreview({ name, onClose }: { name: string; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["inbox-file", name],
    queryFn: ({ signal }) =>
      getJson<{ content: string }>(
        `/api/inbox/file?name=${encodeURIComponent(name)}`,
        signal,
      ),
  });
  return (
    <div
      data-testid="inbox-preview"
      className="rounded-2xl border border-white/10 bg-zinc-900/60 overflow-hidden"
    >
      <div className="px-5 py-3 border-b border-white/10 flex items-center gap-2">
        <FileText className="w-4 h-4 text-indigo-400" />
        <span className="text-sm font-mono text-zinc-200 truncate">{name}</span>
        <button
          type="button"
          onClick={onClose}
          className="ml-auto text-zinc-500 hover:text-zinc-300"
          title="Close preview"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="p-5 max-h-[32rem] overflow-y-auto text-sm text-zinc-300 leading-relaxed [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:text-white [&_h2]:font-semibold [&_h2]:text-white [&_h2]:mt-4 [&_p]:mt-2 [&_ul]:list-disc [&_ul]:pl-5 [&_code]:font-mono [&_code]:text-xs [&_a]:text-indigo-300 [&_a]:underline">
        {isLoading && (
          <div className="h-24 rounded-xl bg-white/5 animate-pulse" />
        )}
        {error && <p className="text-rose-400">{(error as Error).message}</p>}
        {data && (
          <ReactMarkdown>{stripFrontmatter(data.content)}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}

function AddAnalysisForm({ onDone }: { onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [urgency, setUrgency] = useState("");
  const add = useMutation({
    mutationFn: async () => {
      const r = await apiFetch("/api/inbox/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          content,
          tags,
          source: "webapp",
          ...(urgency.trim() ? { urgency_hint: Number(urgency) } : {}),
        }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
      return body;
    },
    onSuccess: () => {
      setTitle("");
      setContent("");
      setTags("");
      setUrgency("");
      onDone();
    },
  });
  const field =
    "w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500";
  return (
    <form
      data-testid="inbox-add-form"
      onSubmit={(e) => {
        e.preventDefault();
        add.mutate();
      }}
      className="rounded-2xl border border-indigo-500/20 bg-zinc-900/40 p-5 space-y-3"
    >
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title"
        className={field}
      />
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Markdown analysis (frontmatter allowed)"
        rows={6}
        className={`${field} font-mono resize-y`}
      />
      <div className="grid grid-cols-2 gap-3">
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="tags, comma, separated"
          className={field}
        />
        <input
          value={urgency}
          onChange={(e) => setUrgency(e.target.value)}
          placeholder="urgency hint 0-10 (optional)"
          type="number"
          min={0}
          max={10}
          step={0.5}
          className={field}
        />
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={!title.trim() || !content.trim() || add.isPending}
          className="px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50"
        >
          {add.isPending ? "Adding..." : "Add to inbox feed"}
        </button>
        {add.isSuccess && (
          <span className="text-xs text-emerald-400">Added</span>
        )}
        {add.error && (
          <span className="text-xs text-rose-400">
            {(add.error as Error).message}
          </span>
        )}
      </div>
    </form>
  );
}

export function InboxPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("analysis");
  const [search, setSearch] = useState("");
  const [newestFirst, setNewestFirst] = useState(true);
  const [page, setPage] = useState(1);
  const [preview, setPreview] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["inbox"],
    queryFn: ({ signal }) => getJson<InboxList>("/api/inbox/list", signal),
    refetchInterval: 60_000,
  });

  const scan = useMutation({
    mutationFn: async () => {
      const r = await apiFetch("/api/inbox/scan", { method: "POST" });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
      return body as { ingested: number; skipped_review_notes: number };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inbox"] }),
  });

  const lists: Record<Tab, string[]> = {
    analysis: data?.pending_analysis ?? [],
    review: data?.review_notes ?? [],
    ingested: data?.ingested_files ?? [],
  };
  const source = lists[tab];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = source.filter((n) => !q || n.toLowerCase().includes(q));
    // file names start with the date, so name order is date order
    return [...rows].sort((a, b) =>
      newestFirst ? b.localeCompare(a) : a.localeCompare(b),
    );
  }, [source, search, newestFirst]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const rows = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const analysisCount = lists.analysis.length;

  const switchTab = (t: Tab) => {
    setTab(t);
    setPage(1);
    setPreview(null);
  };

  return (
    <div data-testid="inbox-page" className="space-y-5 max-w-5xl mx-auto pb-20">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Inbox className="w-6 h-6 text-indigo-400" /> Inbox
          </h1>
          <p className="text-sm text-zinc-500 mt-1 max-w-xl">
            Markdown drops in data/inbox. Analysis files can be ingested into
            the "Opencode Analysis" feed; session-scribe review notes are never
            ingested.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setAdding((v) => !v)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm border border-white/10 text-zinc-300 hover:bg-white/5"
          >
            <Plus className="w-4 h-4" /> Add analysis
          </button>
          <button
            type="button"
            data-testid="inbox-scan"
            disabled={analysisCount === 0 || scan.isPending}
            onClick={() => {
              if (
                window.confirm(
                  `Ingest ${analysisCount} analysis file(s) into the news feed? Review notes are skipped.`,
                )
              )
                scan.mutate();
            }}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40"
          >
            <Upload className="w-4 h-4" />
            {scan.isPending
              ? "Ingesting..."
              : `Ingest ${analysisCount} file(s)`}
          </button>
        </div>
      </div>

      {adding && (
        <AddAnalysisForm
          onDone={() => qc.invalidateQueries({ queryKey: ["inbox"] })}
        />
      )}
      {scan.data && (
        <div
          data-testid="inbox-scan-result"
          className="text-sm px-4 py-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
        >
          Ingested {scan.data.ingested} file(s); skipped{" "}
          {scan.data.skipped_review_notes} review note(s).
        </div>
      )}
      {(error || scan.error) && (
        <div className="text-sm px-4 py-2 rounded-lg border border-rose-500/20 bg-rose-500/10 text-rose-400">
          {((error || scan.error) as Error).message}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["analysis", "Analysis", lists.analysis.length],
            ["review", "Review notes", lists.review.length],
            ["ingested", "Ingested", lists.ingested.length],
          ] as const
        ).map(([key, label, n]) => (
          <button
            key={key}
            type="button"
            data-testid={`inbox-tab-${key}`}
            onClick={() => switchTab(key)}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-sm border",
              tab === key
                ? "border-indigo-500/50 bg-indigo-500/10 text-indigo-300"
                : "border-white/10 text-zinc-400 hover:bg-white/5",
            )}
          >
            {label} <span className="text-xs opacity-70">{n}</span>
          </button>
        ))}
        <div className="flex-1 min-w-48 flex items-center gap-2 rounded-lg border border-white/10 bg-zinc-950 px-3 py-1.5">
          <Search className="w-4 h-4 text-zinc-500" />
          <input
            data-testid="inbox-search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Filter file names..."
            className="flex-1 bg-transparent text-sm text-zinc-300 outline-none"
          />
        </div>
        <select
          value={newestFirst ? "new" : "old"}
          onChange={(e) => {
            setNewestFirst(e.target.value === "new");
            setPage(1);
          }}
          className="bg-zinc-950 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-zinc-300"
        >
          <option value="new">Newest first</option>
          <option value="old">Oldest first</option>
        </select>
        <span data-testid="inbox-count" className="text-xs text-zinc-500">
          {filtered.length} of {source.length}
        </span>
      </div>

      {preview && (
        <FilePreview name={preview} onClose={() => setPreview(null)} />
      )}

      <div className="rounded-2xl border border-white/10 bg-zinc-900/40 overflow-hidden">
        {isLoading && (
          <div className="h-32 m-4 rounded-xl bg-white/5 animate-pulse" />
        )}
        {!isLoading && rows.length === 0 && (
          <p className="px-5 py-8 text-center text-sm text-zinc-500">
            {source.length ? "No files match" : "Nothing here"}
          </p>
        )}
        <ul>
          {rows.map((name) => (
            <li key={name} className="border-b border-white/5 last:border-b-0">
              <button
                type="button"
                data-testid="inbox-file"
                onClick={() => setPreview(name === preview ? null : name)}
                disabled={tab === "ingested"}
                className={clsx(
                  "w-full text-left px-5 py-2.5 text-sm font-mono flex items-center gap-2",
                  tab === "ingested"
                    ? "text-zinc-500 cursor-default"
                    : "text-zinc-300 hover:bg-white/[0.03]",
                  preview === name && "bg-indigo-500/10",
                )}
              >
                <FileText className="w-3.5 h-3.5 shrink-0 text-zinc-500" />
                {name}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-center gap-1 flex-wrap">
          <button
            type="button"
            onClick={() => setPage(current - 1)}
            disabled={current <= 1}
            className="px-3 py-1.5 rounded-lg text-xs border border-white/10 text-zinc-400 disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-xs text-zinc-500 px-2">
            Page {current} of {pages}
          </span>
          <button
            type="button"
            onClick={() => setPage(current + 1)}
            disabled={current >= pages}
            className="px-3 py-1.5 rounded-lg text-xs border border-white/10 text-zinc-400 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}

      {(data?.recent_db_items?.length ?? 0) > 0 && (
        <div className="rounded-2xl border border-white/10 bg-zinc-900/40 overflow-hidden">
          <div className="px-5 py-3 border-b border-white/5 text-sm font-semibold text-white">
            Recently ingested into the feed
          </div>
          <ul>
            {data?.recent_db_items.map((it) => (
              <li
                key={it.id}
                className="px-5 py-2 border-b border-white/5 last:border-b-0 flex items-center gap-3 text-sm"
              >
                <span className="text-zinc-300 truncate">{it.title}</span>
                <span className="ml-auto text-xs text-zinc-500 font-mono shrink-0">
                  {it.fetched_at?.slice(0, 16)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
