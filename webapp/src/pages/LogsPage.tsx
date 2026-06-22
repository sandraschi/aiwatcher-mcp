import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
	AlertCircle,
	AlertTriangle,
	Bug,
	Filter,
	Info,
	ScrollText,
	Terminal,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../utils/api";

async function fetchLogs() {
	const r = await apiFetch("/api/logs");
	return r.json();
}

export function LogsPage() {
	const { data, refetch, isFetching } = useQuery({
		queryKey: ["logs"],
		queryFn: fetchLogs,
		refetchInterval: 3000, // Auto-refresh every 3s
	});

	const [filter, setFilter] = useState("");
	const [levelFilter, setLevelFilter] = useState<string | null>(null);
	const scrollRef = useRef<HTMLDivElement>(null);

	const logs = (data?.logs || []).filter((log: any) => {
		const matchesText =
			log.message.toLowerCase().includes(filter.toLowerCase()) ||
			log.name.toLowerCase().includes(filter.toLowerCase());
		const matchesLevel = levelFilter ? log.level === levelFilter : true;
		return matchesText && matchesLevel;
	});

	// Auto-scroll to bottom on new logs
	useEffect(() => {
		if (scrollRef.current) {
			scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
		}
	}, [logs.length]);

	const getLevelIcon = (level: string) => {
		switch (level) {
			case "ERROR":
				return <AlertCircle className="w-3.5 h-3.5 text-rose-500" />;
			case "WARNING":
				return <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />;
			case "DEBUG":
				return <Bug className="w-3.5 h-3.5 text-blue-500" />;
			default:
				return <Info className="w-3.5 h-3.5 text-zinc-400" />;
		}
	};

	return (
		<div className="flex flex-col h-[calc(100vh-120px)] space-y-4">
			<div className="flex items-center justify-between">
				<div className="flex items-center gap-3">
					<Terminal className="w-5 h-5 text-indigo-400" />
					<h1 className="text-xl font-bold text-white">System Logs</h1>
					{isFetching && (
						<div className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse ml-2" />
					)}
				</div>

				<div className="flex items-center gap-3">
					<div className="relative">
						<Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
						<input
							type="text"
							placeholder="Filter logs..."
							value={filter}
							onChange={(e) => setFilter(e.target.value)}
							className="bg-black/20 border border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500 w-64"
						/>
					</div>

					<div className="flex bg-black/20 border border-white/10 rounded-lg p-0.5">
						{["ERROR", "WARNING", "INFO", "DEBUG"].map((lvl) => (
							<button
								key={lvl}
								onClick={() => setLevelFilter(levelFilter === lvl ? null : lvl)}
								className={clsx(
									"px-2.5 py-1 rounded text-[10px] font-bold transition-all",
									levelFilter === lvl
										? "bg-white/10 text-white shadow-sm"
										: "text-zinc-500 hover:text-zinc-300",
								)}
							>
								{lvl}
							</button>
						))}
					</div>

					<button
						onClick={() => refetch()}
						className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-400 transition-colors"
					>
						<ScrollText className="w-4 h-4" />
					</button>
				</div>
			</div>

			<div
				ref={scrollRef}
				className="flex-1 bg-black/40 border border-white/10 rounded-2xl overflow-y-auto font-mono text-xs p-4 custom-scrollbar"
			>
				{logs.length === 0 ? (
					<div className="h-full flex items-center justify-center text-zinc-600 italic">
						No logs found matching filters.
					</div>
				) : (
					<div className="space-y-1">
						{logs.map((log: any, i: number) => (
							<div
								key={i}
								className="group flex gap-4 py-1 hover:bg-white/5 px-2 rounded -mx-2"
							>
								<span className="text-zinc-600 shrink-0 select-none">
									{new Date(log.timestamp).toLocaleTimeString([], {
										hour12: false,
									})}
								</span>
								<span
									className={clsx(
										"shrink-0 w-16 font-bold flex items-center gap-1.5",
										log.level === "ERROR"
											? "text-rose-500"
											: log.level === "WARNING"
												? "text-amber-500"
												: log.level === "DEBUG"
													? "text-blue-500"
													: "text-zinc-400",
									)}
								>
									{getLevelIcon(log.level)}
									{log.level}
								</span>
								<span className="text-indigo-400 shrink-0 opacity-60">
									[{log.name}]
								</span>
								<span className="text-zinc-300 break-all">{log.message}</span>
							</div>
						))}
					</div>
				)}
			</div>

			<div className="flex items-center justify-between text-[10px] text-zinc-500 px-2 uppercase tracking-widest">
				<span>Showing {logs.length} entries</span>
				<span>Auto-refreshing every 3s</span>
			</div>
		</div>
	);
}
