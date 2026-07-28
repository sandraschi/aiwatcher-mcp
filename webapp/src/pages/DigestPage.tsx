import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertCircle, Eye, RefreshCw, Send, Sparkles } from "lucide-react";
import { useState } from "react";
import { apiFetch } from "../utils/api";

async function fetchDigest(hours: number) {
  const r = await apiFetch(`/api/digest/preview?hours=${hours}`);
  if (!r.ok) {
    const err = await r.json();
    throw new Error(err.error || "Failed to generate digest");
  }
  return r.json();
}

export function DigestPage() {
  const qc = useQueryClient();
  const [hours, setHours] = useState(24);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["digest", hours],
    queryFn: () => fetchDigest(hours),
    enabled: false,
    retry: false,
  });

  const send = useMutation({
    mutationFn: async () => {
      const r = await apiFetch("/api/digest/send", { method: "POST" });
      return r.json();
    },
  });

  // Mutation to poll and distill in one go
  const sync = useMutation({
    mutationFn: async () => {
      await apiFetch("/api/poll", { method: "POST" });
      await apiFetch("/api/distill", { method: "POST" });
    },
    onSuccess: () => {
      qc.invalidateQueries();
      refetch();
    },
  });

  const isEmpty = data && (!data.text_body || data.subject === "No news today");

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Daily Intelligence Digest
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Curated summary for Sandra & Steve
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
          </select>

          <button
            onClick={() => refetch()}
            disabled={isFetching || sync.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-all disabled:opacity-50"
          >
            {isFetching ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            Generate
          </button>

          <button
            onClick={() => send.mutate()}
            disabled={send.isPending || !data?.text_body}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-amber-500 hover:bg-amber-400 text-amber-950 transition-all disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
            {send.isPending ? "Sending..." : "Send Email"}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-bold text-sm">Generation Failed</p>
            <p className="text-xs opacity-80 mt-1">{(error as any).message}</p>
          </div>
        </div>
      )}

      {send.data && (
        <div
          className={clsx(
            "p-4 rounded-xl border flex items-center gap-3",
            send.data.sent
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-500"
              : "bg-rose-500/10 border-rose-500/20 text-rose-500",
          )}
        >
          <div className="w-8 h-8 rounded-lg bg-current/10 flex items-center justify-center">
            <Send className="w-4 h-4" />
          </div>
          <p className="text-sm font-medium">
            {send.data.sent
              ? "Digest dispatched successfully."
              : `Failed to send: ${send.data.error || "Check email settings"}`}
          </p>
        </div>
      )}

      {isLoading || isFetching ? (
        <div className="space-y-4">
          <div className="h-20 rounded-2xl bg-white/5 animate-pulse" />
          <div className="h-96 rounded-2xl bg-white/5 animate-pulse" />
        </div>
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center rounded-3xl border border-dashed border-white/10 bg-white/[0.02]">
          <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
            <RefreshCw className="w-8 h-8 text-zinc-600" />
          </div>
          <h2 className="text-xl font-semibold text-white">
            No items found for this period
          </h2>
          <p className="text-zinc-500 mt-2 max-w-sm">
            There are no news items from the last {hours} hours that have been
            processed yet.
          </p>
          <button
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className="mt-6 flex items-center gap-2 px-6 py-3 rounded-2xl bg-white/10 hover:bg-white/20 text-white font-medium transition-all"
          >
            {sync.isPending ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            Refresh & Distill Now
          </button>
        </div>
      ) : data ? (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="p-6 rounded-2xl border border-white/10 bg-zinc-900/40 backdrop-blur-md">
            <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/5">
              <span className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold">
                Digest Subject
              </span>
              <a
                href={`/api/digest/html?hours=${hours}`}
                target="_blank"
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                rel="noreferrer"
              >
                <Eye className="w-3 h-3" /> View HTML Version
              </a>
            </div>
            <h2 className="text-lg font-medium text-white">{data.subject}</h2>
          </div>

          <div className="p-6 rounded-2xl border border-white/10 bg-zinc-900/40 backdrop-blur-md">
            <span className="text-[10px] uppercase tracking-widest text-zinc-500 font-bold block mb-4">
              Content Preview
            </span>
            <pre className="text-sm leading-relaxed text-zinc-300 whitespace-pre-wrap font-sans">
              {data.text_body}
            </pre>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 px-6 text-center rounded-3xl border border-dashed border-white/10 bg-white/[0.02]">
          <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-4 text-indigo-400">
            <Sparkles className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-semibold text-white">
            Generate Your First Digest
          </h2>
          <p className="text-zinc-500 mt-2 max-w-sm">
            Click the generate button to analyze recent news and create a
            summary for Sandra & Steve.
          </p>
          <button
            onClick={() => refetch()}
            className="mt-6 px-8 py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-lg shadow-indigo-500/20 transition-all"
          >
            Generate Now
          </button>
        </div>
      )}
    </div>
  );
}
