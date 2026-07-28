import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  AlertCircle,
  AlertTriangle,
  Boxes,
  Eye,
  EyeOff,
  RefreshCw,
  Save,
  Settings2,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../utils/api";

async function fetchCaps() {
  const r = await apiFetch("/api/capabilities");
  return r.json();
}

async function fetchEnv() {
  const r = await apiFetch("/api/env");
  return r.json();
}

async function saveEnv(payload: Record<string, string>) {
  const r = await apiFetch("/api/env", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error("Failed to save settings");
  return r.json();
}

export interface HfSettings {
  huggingface_enabled: boolean;
  hf_token_set: boolean;
  hf_watchlist: string;
  hf_poll_interval_minutes: number;
  hf_poll_max_per_author: number;
  hf_min_weight_bytes: number;
  hf_include_papers: boolean;
  hf_include_models: boolean;
  hf_include_modified: boolean;
  hf_include_trending: boolean;
  hf_discovery_enabled: boolean;
  hf_discovery_limit: number;
  hf_discovery_max_age_days: number;
}

async function fetchHfSettings(): Promise<HfSettings> {
  const r = await apiFetch("/api/huggingface/settings");
  if (!r.ok) throw new Error("Failed to load Hugging Face settings");
  return r.json();
}

async function saveHfSettings(payload: HfSettings & { hf_token?: string }) {
  const r = await apiFetch("/api/huggingface/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error("Failed to save Hugging Face settings");
  return r.json();
}

async function reloadConfig() {
  const r = await apiFetch("/api/config/reload", { method: "POST" });
  if (!r.ok) throw new Error("Failed to reload config");
  return r.json();
}

async function testLLM(payload: {
  provider: string;
  key?: string;
  model: string;
  base_url?: string;
}) {
  const r = await apiFetch("/api/test-llm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const err = await r.json();
    throw new Error(err.error || "Connection failed");
  }
  return r.json();
}

export function SettingsPage() {
  const qc = useQueryClient();
  const { data: caps } = useQuery({
    queryKey: ["capabilities"],
    queryFn: fetchCaps,
  });
  const { data: initialEnv, isLoading } = useQuery({
    queryKey: ["env"],
    queryFn: fetchEnv,
  });
  const { data: initialHf, isLoading: hfLoading } = useQuery({
    queryKey: ["hf-settings"],
    queryFn: fetchHfSettings,
  });

  const [env, setEnv] = useState<Record<string, string>>({});
  const [hf, setHf] = useState<HfSettings | null>(null);
  const [hfToken, setHfToken] = useState("");
  const [showHfToken, setShowHfToken] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [hfSaved, setHfSaved] = useState(false);

  useEffect(() => {
    if (initialEnv) {
      setEnv(initialEnv);
    }
  }, [initialEnv]);

  useEffect(() => {
    if (initialHf) {
      setHf(initialHf);
    }
  }, [initialHf]);

  const mutation = useMutation({
    mutationFn: async () => {
      await saveEnv(env);
      if (hf) {
        await saveHfSettings({
          ...hf,
          ...(hfToken.trim() ? { hf_token: hfToken.trim() } : {}),
        });
      }
      await reloadConfig();
    },
    onSuccess: () => {
      setIsSaved(true);
      setHfSaved(true);
      setHfToken("");
      qc.invalidateQueries();
      setTimeout(() => {
        setIsSaved(false);
        setHfSaved(false);
      }, 3000);
    },
  });

  const [llmModels, setLlmModels] = useState<string[]>([]);

  const fetchModels = useCallback(
    async (provider: string, baseUrl: string, key?: string) => {
      const params = new URLSearchParams({ provider });
      if (baseUrl) params.set("base_url", baseUrl);
      if (key) params.set("key", key);
      try {
        const r = await fetch(`/api/llm/models?${params}`);
        if (r.ok) {
          const d = await r.json();
          setLlmModels(d.models || []);
        }
      } catch {
        /* ignore */
      }
    },
    [],
  );

  useEffect(() => {
    const p = env.LLM_PROVIDER || "lmstudio";
    fetchModels(p, env.LLM_BASE_URL || "", env.ANTHROPIC_API_KEY || "");
  }, [env.LLM_PROVIDER, env.LLM_BASE_URL, env.ANTHROPIC_API_KEY, fetchModels]);

  const testMutation = useMutation({
    mutationFn: testLLM,
    onSuccess: () => {
      setTimeout(() => testMutation.reset(), 3000);
      fetchModels(
        env.LLM_PROVIDER || "lmstudio",
        env.LLM_BASE_URL || "",
        env.ANTHROPIC_API_KEY || "",
      );
    },
  });

  const handleChange = (key: string, value: string) => {
    setEnv((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    mutation.mutate();
  };

  const patchHf = <K extends keyof HfSettings>(
    key: K,
    value: HfSettings[K],
  ) => {
    setHf((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const integrations = caps?.integrations ?? {};
  const features = caps?.features ?? {};

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-20">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/70">
          Settings & Configuration
        </h1>
        <button
          onClick={handleSave}
          disabled={mutation.isPending}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-amber-500 hover:bg-amber-400 text-amber-950 transition-all shadow-[0_0_20px_rgba(245,158,11,0.3)] hover:shadow-[0_0_30px_rgba(245,158,11,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {mutation.isPending ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Changes
        </button>
      </div>

      {env.LLM_PROVIDER === "anthropic" && !env.ANTHROPIC_API_KEY && (
        <div className="flex items-center gap-4 p-5 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-500 animate-in fade-in slide-in-from-top-4">
          <div className="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center shrink-0">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <p className="font-bold">Anthropic API Key Missing</p>
            <p className="text-sm opacity-80">
              Distillation is currently using Anthropic but no key is provided.
            </p>
          </div>
        </div>
      )}

      {isSaved && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 animate-in fade-in slide-in-from-top-4">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium">Settings saved</p>
            <p className="text-xs opacity-80">
              {hfSaved
                ? "Hugging Face config applied immediately. Scheduler interval changes need a backend restart."
                : "Config reloaded. Restart backend if poll intervals changed."}
            </p>
          </div>
        </div>
      )}

      {/* Hugging Face */}
      <section className="rounded-2xl border border-amber-500/20 bg-zinc-900/40 backdrop-blur-md overflow-hidden">
        <div className="p-5 border-b border-white/10 flex items-center gap-3 bg-amber-500/5">
          <Boxes className="w-5 h-5 text-amber-400" />
          <div>
            <h2 className="text-base font-semibold text-white">Hugging Face</h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              Author watchlist, discovery, polling — saved to .env, hot-reloaded
            </p>
          </div>
        </div>

        {hfLoading || !hf ? (
          <div className="p-8 text-center text-zinc-500 text-sm">Loading…</div>
        ) : (
          <div className="p-5 grid gap-6 md:grid-cols-2">
            <div className="space-y-4">
              <label className="flex items-center justify-between cursor-pointer">
                <div>
                  <div className="text-sm font-medium text-zinc-200">
                    Enable HF polling
                  </div>
                  <div className="text-xs text-zinc-500">
                    Master switch for scheduler + manual poll
                  </div>
                </div>
                <div className="relative inline-flex items-center">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={hf.huggingface_enabled}
                    onChange={(e) =>
                      patchHf("huggingface_enabled", e.target.checked)
                    }
                  />
                  <div className="w-11 h-6 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500" />
                </div>
              </label>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-400">
                  HF_TOKEN {hf.hf_token_set && "(configured)"}
                </label>
                <div className="relative">
                  <input
                    type={showHfToken ? "text" : "password"}
                    value={hfToken}
                    onChange={(e) => setHfToken(e.target.value)}
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                    placeholder={
                      hf.hf_token_set
                        ? "Leave blank to keep current token"
                        : "hf_…"
                    }
                  />
                  <button
                    type="button"
                    onClick={() => setShowHfToken(!showHfToken)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                  >
                    {showHfToken ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-400">
                  Author watchlist
                </label>
                <textarea
                  value={hf.hf_watchlist}
                  onChange={(e) => patchHf("hf_watchlist", e.target.value)}
                  rows={3}
                  className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500 resize-y"
                  placeholder="Jackrong,Qwen,bartowski,mradermacher,unsloth"
                />
                <p className="text-[10px] text-zinc-600">
                  Comma-separated HF usernames — polled by createdAt
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-400">
                    Poll interval (min)
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={hf.hf_poll_interval_minutes}
                    onChange={(e) =>
                      patchHf(
                        "hf_poll_interval_minutes",
                        Number(e.target.value),
                      )
                    }
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-400">
                    Max per author
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={hf.hf_poll_max_per_author}
                    onChange={(e) =>
                      patchHf("hf_poll_max_per_author", Number(e.target.value))
                    }
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-400">
                  Min weight bytes
                </label>
                <input
                  type="number"
                  min={0}
                  step={100000}
                  value={hf.hf_min_weight_bytes}
                  onChange={(e) =>
                    patchHf("hf_min_weight_bytes", Number(e.target.value))
                  }
                  className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                />
                <p className="text-[10px] text-zinc-600">
                  Skip empty repos until safetensors/gguf exceeds this size
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider text-amber-400/80">
                Sources
              </h3>
              <div className="space-y-3 p-4 rounded-xl bg-black/20 border border-white/5">
                {[
                  {
                    key: "hf_discovery_enabled" as const,
                    label: "Discovery channel",
                    desc: "Recent high-like models outside watchlist",
                  },
                  {
                    key: "hf_include_papers" as const,
                    label: "Daily papers",
                    desc: "HF curated ML papers feed",
                  },
                  {
                    key: "hf_include_models" as const,
                    label: "Global new models",
                    desc: "Site-wide createdAt firehose (noisy)",
                  },
                  {
                    key: "hf_include_modified" as const,
                    label: "Modified models",
                    desc: "Quant/card edits — lower priority",
                  },
                  {
                    key: "hf_include_trending" as const,
                    label: "Trending",
                    desc: "HF trending repos",
                  },
                ].map(({ key, label, desc }) => (
                  <label
                    key={key}
                    className="flex items-center justify-between cursor-pointer group"
                  >
                    <div className="space-y-0.5 pr-3">
                      <div className="text-sm font-medium text-zinc-200 group-hover:text-white">
                        {label}
                      </div>
                      <div className="text-xs text-zinc-500">{desc}</div>
                    </div>
                    <div className="relative inline-flex items-center shrink-0">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={hf[key]}
                        onChange={(e) => patchHf(key, e.target.checked)}
                      />
                      <div className="w-11 h-6 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500" />
                    </div>
                  </label>
                ))}
              </div>

              {hf.hf_discovery_enabled && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-400">
                      Discovery limit
                    </label>
                    <input
                      type="number"
                      min={1}
                      value={hf.hf_discovery_limit}
                      onChange={(e) =>
                        patchHf("hf_discovery_limit", Number(e.target.value))
                      }
                      className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-400">
                      Discovery max age (days)
                    </label>
                    <input
                      type="number"
                      min={1}
                      value={hf.hf_discovery_max_age_days}
                      onChange={(e) =>
                        patchHf(
                          "hf_discovery_max_age_days",
                          Number(e.target.value),
                        )
                      }
                      className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {/* ENV Editor */}
      <section className="rounded-2xl border border-white/10 bg-zinc-900/40 backdrop-blur-md overflow-hidden">
        <div className="p-5 border-b border-white/10 flex items-center gap-3 bg-white/5">
          <Settings2 className="w-5 h-5 text-indigo-400" />
          <h2 className="text-base font-semibold text-white">
            Environment Variables (.env)
          </h2>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-zinc-500 text-sm">
            Loading configuration...
          </div>
        ) : (
          <div className="p-5 grid gap-6 md:grid-cols-2">
            {/* Intelligence Settings */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2 text-indigo-400">
                Intelligence & LLM
              </h3>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-400">
                  LLM PROVIDER
                </label>
                <select
                  value={env.LLM_PROVIDER || "anthropic"}
                  onChange={(e) => handleChange("LLM_PROVIDER", e.target.value)}
                  className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                >
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="ollama">Ollama (Local)</option>
                  <option value="lmstudio">LM Studio (Local)</option>
                </select>
              </div>

              {env.LLM_PROVIDER === "anthropic" ? (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-zinc-400">
                      ANTHROPIC_API_KEY
                    </label>
                    <button
                      onClick={() =>
                        testMutation.mutate({
                          provider: "anthropic",
                          key: env.ANTHROPIC_API_KEY,
                          model: env.DISTILLATION_MODEL,
                        })
                      }
                      disabled={
                        testMutation.isPending || !env.ANTHROPIC_API_KEY
                      }
                      className={clsx(
                        "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded transition-all",
                        testMutation.isSuccess
                          ? "bg-emerald-500/20 text-emerald-500"
                          : testMutation.isError
                            ? "bg-rose-500/20 text-rose-500"
                            : "bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10 disabled:opacity-50",
                      )}
                    >
                      {testMutation.isPending
                        ? "Testing..."
                        : testMutation.isSuccess
                          ? "Success!"
                          : testMutation.isError
                            ? "Test Failed"
                            : "Test Connection"}
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={env.ANTHROPIC_API_KEY || ""}
                      onChange={(e) =>
                        handleChange("ANTHROPIC_API_KEY", e.target.value)
                      }
                      className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                      placeholder="sk-ant-..."
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                    >
                      {showPassword ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-zinc-400">
                      LLM BASE URL (OPTIONAL)
                    </label>
                    <button
                      onClick={() =>
                        testMutation.mutate({
                          provider: env.LLM_PROVIDER,
                          model: env.DISTILLATION_MODEL,
                          base_url: env.LLM_BASE_URL,
                        })
                      }
                      disabled={testMutation.isPending}
                      className={clsx(
                        "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded transition-all",
                        testMutation.isSuccess
                          ? "bg-emerald-500/20 text-emerald-500"
                          : testMutation.isError
                            ? "bg-rose-500/20 text-rose-500"
                            : "bg-white/5 text-zinc-500 hover:text-zinc-300 hover:bg-white/10 disabled:opacity-50",
                      )}
                    >
                      {testMutation.isPending
                        ? "Testing..."
                        : testMutation.isSuccess
                          ? "Success!"
                          : testMutation.isError
                            ? "Test Failed"
                            : "Test Connection"}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={env.LLM_BASE_URL || ""}
                    onChange={(e) =>
                      handleChange("LLM_BASE_URL", e.target.value)
                    }
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                    placeholder={
                      env.LLM_PROVIDER === "ollama"
                        ? "http://localhost:11434/v1"
                        : "http://localhost:1234/v1"
                    }
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-400">
                  DISTILLATION_MODEL
                </label>
                {llmModels.length > 0 ? (
                  <select
                    value={env.DISTILLATION_MODEL || ""}
                    onChange={(e) =>
                      handleChange("DISTILLATION_MODEL", e.target.value)
                    }
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                  >
                    <option value="">Select a model…</option>
                    {llmModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={env.DISTILLATION_MODEL || ""}
                    onChange={(e) =>
                      handleChange("DISTILLATION_MODEL", e.target.value)
                    }
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                    placeholder={
                      env.LLM_PROVIDER === "anthropic"
                        ? "claude-3-5-sonnet-latest"
                        : "llama3"
                    }
                  />
                )}
                {llmModels.length > 0 && (
                  <p className="text-[10px] text-zinc-500 mt-1">
                    {llmModels.length} model{llmModels.length !== 1 ? "s" : ""}{" "}
                    available from {env.LLM_BASE_URL}
                  </p>
                )}
              </div>

              {testMutation.isError && (
                <p className="text-[10px] text-rose-500 mt-1 font-mono">
                  {(testMutation.error as any).message}
                </p>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-400">
                    ALERT_THRESHOLD
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={env.ALERT_THRESHOLD || "8.5"}
                    onChange={(e) =>
                      handleChange("ALERT_THRESHOLD", e.target.value)
                    }
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-400">
                    ALERT_HOUR_UTC
                  </label>
                  <input
                    type="number"
                    value={env.ALERT_HOUR_UTC || "4"}
                    onChange={(e) =>
                      handleChange("ALERT_HOUR_UTC", e.target.value)
                    }
                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-400">
                  EMAIL_RECIPIENTS
                </label>
                <input
                  type="text"
                  value={env.EMAIL_RECIPIENTS || ""}
                  onChange={(e) =>
                    handleChange("EMAIL_RECIPIENTS", e.target.value)
                  }
                  className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition-colors"
                  placeholder="sandra@example.com, steve@example.com"
                />
              </div>
            </div>

            {/* Feature Toggles */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
                Integrations
              </h3>

              <div className="space-y-3 p-4 rounded-xl bg-black/20 border border-white/5">
                {[
                  {
                    key: "ROBOFANG_ENABLED",
                    label: "Robofang Alerts",
                    desc: "Push critical events to council",
                  },
                  {
                    key: "EMAIL_ENABLED",
                    label: "Email Digest",
                    desc: "Send daily digest to recipients",
                  },
                  {
                    key: "CALIBRE_ENABLED",
                    label: "Calibre Sync",
                    desc: "Archive digests as eBooks",
                  },
                  {
                    key: "GMAIL_ENABLED",
                    label: "Gmail Alpha Signal",
                    desc: "Parse newsletters directly",
                  },
                ].map(({ key, label, desc }) => (
                  <label
                    key={key}
                    className="flex items-center justify-between cursor-pointer group"
                  >
                    <div className="space-y-0.5">
                      <div className="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">
                        {label}
                      </div>
                      <div className="text-xs text-zinc-500">{desc}</div>
                    </div>
                    <div className="relative inline-flex items-center">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={env[key] === "true" || env[key] === "1"}
                        onChange={(e) =>
                          handleChange(key, e.target.checked ? "true" : "false")
                        }
                      />
                      <div className="w-11 h-6 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500" />
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Runtime Status */}
      <section className="rounded-2xl border border-white/10 bg-zinc-900/40 backdrop-blur-md overflow-hidden">
        <div className="p-5 border-b border-white/10 flex items-center gap-3 bg-white/5">
          <Zap className="w-5 h-5 text-amber-400" />
          <h2 className="text-base font-semibold text-white">
            Live Server Capabilities
          </h2>
        </div>
        <div className="p-5">
          <p className="text-xs text-zinc-400 mb-4">
            These values reflect the currently running FastMCP backend.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="flex flex-col gap-1.5 p-3 rounded-xl bg-black/20 border border-white/5">
              <span className="text-xs uppercase tracking-wider text-zinc-500 font-semibold truncate">
                PROVIDER
              </span>
              <span className="text-sm font-mono font-medium text-indigo-400 uppercase">
                {caps?.server?.provider || "anthropic"}
              </span>
            </div>
            {Object.entries({
              ...features,
              ...Object.fromEntries(
                Object.entries(integrations).map(([k, v]) => [`${k}`, v]),
              ),
            }).map(([key, value]) => (
              <div
                key={key}
                className="flex flex-col gap-1.5 p-3 rounded-xl bg-black/20 border border-white/5"
              >
                <span className="text-xs uppercase tracking-wider text-zinc-500 font-semibold truncate">
                  {key.replace(/_/g, " ")}
                </span>
                <span
                  className={`text-sm font-mono font-medium ${value ? "text-emerald-400" : "text-zinc-600"}`}
                >
                  {value ? "ENABLED" : "DISABLED"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
