import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Clock,
  Plus,
  Search,
  ToggleLeft,
  ToggleRight,
  Upload,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { apiFetch } from "../utils/api";

async function fetchFeeds() {
  const r = await apiFetch("/api/feeds");
  return r.json();
}

type FeedFilter = "all" | "failing" | "enabled" | "disabled";
type FeedSort = "name" | "failures" | "fetched";
const PAGE_SIZE = 20;

export function FeedsPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["feeds"], queryFn: fetchFeeds });
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);

  const toggle = useMutation({
    mutationFn: async (id: number) => {
      await apiFetch(`/api/feeds/${id}/toggle`, { method: "POST" });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feeds"] }),
  });

  const addFeed = useMutation({
    mutationFn: async () => {
      const r = await apiFetch("/api/feeds/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, url }),
      });
      return r.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feeds"] });
      setName("");
      setUrl("");
      setAdding(false);
    },
  });

  const opmlInput = useRef<HTMLInputElement>(null);
  const importOpml = useMutation({
    mutationFn: async (file: File) => {
      const r = await apiFetch("/api/opml/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opml_xml: await file.text() }),
      });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.error || `Import failed (${r.status})`);
      return body as { imported: Array<{ name?: string }>; count: number };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feeds"] }),
  });

  const allFeeds: any[] = data?.feeds ?? [];
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FeedFilter>("all");
  const [sort, setSort] = useState<FeedSort>("failures");
  const [page, setPage] = useState(1);
  const failingCount = allFeeds.filter(
    (f) => (f.consecutive_failures ?? 0) > 0,
  ).length;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const rows = allFeeds.filter((f) => {
      if (q && !`${f.name} ${f.url} ${f.feed_type}`.toLowerCase().includes(q))
        return false;
      if (filter === "failing") return (f.consecutive_failures ?? 0) > 0;
      if (filter === "enabled") return !!f.enabled;
      if (filter === "disabled") return !f.enabled;
      return true;
    });
    return [...rows].sort((a, b) => {
      if (sort === "failures")
        return (
          (b.consecutive_failures ?? 0) - (a.consecutive_failures ?? 0) ||
          a.name.localeCompare(b.name)
        );
      if (sort === "fetched") {
        // missing last_fetched sorts last
        if (!a.last_fetched) return b.last_fetched ? 1 : 0;
        if (!b.last_fetched) return -1;
        return b.last_fetched.localeCompare(a.last_fetched);
      }
      return a.name.localeCompare(b.name);
    });
  }, [allFeeds, search, filter, sort]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const feeds = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const resetPage = () => setPage(1);
  const controlStyle = {
    background: "var(--bg-surface)",
    color: "var(--text-secondary)",
    borderColor: "var(--border)",
  };

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1
          className="text-xl font-semibold"
          style={{ color: "var(--text-primary)" }}
        >
          Feed Sources
        </h1>
        <div className="flex gap-2">
          <input
            ref={opmlInput}
            data-testid="opml-file"
            type="file"
            accept=".opml,.xml,text/xml,application/xml"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) importOpml.mutate(f);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            data-testid="opml-import"
            onClick={() => opmlInput.current?.click()}
            disabled={importOpml.isPending}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border transition-colors disabled:opacity-50"
            style={controlStyle}
          >
            <Upload className="w-4 h-4" />
            {importOpml.isPending ? "Importing..." : "Import OPML"}
          </button>
          <button
            onClick={() => setAdding((a) => !a)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border transition-colors"
            style={controlStyle}
          >
            <Plus className="w-4 h-4" />
            Add Feed
          </button>
        </div>
      </div>

      {importOpml.data && (
        <div
          data-testid="opml-result"
          className="text-sm px-4 py-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
        >
          Imported {importOpml.data.count} new feed
          {importOpml.data.count === 1 ? "" : "s"}
          {importOpml.data.count > 0 &&
            `: ${importOpml.data.imported
              .map((f) => f.name)
              .filter(Boolean)
              .slice(0, 5)
              .join(", ")}${importOpml.data.count > 5 ? ", ..." : ""}`}
          {importOpml.data.count === 0 && " (all already present)"}
        </div>
      )}
      {importOpml.error && (
        <div
          data-testid="opml-error"
          className="text-sm px-4 py-2 rounded-lg border border-rose-500/20 bg-rose-500/10 text-rose-400"
        >
          {(importOpml.error as Error).message}
        </div>
      )}

      {adding && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="rounded-xl border p-4 space-y-3"
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--accent-amber)",
          }}
        >
          <p
            className="text-sm font-medium"
            style={{ color: "var(--text-primary)" }}
          >
            Add new feed
          </p>
          <div className="grid grid-cols-2 gap-3">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Feed name"
              className="rounded-lg px-3 py-2 text-sm border outline-none"
              style={{
                background: "var(--bg-primary)",
                color: "var(--text-primary)",
                borderColor: "var(--border)",
              }}
            />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/feed.xml"
              className="rounded-lg px-3 py-2 text-sm border outline-none"
              style={{
                background: "var(--bg-primary)",
                color: "var(--text-primary)",
                borderColor: "var(--border)",
              }}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => addFeed.mutate()}
              disabled={!name || !url || addFeed.isPending}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              style={{
                background: "rgba(245,158,11,0.15)",
                color: "var(--accent-amber)",
                border: "1px solid rgba(245,158,11,0.3)",
              }}
            >
              {addFeed.isPending ? "Adding..." : "Add"}
            </button>
            <button
              onClick={() => setAdding(false)}
              className="px-4 py-2 rounded-lg text-sm"
              style={{ color: "var(--text-muted)" }}
            >
              Cancel
            </button>
          </div>
        </motion.div>
      )}

      {failingCount > 0 && (
        <button
          type="button"
          data-testid="feeds-failing-banner"
          onClick={() => {
            setFilter("failing");
            resetPage();
          }}
          className="w-full flex items-center gap-2 text-left text-sm px-4 py-2 rounded-lg border border-rose-500/20 bg-rose-500/10 text-rose-400"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {failingCount} of {allFeeds.length} feeds have consecutive fetch
          failures - show them
        </button>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div
          className="flex-1 min-w-48 flex items-center gap-2 rounded-lg border px-3 py-2"
          style={controlStyle}
        >
          <Search className="w-4 h-4" style={{ color: "var(--text-muted)" }} />
          <input
            data-testid="feeds-search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              resetPage();
            }}
            placeholder="Search name, URL, type..."
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--text-primary)" }}
          />
        </div>
        <select
          data-testid="feeds-filter"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value as FeedFilter);
            resetPage();
          }}
          className="text-sm rounded-lg px-3 py-2 border outline-none"
          style={controlStyle}
        >
          <option value="all">All feeds</option>
          <option value="failing">Failing</option>
          <option value="enabled">Enabled</option>
          <option value="disabled">Disabled</option>
        </select>
        <select
          data-testid="feeds-sort"
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as FeedSort);
            resetPage();
          }}
          className="text-sm rounded-lg px-3 py-2 border outline-none"
          style={controlStyle}
        >
          <option value="failures">Sort: failures</option>
          <option value="name">Sort: name</option>
          <option value="fetched">Sort: last fetched</option>
        </select>
        <span
          data-testid="feeds-count"
          className="text-xs"
          style={{ color: "var(--text-muted)" }}
        >
          {filtered.length} of {allFeeds.length}
        </span>
      </div>

      <div
        className="rounded-xl border overflow-hidden"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border)",
        }}
      >
        {feeds.length === 0 && (
          <div
            className="px-5 py-8 text-center text-sm"
            style={{ color: "var(--text-muted)" }}
          >
            {allFeeds.length ? "No feeds match" : "No feeds configured"}
          </div>
        )}
        {feeds.map((feed: any) => (
          <div
            key={feed.id}
            className="flex items-center gap-4 px-5 py-4 border-b last:border-b-0 hover:bg-zinc-800/30"
            style={{ borderColor: "var(--border)" }}
          >
            <div className="flex-1 min-w-0">
              <div
                className="text-sm font-medium"
                style={{
                  color: feed.enabled
                    ? "var(--text-primary)"
                    : "var(--text-muted)",
                }}
              >
                {feed.name}
              </div>
              <div
                className="text-xs mt-0.5 truncate font-mono"
                style={{ color: "var(--text-muted)" }}
              >
                {feed.url}
              </div>
              {feed.last_fetched && (
                <div className="flex items-center gap-1.5 mt-1">
                  <Clock
                    className="w-3 h-3"
                    style={{ color: "var(--text-muted)" }}
                  />
                  <span
                    className="text-xs"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {formatDistanceToNow(new Date(feed.last_fetched), {
                      addSuffix: true,
                    })}
                  </span>
                </div>
              )}
              {(feed.consecutive_failures ?? 0) > 0 && (
                <div
                  data-testid="feed-health-error"
                  className="mt-1.5 text-xs text-rose-400 truncate"
                  title={feed.last_error ?? ""}
                >
                  <span className="font-semibold">
                    {feed.consecutive_failures} consecutive failures
                  </span>
                  {feed.last_error && (
                    <span className="opacity-80">
                      {" "}
                      - {String(feed.last_error).split("\n")[0]}
                    </span>
                  )}
                </div>
              )}
            </div>
            <span
              className="text-xs px-2 py-0.5 rounded-full font-mono"
              style={{
                background: "rgba(59,130,246,0.1)",
                color: "#3b82f6",
                border: "1px solid rgba(59,130,246,0.2)",
              }}
            >
              {feed.feed_type}
            </span>
            <button
              onClick={() => toggle.mutate(feed.id)}
              title={feed.enabled ? "Disable feed" : "Enable feed"}
              style={{
                color: feed.enabled
                  ? "var(--accent-green)"
                  : "var(--text-muted)",
              }}
            >
              {feed.enabled ? (
                <ToggleRight className="w-6 h-6" />
              ) : (
                <ToggleLeft className="w-6 h-6" />
              )}
            </button>
          </div>
        ))}
      </div>

      {pages > 1 && (
        <div
          data-testid="feeds-pagination"
          className="flex items-center justify-center gap-1"
        >
          <button
            type="button"
            onClick={() => setPage(current - 1)}
            disabled={current <= 1}
            className="px-3 py-1.5 rounded-lg text-xs border disabled:opacity-40"
            style={controlStyle}
          >
            Prev
          </button>
          {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
            <button
              type="button"
              key={n}
              onClick={() => setPage(n)}
              className="px-3 py-1.5 rounded-lg text-xs border"
              style={
                n === current
                  ? {
                      ...controlStyle,
                      color: "var(--accent-amber)",
                      borderColor: "var(--accent-amber)",
                    }
                  : controlStyle
              }
            >
              {n}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setPage(current + 1)}
            disabled={current >= pages}
            className="px-3 py-1.5 rounded-lg text-xs border disabled:opacity-40"
            style={controlStyle}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
