import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Check, ExternalLink, Info, Loader2, Plus, Rss, X } from "lucide-react";
import { useState } from "react";
import { UrgencyBadge } from "../components/UrgencyBadge";

export function BundlesPage() {
	const [selectedBundleId, setSelectedBundleId] = useState<number | null>(null);
	const [isWizardOpen, setIsWizardOpen] = useState(false);
	const queryClient = useQueryClient();

	const { data: bundlesData, isLoading: isLoadingBundles } = useQuery({
		queryKey: ["bundles"],
		queryFn: () => fetch("/api/bundles").then((r) => r.json()),
	});

	const bundles = bundlesData?.bundles ?? [];

	return (
		<div className="space-y-6 max-w-6xl">
			<div className="flex items-center justify-between">
				<div>
					<h1
						className="text-xl font-semibold"
						style={{ color: "var(--text-primary)" }}
					>
						Interest Bundles
					</h1>
					<p className="text-sm" style={{ color: "var(--text-muted)" }}>
						Niche-specific AI personas filtering your global feeds.
					</p>
				</div>
				<button
					onClick={() => setIsWizardOpen(true)}
					className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
					style={{ background: "var(--accent-amber)", color: "#000" }}
				>
					<Plus className="w-4 h-4" />
					New Bundle
				</button>
			</div>

			<div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
				{/* Sidebar: Bundle List */}
				<div className="lg:col-span-1 space-y-2">
					{isLoadingBundles
						? Array.from({ length: 3 }).map((_, i) => (
								<div
									key={i}
									className="h-14 rounded-xl animate-pulse"
									style={{ background: "var(--bg-surface)" }}
								/>
							))
						: bundles.map((b: any) => (
								<button
									key={b.id}
									onClick={() => setSelectedBundleId(b.id)}
									className={`w-full text-left p-4 rounded-xl border transition-all ${
										selectedBundleId === b.id
											? "border-amber-500/50"
											: "hover:border-zinc-700"
									}`}
									style={{
										background:
											selectedBundleId === b.id
												? "rgba(245,158,11,0.08)"
												: "var(--bg-surface)",
										borderColor:
											selectedBundleId === b.id
												? "var(--accent-amber)"
												: "var(--border)",
									}}
								>
									<div
										className="font-medium text-sm"
										style={{
											color:
												selectedBundleId === b.id
													? "var(--accent-amber)"
													: "var(--text-primary)",
										}}
									>
										{b.name}
									</div>
									<div
										className="text-xs mt-1"
										style={{ color: "var(--text-muted)" }}
									>
										{b.topic}
									</div>
								</button>
							))}
				</div>

				{/* Main: Items for Selected Bundle */}
				<div className="lg:col-span-3">
					{selectedBundleId ? (
						<BundleView bundleId={selectedBundleId} />
					) : (
						<div
							className="flex flex-col items-center justify-center py-20 rounded-2xl border border-dashed"
							style={{
								borderColor: "var(--border)",
								background: "var(--bg-surface)",
							}}
						>
							<div
								className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
								style={{ background: "rgba(255,255,255,0.03)" }}
							>
								<Info
									className="w-6 h-6"
									style={{ color: "var(--text-muted)" }}
								/>
							</div>
							<p className="text-sm" style={{ color: "var(--text-muted)" }}>
								Select a bundle to view distilled insights
							</p>
						</div>
					)}
				</div>
			</div>

			{isWizardOpen && (
				<BundleWizard
					onClose={() => setIsWizardOpen(false)}
					onCreated={() =>
						queryClient.invalidateQueries({ queryKey: ["bundles"] })
					}
				/>
			)}
		</div>
	);
}

function BundleView({ bundleId }: { bundleId: number }) {
	const [hours, setHours] = useState(24);

	const { data, isLoading } = useQuery({
		queryKey: ["bundle-items", bundleId, hours],
		queryFn: () =>
			fetch(`/api/bundles/${bundleId}/items?hours=${hours}&limit=50`).then(
				(r) => r.json(),
			),
		refetchInterval: 60_000,
	});

	const items = data?.items ?? [];

	return (
		<div className="space-y-4">
			<div className="flex items-center justify-between px-2">
				<h2
					className="text-sm font-semibold uppercase tracking-wider"
					style={{ color: "var(--text-muted)" }}
				>
					Recent Highlights
				</h2>
				<select
					value={hours}
					onChange={(e) => setHours(Number(e.target.value))}
					className="text-xs rounded-md px-2 py-1 border outline-none"
					style={{
						background: "var(--bg-surface)",
						color: "var(--text-secondary)",
						borderColor: "var(--border)",
					}}
				>
					<option value={6}>6h</option>
					<option value={24}>24h</option>
					<option value={72}>3d</option>
				</select>
			</div>

			{isLoading ? (
				<div className="space-y-3">
					{Array.from({ length: 5 }).map((_, i) => (
						<div
							key={i}
							className="h-24 rounded-xl animate-pulse"
							style={{ background: "var(--bg-surface)" }}
						/>
					))}
				</div>
			) : items.length === 0 ? (
				<div
					className="text-center py-12 text-sm"
					style={{ color: "var(--text-muted)" }}
				>
					No distilled items for this bundle yet. Ensure feeds are linked.
				</div>
			) : (
				<div className="space-y-3">
					{items.map((item: any) => (
						<div
							key={item.id}
							className="rounded-xl border p-4 transition-colors"
							style={{
								background: "var(--bg-surface)",
								borderColor: "var(--border)",
							}}
						>
							<div className="flex items-start gap-4">
								<UrgencyBadge score={item.urgency_score} />
								<div className="flex-1 min-w-0">
									<div className="flex items-start justify-between gap-2">
										<a
											href={item.url}
											target="_blank"
											rel="noopener noreferrer"
											className="text-sm font-medium hover:underline flex-1"
											style={{ color: "var(--text-primary)" }}
										>
											{item.title}
										</a>
										<ExternalLink
											className="w-3.5 h-3.5 mt-0.5 flex-shrink-0"
											style={{ color: "var(--text-muted)" }}
										/>
									</div>
									<p
										className="text-xs mt-2 italic leading-relaxed"
										style={{ color: "var(--text-secondary)" }}
									>
										"{item.distilled_summary}"
									</p>
									<div className="flex items-center gap-3 mt-3">
										<span
											className="text-[10px] font-bold uppercase"
											style={{ color: "var(--accent-amber)" }}
										>
											{item.feed_name}
										</span>
										<span
											className="text-[10px]"
											style={{ color: "var(--text-muted)" }}
										>
											{formatDistanceToNow(new Date(item.fetched_at), {
												addSuffix: true,
											})}
										</span>
										{item.bundle_tags &&
											JSON.parse(item.bundle_tags).map((t: string) => (
												<span
													key={t}
													className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700"
													style={{ color: "var(--text-muted)" }}
												>
													{t}
												</span>
											))}
									</div>
								</div>
							</div>
						</div>
					))}
				</div>
			)}

			<div
				className="mt-8 border-t pt-6"
				style={{ borderColor: "var(--border)" }}
			>
				<BundleFeedManager bundleId={bundleId} />
			</div>
		</div>
	);
}

function BundleFeedManager({ bundleId }: { bundleId: number }) {
	const queryClient = useQueryClient();
	const { data: feedsData } = useQuery({
		queryKey: ["feeds"],
		queryFn: () => fetch("/api/feeds").then((r) => r.json()),
	});

	const { data: linkedFeedsData } = useQuery({
		queryKey: ["bundle-feeds", bundleId],
		queryFn: () =>
			fetch(`/api/bundles/${bundleId}/feeds`).then((r) => r.json()),
	});

	const feeds = feedsData?.feeds ?? [];
	const linkedFeedIds = new Set(
		(linkedFeedsData?.feeds ?? []).map((f: any) => f.id),
	);

	const linkMutation = useMutation({
		mutationFn: (feedId: number) =>
			fetch(`/api/bundles/${bundleId}/feeds`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ feed_id: feedId }),
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["bundle-items", bundleId] });
			queryClient.invalidateQueries({ queryKey: ["bundle-feeds", bundleId] });
		},
	});

	return (
		<div className="space-y-3">
			<div className="flex items-center justify-between">
				<h3
					className="text-xs font-semibold uppercase tracking-wider"
					style={{ color: "var(--text-muted)" }}
				>
					Source Management
				</h3>
				<span className="text-[10px] text-zinc-500">
					{linkedFeedIds.size} linked
				</span>
			</div>
			<div className="flex flex-wrap gap-2">
				{feeds.map((f: any) => {
					const isLinked = linkedFeedIds.has(f.id);
					return (
						<button
							key={f.id}
							onClick={() => !isLinked && linkMutation.mutate(f.id)}
							className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-all ${
								isLinked ? "opacity-100 cursor-default" : "hover:bg-zinc-800"
							}`}
							style={{
								background: isLinked
									? "rgba(245,158,11,0.1)"
									: "var(--bg-surface)",
								borderColor: isLinked ? "var(--accent-amber)" : "var(--border)",
								color: isLinked
									? "var(--accent-amber)"
									: "var(--text-secondary)",
							}}
						>
							<Rss className="w-3 h-3" />
							{f.name}
							{isLinked && <Check className="w-3 h-3 ml-1" />}
						</button>
					);
				})}
			</div>
			<p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
				Only sources linked to this bundle (highlighted in amber) will be
				processed by the "{bundleId}" persona.
			</p>
		</div>
	);
}

function BundleWizard({
	onClose,
	onCreated,
}: { onClose: () => void; onCreated: () => void }) {
	const [topic, setTopic] = useState("");
	const [step, setStep] = useState<"input" | "loading" | "success">("input");
	const [result, setResult] = useState<any>(null);

	const createMutation = useMutation({
		mutationFn: async (t: string) => {
			setStep("loading");
			const r = await fetch("/api/bundles/create", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ topic: t }),
			});
			if (!r.ok) throw new Error("Failed to create");
			return r.json();
		},
		onSuccess: (data) => {
			setResult(data);
			setStep("success");
			onCreated();
		},
	});

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
			<div
				className="w-full max-w-md rounded-2xl border shadow-2xl p-6"
				style={{
					background: "var(--bg-secondary)",
					borderColor: "var(--border)",
				}}
			>
				{step === "input" && (
					<div className="space-y-4">
						<div className="flex items-center justify-between">
							<h2
								className="text-lg font-semibold"
								style={{ color: "var(--text-primary)" }}
							>
								New Interest Bundle
							</h2>
							<button onClick={onClose} style={{ color: "var(--text-muted)" }}>
								<X className="w-5 h-5" />
							</button>
						</div>
						<p className="text-sm" style={{ color: "var(--text-secondary)" }}>
							What niche interests you? (e.g. "Yachts and Boats", "Dogs",
							"Modern Art")
						</p>
						<input
							value={topic}
							onChange={(e) => setTopic(e.target.value)}
							placeholder="e.g. Mechanical Watches"
							className="w-full px-4 py-3 rounded-xl border outline-none text-sm transition-all focus:border-amber-500/50"
							style={{
								background: "var(--bg-surface)",
								borderColor: "var(--border)",
								color: "var(--text-primary)",
							}}
							onKeyDown={(e) =>
								e.key === "Enter" && createMutation.mutate(topic)
							}
						/>
						<button
							disabled={!topic || createMutation.isPending}
							onClick={() => createMutation.mutate(topic)}
							className="w-full py-3 rounded-xl font-semibold text-sm transition-all active:scale-[0.98] disabled:opacity-50"
							style={{ background: "var(--accent-amber)", color: "#000" }}
						>
							Generate Bundle Persona
						</button>
					</div>
				)}

				{step === "loading" && (
					<div className="py-10 flex flex-col items-center justify-center text-center space-y-4">
						<Loader2
							className="w-8 h-8 animate-spin"
							style={{ color: "var(--accent-amber)" }}
						/>
						<div>
							<div
								className="font-medium text-sm"
								style={{ color: "var(--text-primary)" }}
							>
								Eliciting Persona...
							</div>
							<p
								className="text-xs mt-1"
								style={{ color: "var(--text-muted)" }}
							>
								Claude is defining a custom filter for "{topic}"
							</p>
						</div>
					</div>
				)}

				{step === "success" && (
					<div className="space-y-5">
						<div
							className="w-12 h-12 rounded-full flex items-center justify-center mx-auto"
							style={{ background: "rgba(34,197,94,0.1)" }}
						>
							<Check className="w-6 h-6 text-green-500" />
						</div>
						<div className="text-center">
							<h2
								className="text-lg font-semibold"
								style={{ color: "var(--text-primary)" }}
							>
								Bundle Created!
							</h2>
							<p
								className="text-sm mt-1"
								style={{ color: "var(--text-secondary)" }}
							>
								"{result?.name}" is now ready.
							</p>
						</div>

						{result?.suggested_feeds?.length > 0 && (
							<div className="space-y-2">
								<div className="text-[10px] font-bold uppercase text-zinc-500 px-1">
									Suggested Sources
								</div>
								<div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
									{result.suggested_feeds.map((s: any, i: number) => (
										<SuggestedSource
											key={i}
											source={s}
											bundleId={result.id}
											onAdded={() => {}}
										/>
									))}
								</div>
							</div>
						)}

						<button
							onClick={onClose}
							className="w-full py-3 rounded-xl font-semibold text-sm"
							style={{
								background: "var(--bg-surface)",
								border: "1px solid var(--border)",
								color: "var(--text-primary)",
							}}
						>
							Finish
						</button>
					</div>
				)}
			</div>
		</div>
	);
}

function SuggestedSource({
	source,
	bundleId,
	onAdded,
}: { source: any; bundleId: number; onAdded: () => void }) {
	const [status, setStatus] = useState<"idle" | "adding" | "added">("idle");

	const handleAdd = async () => {
		setStatus("adding");
		try {
			// 1. Add feed
			const r1 = await fetch("/api/feeds/add", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					name: source.name,
					url: source.url,
					feed_type: source.type || "rss",
				}),
			});
			const data1 = await r1.json();

			// 2. Link to bundle
			await fetch(`/api/bundles/${bundleId}/feeds`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ feed_id: data1.id }),
			});

			setStatus("added");
			onAdded();
		} catch (e) {
			console.error(e);
			setStatus("idle");
		}
	};

	return (
		<div className="flex items-center justify-between p-2 rounded-lg bg-zinc-900 border border-zinc-800">
			<div className="min-w-0">
				<div className="text-xs font-medium truncate text-zinc-200">
					{source.name}
				</div>
				<div className="text-[10px] truncate text-zinc-500">{source.url}</div>
			</div>
			<button
				disabled={status !== "idle"}
				onClick={handleAdd}
				className="ml-3 p-1.5 rounded-md transition-all active:scale-95 disabled:opacity-50"
				style={{
					background:
						status === "added" ? "rgba(34,197,94,0.1)" : "var(--bg-surface)",
					border: "1px solid var(--border)",
				}}
			>
				{status === "added" ? (
					<Check className="w-3.5 h-3.5 text-green-500" />
				) : (
					<Plus className="w-3.5 h-3.5 text-zinc-400" />
				)}
			</button>
		</div>
	);
}
