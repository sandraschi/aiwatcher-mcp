import { useMutation } from "@tanstack/react-query";
import { Check, Loader2, Search, ShieldAlert, Volume2 } from "lucide-react";
import { useState } from "react";
import { apiFetch } from "../utils/api";

export function TestsPage() {
  return (
    <div className="space-y-8 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1
            className="text-xl font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            System Tests
          </h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Debug and validate core integrations and AI logic.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SpeechTest />
        <SourceFinderTest />
      </div>
    </div>
  );
}

function SpeechTest() {
  const [text, setText] = useState(
    "This is a test of the emergency news broadcast system.",
  );

  const speakMutation = useMutation({
    mutationFn: (t: string) =>
      apiFetch("/api/test/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: t }),
      }).then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "Speech test failed");
        return data;
      }),
  });

  return (
    <div
      className="p-6 rounded-2xl border space-y-4"
      style={{
        background: "var(--bg-secondary)",
        borderColor: "var(--border)",
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ background: "rgba(245,158,11,0.1)" }}
        >
          <Volume2 className="w-5 h-5 text-amber-500" />
        </div>
        <h2 className="font-semibold" style={{ color: "var(--text-primary)" }}>
          Speech Output
        </h2>
      </div>

      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        Verify connection to <code>speechops-mcp</code>.
      </p>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full h-24 p-3 rounded-xl border text-sm outline-none resize-none"
        style={{
          background: "var(--bg-surface)",
          borderColor: "var(--border)",
          color: "var(--text-primary)",
        }}
      />

      <button
        disabled={speakMutation.isPending}
        onClick={() => speakMutation.mutate(text)}
        className="w-full py-2.5 rounded-xl text-sm font-medium transition-all active:scale-95 disabled:opacity-50"
        style={{ background: "var(--accent-amber)", color: "#000" }}
      >
        {speakMutation.isPending ? (
          <Loader2 className="w-4 h-4 animate-spin mx-auto" />
        ) : (
          "Trigger Announcement"
        )}
      </button>

      {speakMutation.isSuccess && (
        <div className="flex items-center gap-2 text-xs text-green-500 bg-green-500/10 p-2 rounded-lg">
          <Check className="w-3.5 h-3.5" />
          Speech command sent successfully
        </div>
      )}

      {speakMutation.isError && (
        <div className="flex items-center gap-2 text-xs text-red-500 bg-red-500/10 p-2 rounded-lg">
          <ShieldAlert className="w-3.5 h-3.5" />
          {speakMutation.error.message}
        </div>
      )}
    </div>
  );
}

function SourceFinderTest() {
  const [topic, setTopic] = useState("");
  const [result, setResult] = useState<any>(null);

  const findMutation = useMutation({
    mutationFn: (t: string) =>
      apiFetch("/api/test/discover-sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: t }),
      }).then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "Discovery failed");
        return data;
      }),
    onSuccess: (data) => setResult(data),
  });

  return (
    <div
      className="p-6 rounded-2xl border space-y-4"
      style={{
        background: "var(--bg-secondary)",
        borderColor: "var(--border)",
      }}
    >
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ background: "rgba(59,130,246,0.1)" }}
        >
          <Search className="w-5 h-5 text-blue-500" />
        </div>
        <h2 className="font-semibold" style={{ color: "var(--text-primary)" }}>
          Source Finder
        </h2>
      </div>

      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        Test the AI's ability to discover niche feeds for a topic.
      </p>

      <div className="flex gap-2">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. Vintage Yachts"
          className="flex-1 px-3 py-2 rounded-xl border text-sm outline-none"
          style={{
            background: "var(--bg-surface)",
            borderColor: "var(--border)",
            color: "var(--text-primary)",
          }}
          onKeyDown={(e) => e.key === "Enter" && findMutation.mutate(topic)}
        />
        <button
          disabled={findMutation.isPending || !topic}
          onClick={() => findMutation.mutate(topic)}
          className="px-4 rounded-xl text-sm font-medium transition-all active:scale-95 disabled:opacity-50"
          style={{ background: "var(--accent-amber)", color: "#000" }}
        >
          {findMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            "Find"
          )}
        </button>
      </div>

      {findMutation.isError && (
        <div className="flex items-center gap-2 text-xs text-red-500 bg-red-500/10 p-2 rounded-lg">
          <ShieldAlert className="w-3.5 h-3.5" />
          {findMutation.error.message}
        </div>
      )}

      {result && (
        <div className="space-y-3 pt-2">
          <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 space-y-2">
            <div className="text-[10px] font-bold uppercase text-zinc-500">
              Suggested Persona
            </div>
            <div className="text-xs text-zinc-300 font-medium">
              {result.name}
            </div>
            <div className="text-[10px] text-zinc-400 italic leading-relaxed">
              {result.system_prompt}
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="text-[10px] font-bold uppercase text-zinc-500 px-1">
              Discovered Feeds
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto pr-1 scrollbar-thin">
              {result.suggested_feeds?.map((f: any, i: number) => (
                <div
                  key={i}
                  className="p-2 rounded bg-zinc-800/50 border border-zinc-700/50 flex flex-col gap-0.5 transition-colors hover:bg-zinc-800"
                >
                  <span className="text-[10px] font-medium text-zinc-200">
                    {f.name}
                  </span>
                  <span className="text-[8px] text-zinc-500 truncate">
                    {f.url}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
