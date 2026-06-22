import { apiFetch } from "../utils/api";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { AnimatePresence, motion } from "framer-motion";
import {
	AlertTriangle,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	RefreshCw,
	ShieldAlert,
} from "lucide-react";
import { useState } from "react";

export type PipelineAlert = {
	severity: "critical" | "warning" | string;
	code: string;
	message: string;
	source?: string;
	detail?: Record<string, unknown>;
};

export type PipelineLiveness = {
	success: boolean;
	healthy: boolean;
	critical_count: number;
	warning_count: number;
	checked_at?: string;
	stale_hours: number;
	alerts: PipelineAlert[];
	checks?: Array<Record<string, unknown>>;
};

async function fetchPipelineLiveness(): Promise<PipelineLiveness> {
	const r = await apiFetch("/api/pipeline/liveness?stale_hours=48");
	if (!r.ok) {
		throw new Error(`Pipeline liveness HTTP ${r.status}`);
	}
	return r.json();
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, warning: 1 };

function sortAlerts(alerts: PipelineAlert[]): PipelineAlert[] {
	return [...alerts].sort(
		(a, b) =>
			(SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9),
	);
}

export function PipelineHealthCard() {
	const [expanded, setExpanded] = useState(true);
	const { data, isLoading, isError, error, dataUpdatedAt, isFetching } =
		useQuery({
			queryKey: ["pipeline-liveness"],
			queryFn: fetchPipelineLiveness,
			refetchInterval: 15_000,
			refetchIntervalInBackground: true,
			staleTime: 10_000,
		});

	const healthy = data?.healthy ?? true;
	const alerts = sortAlerts(data?.alerts ?? []);
	const hasIssues = alerts.length > 0;
	const checkedLabel = data?.checked_at
		? formatDistanceToNow(new Date(data.checked_at), { addSuffix: true })
		: dataUpdatedAt
			? formatDistanceToNow(dataUpdatedAt, { addSuffix: true })
			: "—";

	if (isLoading && !data) {
		return (
			<div
				className="rounded-xl border px-4 py-3 flex items-center gap-2 text-sm"
				style={{
					borderColor: "var(--border)",
					background: "var(--bg-surface)",
					color: "var(--text-muted)",
				}}
			>
				<RefreshCw className="w-4 h-4 animate-spin" />
				Checking open-weight pipeline…
			</div>
		);
	}

	if (isError) {
		return (
			<div
				className="rounded-xl border px-4 py-3"
				style={{
					background: "rgba(239,68,68,0.08)",
					borderColor: "rgba(239,68,68,0.35)",
				}}
			>
				<div className="flex items-center gap-2 text-sm font-medium text-red-400">
					<ShieldAlert className="w-4 h-4 shrink-0" />
					Pipeline monitor offline — cannot reach /api/pipeline/liveness
				</div>
				<p className="text-xs mt-1 text-red-300/80">
					{(error as Error)?.message ?? "Unknown error"}
				</p>
			</div>
		);
	}

	if (healthy && !hasIssues) {
		return (
			<div
				className="rounded-xl border px-4 py-2.5 flex items-center justify-between gap-3"
				style={{
					background: "rgba(34,197,94,0.06)",
					borderColor: "rgba(34,197,94,0.25)",
				}}
			>
				<div className="flex items-center gap-2 text-sm text-emerald-400">
					<CheckCircle2 className="w-4 h-4 shrink-0" />
					<span>
						Open-weight pipeline OK — arXiv pull + code-hunt loop healthy
					</span>
				</div>
				<span className="text-xs text-emerald-500/70 flex items-center gap-1">
					{isFetching && <RefreshCw className="w-3 h-3 animate-spin" />}
					checked {checkedLabel}
				</span>
			</div>
		);
	}

	const critical = alerts.filter((a) => a.severity === "critical");
	const warnings = alerts.filter((a) => a.severity === "warning");

	return (
		<motion.div
			initial={{ opacity: 0, y: -4 }}
			animate={{ opacity: 1, y: 0 }}
			className="rounded-xl border overflow-hidden"
			style={{
				background: critical.length
					? "rgba(239,68,68,0.06)"
					: "rgba(245,158,11,0.06)",
				borderColor: critical.length
					? "rgba(239,68,68,0.4)"
					: "rgba(245,158,11,0.35)",
			}}
		>
			<button
				type="button"
				onClick={() => setExpanded((v) => !v)}
				className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left"
			>
				<div className="flex items-center gap-2 min-w-0">
					<AlertTriangle
						className="w-5 h-5 shrink-0"
						style={{ color: critical.length ? "#ef4444" : "#f59e0b" }}
					/>
					<div className="min-w-0">
						<div
							className="text-sm font-semibold"
							style={{ color: critical.length ? "#fca5a5" : "#fcd34d" }}
						>
							Pipeline degraded
							{critical.length > 0 && (
								<span className="font-mono ml-2">
									{data?.critical_count ?? critical.length} critical
								</span>
							)}
							{warnings.length > 0 && (
								<span className="font-mono ml-2 opacity-80">
									{data?.warning_count ?? warnings.length} warn
								</span>
							)}
						</div>
						<p className="text-xs mt-0.5 truncate" style={{ color: "var(--text-muted)" }}>
							{critical[0]?.message ?? warnings[0]?.message ?? "Check ingestion loop"}
						</p>
					</div>
				</div>
				<div className="flex items-center gap-2 shrink-0">
					<span className="text-xs" style={{ color: "var(--text-muted)" }}>
						{isFetching && <RefreshCw className="w-3 h-3 animate-spin inline mr-1" />}
						{checkedLabel}
					</span>
					{expanded ? (
						<ChevronUp className="w-4 h-4" style={{ color: "var(--text-muted)" }} />
					) : (
						<ChevronDown className="w-4 h-4" style={{ color: "var(--text-muted)" }} />
					)}
				</div>
			</button>

			<AnimatePresence>
				{expanded && (
					<motion.div
						initial={{ height: 0, opacity: 0 }}
						animate={{ height: "auto", opacity: 1 }}
						exit={{ height: 0, opacity: 0 }}
						className="border-t"
						style={{ borderColor: "var(--border)" }}
					>
						<ul className="divide-y" style={{ borderColor: "var(--border)" }}>
							{alerts.map((alert) => (
								<li key={`${alert.source}-${alert.code}-${alert.message}`} className="px-4 py-3">
									<div className="flex items-start gap-2">
										<span
											className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0 mt-0.5"
											style={
												alert.severity === "critical"
													? {
															background: "rgba(239,68,68,0.2)",
															color: "#f87171",
														}
													: {
															background: "rgba(245,158,11,0.2)",
															color: "#fbbf24",
														}
											}
										>
											{alert.severity}
										</span>
										<div className="min-w-0 flex-1">
											<div className="text-xs font-mono text-zinc-500">
												{alert.source ?? "?"} · {alert.code}
											</div>
											<p
												className="text-sm mt-0.5"
												style={{ color: "var(--text-primary)" }}
											>
												{alert.message}
											</p>
											{alert.detail?.last_error != null && (
												<p className="text-xs mt-1 font-mono text-red-300/80 break-all">
													{String(alert.detail.last_error)}
												</p>
											)}
										</div>
									</div>
								</li>
							))}
						</ul>
						<div
							className="px-4 py-2 text-xs"
							style={{
								color: "var(--text-muted)",
								background: "rgba(0,0,0,0.15)",
							}}
						>
							Auto-refresh every 15s · threshold {data?.stale_hours ?? 48}h stale ·
							try <strong>Poll Feeds</strong> if arXiv rows are empty
						</div>
					</motion.div>
				)}
			</AnimatePresence>
		</motion.div>
	);
}

/** Compact badge for the global status bar. */
export function PipelineHealthBadge() {
	const { data, isError } = useQuery({
		queryKey: ["pipeline-liveness"],
		queryFn: fetchPipelineLiveness,
		refetchInterval: 15_000,
		refetchIntervalInBackground: true,
	});

	if (isError || !data) {
		return null;
	}
	if (data.healthy) {
		return null;
	}

	return (
		<div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-500/15 border border-rose-500/30 text-[10px] font-bold text-rose-400 uppercase tracking-wider animate-pulse">
			<AlertTriangle className="w-3 h-3" />
			Pipeline {data.critical_count > 0 ? "down" : "warn"}
		</div>
	);
}
