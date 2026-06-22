import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Bot, User, RefreshCw } from "lucide-react";
import { apiFetch } from "../utils/api";

type Role = "user" | "assistant";
interface Message { role: Role; content: string }

const PROVIDERS = [
	{ id: "lmstudio", label: "LM Studio", defaultUrl: "http://localhost:1234/v1" },
	{ id: "ollama", label: "Ollama", defaultUrl: "http://localhost:11434" },
	{ id: "openai", label: "OpenAI", defaultUrl: "https://api.openai.com/v1" },
	{ id: "anthropic", label: "Anthropic", defaultUrl: "https://api.anthropic.com/v1" },
	{ id: "deepseek", label: "DeepSeek", defaultUrl: "https://api.deepseek.com/v1" },
];

export default function ChatPage() {
	const [messages, setMessages] = useState<Message[]>([]);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const [provider, setProvider] = useState(() => localStorage.getItem("chat_provider") || "lmstudio");
	const [model, setModel] = useState(() => localStorage.getItem("chat_model") || "");
	const [models, setModels] = useState<string[]>([]);
	const [baseUrl, setBaseUrl] = useState(() => localStorage.getItem("chat_base_url") || "");
	const [error, setError] = useState<string | null>(null);
	const bottomRef = useRef<HTMLDivElement>(null);

	const providerCfg = PROVIDERS.find((p) => p.id === provider);

	const fetchModels = useCallback(async (p: string, url: string) => {
		try {
			const params = new URLSearchParams({ provider: p });
			if (url) params.set("base_url", url);
			const r = await fetch(`/api/llm/models?${params}`);
			if (r.ok) {
				const d = await r.json();
				setModels(d.models || []);
				if (d.models?.length && !d.models.includes(model)) {
					setModel(d.models[0]);
				}
			}
		} catch { /* ignore */ }
	}, [model]);

	useEffect(() => {
		const url = baseUrl || providerCfg?.defaultUrl || "";
		fetchModels(provider, url);
	}, [provider, baseUrl, fetchModels, providerCfg]);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages]);

	const sendMessage = async () => {
		if (!input.trim() || loading) return;
		const userMsg: Message = { role: "user", content: input.trim() };
		setMessages((m) => [...m, userMsg]);
		setInput("");
		setLoading(true);
		setError(null);
		try {
			const body: Record<string, string> = {
				provider,
				model: model || providerCfg?.defaultUrl || "",
				message: input.trim(),
			};
			if (baseUrl) body.base_url = baseUrl;
			const r = await apiFetch("/api/chat", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(body),
			});
			const data = await r.json();
			if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
			setMessages((m) => [...m, { role: "assistant", content: data.reply || data.message || JSON.stringify(data) }]);
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			setError(msg);
			setMessages((m) => [...m, { role: "assistant", content: `Error: ${msg}` }]);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex flex-col h-[calc(100vh-6rem)] max-w-4xl mx-auto">
			<div className="flex items-center justify-between mb-4 px-2">
				<h1 className="text-xl font-bold">AI Chat</h1>
				<div className="flex items-center gap-2 flex-wrap">
					<select
						value={provider}
						onChange={(e) => { setProvider(e.target.value); localStorage.setItem("chat_provider", e.target.value); }}
						className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white"
					>
						{PROVIDERS.map((p) => (
							<option key={p.id} value={p.id}>{p.label}</option>
						))}
					</select>
					{provider !== "anthropic" && provider !== "openai" && (
						<input
							type="text"
							value={baseUrl}
							onChange={(e) => { setBaseUrl(e.target.value); localStorage.setItem("chat_base_url", e.target.value); }}
							placeholder={providerCfg?.defaultUrl || "http://localhost:1234/v1"}
							className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white w-48"
						/>
					)}
					{models.length > 0 ? (
						<select
							value={model}
							onChange={(e) => { setModel(e.target.value); localStorage.setItem("chat_model", e.target.value); }}
							className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white"
						>
							{models.map((m) => (
								<option key={m} value={m}>{m}</option>
							))}
						</select>
					) : (
						<input
							type="text"
							value={model}
							onChange={(e) => { setModel(e.target.value); localStorage.setItem("chat_model", e.target.value); }}
							placeholder="model name"
							className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white w-36"
						/>
					)}
					<button
						onClick={() => fetchModels(provider, baseUrl || providerCfg?.defaultUrl || "")}
						className="p-1.5 rounded-lg hover:bg-white/5 text-zinc-400"
						title="Refresh models"
					>
						<RefreshCw className="w-3.5 h-3.5" />
					</button>
				</div>
			</div>

			<div className="flex-1 overflow-y-auto space-y-3 px-2 pb-4">
				{messages.length === 0 && (
					<div className="text-center text-zinc-500 text-sm mt-12">
						<Bot className="w-10 h-10 mx-auto mb-3 opacity-30" />
						<p>Send a message to start chatting with {providerCfg?.label || "the AI"}.</p>
						<p className="text-xs mt-1">Model: {model || "not selected"}</p>
					</div>
				)}
				{messages.map((m, i) => (
					<div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
						{m.role === "assistant" && (
							<div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center shrink-0 mt-1">
								<Bot className="w-4 h-4 text-indigo-400" />
							</div>
						)}
						<div className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
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
				{error && <p className="text-xs text-red-400 text-center">{error}</p>}
				<div ref={bottomRef} />
			</div>

			<div className="flex gap-2 p-2 border-t border-white/5">
				<input
					type="text"
					value={input}
					onChange={(e) => setInput(e.target.value)}
					onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
					placeholder={`Ask ${providerCfg?.label || "AI"}...`}
					className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-indigo-500/50 transition-colors"
					disabled={loading}
				/>
				<button
					onClick={sendMessage}
					disabled={loading || !input.trim()}
					className="p-2.5 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/30 disabled:opacity-30 transition-colors"
				>
					<Send className="w-4 h-4" />
				</button>
			</div>
		</div>
	);
}
