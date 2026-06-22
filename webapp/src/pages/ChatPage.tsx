import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Download, Send, Sparkles, User, RefreshCw, Trash2 } from "lucide-react";
import { apiFetch } from "../utils/api";

type Role = "user" | "assistant" | "system";
interface Message { role: Role; content: string }

const PROVIDERS = [
	{ id: "lmstudio", label: "LM Studio", defaultUrl: "http://localhost:1234/v1" },
	{ id: "ollama", label: "Ollama", defaultUrl: "http://localhost:11434" },
	{ id: "openai", label: "OpenAI", defaultUrl: "https://api.openai.com/v1" },
	{ id: "anthropic", label: "Anthropic", defaultUrl: "https://api.anthropic.com/v1" },
	{ id: "deepseek", label: "DeepSeek", defaultUrl: "https://api.deepseek.com/v1" },
];

const PERSONALITIES = [
	{ id: "professional", label: "Professional", desc: "Concise and helpful" },
	{ id: "mentor", label: "Mentor", desc: "Patient and encouraging" },
	{ id: "sarcastic", label: "Sarcastic", desc: "Dry wit and sharp" },
	{ id: "pirate", label: "Pirate", desc: "Arr, nautical fun!" },
	{ id: "enthusiast", label: "Enthusiast", desc: "Over-the-top excitement" },
];

const SESSION_KEY = "aiw_chat_session";

function loadSession(): { messages: Message[]; provider: string; model: string; personality: string; baseUrl: string } {
	try {
		const raw = localStorage.getItem(SESSION_KEY);
		if (raw) return JSON.parse(raw);
	} catch { /* ignore */ }
	return { messages: [], provider: "lmstudio", model: "", personality: "professional", baseUrl: "" };
}

function saveSession(data: { messages: Message[]; provider: string; model: string; personality: string; baseUrl: string }) {
	try {
		localStorage.setItem(SESSION_KEY, JSON.stringify(data));
	} catch { /* ignore */ }
}

export default function ChatPage() {
	const [session, setSession] = useState(() => loadSession());
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const [models, setModels] = useState<string[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [refining, setRefining] = useState(false);
	const [showPersonalityPicker, setShowPersonalityPicker] = useState(false);
	const bottomRef = useRef<HTMLDivElement>(null);

	const providerCfg = PROVIDERS.find((p) => p.id === session.provider);

	const set = useCallback((partial: Partial<typeof session>) => {
		setSession((prev) => {
			const next = { ...prev, ...partial };
			saveSession(next);
			return next;
		});
	}, []);

	const fetchModels = useCallback(async (provider: string, url: string) => {
		try {
			const params = new URLSearchParams({ provider });
			if (url) params.set("base_url", url);
			const r = await fetch(`/api/llm/models?${params}`);
			if (r.ok) {
				const d = await r.json();
				setModels(d.models || []);
				if (d.models?.length && !d.models.includes(session.model)) {
					set({ model: d.models[0] });
				}
			}
		} catch { /* ignore */ }
	}, [session.model, set]);

	useEffect(() => {
		const url = session.baseUrl || providerCfg?.defaultUrl || "";
		fetchModels(session.provider, url);
	}, [session.provider, session.baseUrl, fetchModels, providerCfg]);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [session.messages]);

	const sendMessage = async (text: string, refine: boolean = false) => {
		if (!text.trim() || loading) return;
		const userMsg: Message = { role: "user", content: text.trim() };

		if (refine) {
			setRefining(true);
			try {
				const refinePrompt = `Rewrite and expand the following prompt to be more detailed, specific, and effective for an LLM. Keep the original intent but make it clearer:\n\n${text.trim()}`;
				const body: Record<string, string> = {
					provider: session.provider,
					model: session.model || providerCfg?.defaultUrl || "",
					prompt: refinePrompt,
					personality: "professional",
				};
				if (session.baseUrl) body.base_url = session.baseUrl;
				const r = await apiFetch("/api/llm/chat", {
					method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
				});
				const data = await r.json();
				if (data.reply) {
					setInput(data.reply);
				}
			} catch { /* ignore */ }
			setRefining(false);
			return;
		}

		set({ messages: [...session.messages, userMsg] });
		setInput("");
		setLoading(true);
		setError(null);

		try {
			const body: Record<string, any> = {
				provider: session.provider,
				model: session.model || "gemma3:1b",
				messages: session.messages,
				prompt: text.trim(),
				personality: session.personality,
			};
			if (session.baseUrl) body.base_url = session.baseUrl;
			const r = await apiFetch("/api/llm/chat", {
				method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
			});
			const data = await r.json();
			if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
			const reply: Message = { role: "assistant", content: data.reply || "No response" };
			set({ messages: [...session.messages, userMsg, reply] });
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			setError(msg);
			set({ messages: [...session.messages, userMsg, { role: "assistant", content: `Error: ${msg}` }] });
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex flex-col h-[calc(100vh-6rem)] max-w-5xl mx-auto">
			{/* Top bar: provider, model, personality, actions */}
			<div className="flex items-center justify-between gap-2 mb-3 px-2 flex-wrap">
				<div className="flex items-center gap-2 flex-wrap">
					<select value={session.provider} onChange={(e) => set({ provider: e.target.value })}
						className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white">
						{PROVIDERS.map((p) => (<option key={p.id} value={p.id}>{p.label}</option>))}
					</select>
					{session.provider === "openai" || session.provider === "deepseek" ? (
						<input type="text" value={session.baseUrl}
							onChange={(e) => set({ baseUrl: e.target.value })}
							placeholder={providerCfg?.defaultUrl || "https://api.openai.com/v1"}
							className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white w-44" />
					) : null}
					{models.length > 0 ? (
						<select value={session.model} onChange={(e) => set({ model: e.target.value })}
							className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white">
							{models.map((m) => (<option key={m} value={m}>{m}</option>))}
						</select>
					) : (
						<input type="text" value={session.model}
							onChange={(e) => set({ model: e.target.value })}
							placeholder="model name"
							className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white w-32" />
					)}
					<button onClick={() => fetchModels(session.provider, session.baseUrl || providerCfg?.defaultUrl || "")}
						className="p-1.5 rounded-lg hover:bg-white/5 text-zinc-400" title="Refresh models">
						<RefreshCw className="w-3.5 h-3.5" />
					</button>
				</div>
				<div className="flex items-center gap-2">
					{session.messages.length > 0 && (
						<button onClick={() => {
							const text = session.messages.filter(m => m.role !== "system")
								.map(m => `${m.role === "user" ? "You" : "AI"}: ${m.content}`).join("\n\n---\n\n");
							const blob = new Blob([text], { type: "text/plain" });
							const url = URL.createObjectURL(blob);
							const a = document.createElement("a");
							a.href = url; a.download = `aiwatcher-chat-${Date.now()}.txt`;
							a.click(); URL.revokeObjectURL(url);
						}}
							className="p-1.5 rounded-lg hover:bg-white/5 text-zinc-500 hover:text-green-400 transition-colors"
							title="Export chat">
							<Download className="w-3.5 h-3.5" />
						</button>
					)}
					<div className="relative">
						<button onClick={() => setShowPersonalityPicker(!showPersonalityPicker)}
							className="px-2 py-1.5 rounded-lg text-xs border border-white/10 hover:bg-white/5 text-zinc-300 transition-colors">
							{PERSONALITIES.find((p) => p.id === session.personality)?.label || "Professional"}
						</button>
						{showPersonalityPicker && (
							<>
								<div className="fixed inset-0 z-10" onClick={() => setShowPersonalityPicker(false)} />
								<div className="absolute right-0 top-full mt-1 z-20 w-48 bg-zinc-900 border border-white/10 rounded-xl shadow-2xl overflow-hidden">
									{PERSONALITIES.map((p) => (
										<button key={p.id} onClick={() => { set({ personality: p.id }); setShowPersonalityPicker(false); }}
											className={`w-full text-left px-3 py-2.5 text-sm hover:bg-white/5 transition-colors ${session.personality === p.id ? "text-indigo-400 bg-indigo-500/10" : "text-zinc-300"}`}>
											<div className="font-medium">{p.label}</div>
											<div className="text-xs text-zinc-500">{p.desc}</div>
										</button>
									))}
								</div>
							</>
						)}
					</div>
					<button onClick={() => { set({ messages: [] }); setError(null); }}
						className="p-1.5 rounded-lg hover:bg-white/5 text-zinc-500 hover:text-red-400 transition-colors" title="Clear chat">
						<Trash2 className="w-3.5 h-3.5" />
					</button>
				</div>
			</div>

			{/* Messages */}
			<div className="flex-1 overflow-y-auto space-y-3 px-2 pb-4">
				{session.messages.length === 0 && (
					<div className="text-center text-zinc-500 text-sm mt-12">
						<Bot className="w-12 h-12 mx-auto mb-3 opacity-20" />
						<p>Send a message to start chatting.</p>
						<p className="text-xs mt-1">Personality: <strong>{PERSONALITIES.find((p) => p.id === session.personality)?.label}</strong></p>
						<p className="text-xs text-zinc-600">Model: {session.model || "not selected"} · {providerCfg?.label}</p>
					</div>
				)}
				{session.messages.map((m, i) => (
					m.role !== "system" && (
						<div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
							{m.role === "assistant" && (
								<div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center shrink-0 mt-1">
									<Bot className="w-4 h-4 text-indigo-400" />
								</div>
							)}
							<div className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
								m.role === "user" ? "bg-indigo-500/20 text-white" : "bg-white/5 text-zinc-200"
							}`}>
								{m.content}
							</div>
							{m.role === "user" && (
								<div className="w-7 h-7 rounded-full bg-indigo-500/30 flex items-center justify-center shrink-0 mt-1">
									<User className="w-4 h-4 text-indigo-300" />
								</div>
							)}
						</div>
					)
				))}
				{loading && (
					<div className="flex gap-3">
						<div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center shrink-0">
							<Bot className="w-4 h-4 text-indigo-400" />
						</div>
						<div className="bg-white/5 rounded-xl px-4 py-2.5">
							<div className="flex gap-1">
								<div className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "0ms" }} />
								<div className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "150ms" }} />
								<div className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "300ms" }} />
							</div>
						</div>
					</div>
				)}
				{error && !loading && <p className="text-xs text-red-400 text-center">{error}</p>}
				<div ref={bottomRef} />
			</div>

			{/* Input */}
			<div className="flex gap-2 p-2 border-t border-white/5 items-end">
				<div className="flex-1 flex gap-2">
					<input type="text" value={input}
						onChange={(e) => setInput(e.target.value)}
						onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
						placeholder="Ask anything..." disabled={loading}
						className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-indigo-500/50 transition-colors" />
					<button onClick={() => sendMessage(input, true)} disabled={refining || !input.trim()}
						className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 disabled:opacity-30 transition-colors"
						title="Refine prompt with AI">
						<Sparkles className={`w-4 h-4 ${refining ? "animate-pulse" : ""}`} />
					</button>
				</div>
				<button onClick={() => sendMessage(input)} disabled={loading || !input.trim()}
					className="p-2.5 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/30 disabled:opacity-30 transition-colors">
					<Send className="w-4 h-4" />
				</button>
			</div>
		</div>
	);
}
