import { Activity, Loader2 } from "lucide-react";
import { PipelineHealthCard } from "../components/PipelineHealthCard";
import { useConnection } from "../store/connection";

export default function StatusPage() {
	const { state } = useConnection();

	const statusBadge = () => {
		switch (state) {
			case "connected":
				return (
					<div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold uppercase tracking-widest">
						<Activity className="w-3 h-3" />
						Live
					</div>
				);
			case "connecting":
				return (
					<div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-500 text-xs font-bold uppercase tracking-widest">
						<Loader2 className="w-3 h-3 animate-spin" />
						Connecting
					</div>
				);
			case "offline":
			case "error":
				return (
					<div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-500 text-xs font-bold uppercase tracking-widest">
						<Activity className="w-3 h-3" />
						Offline
					</div>
				);
		}
	};

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">Pipeline Status</h1>
					<p className="text-muted-foreground text-sm mt-1">
						Fleet integration health checks and pipeline liveness monitoring.
					</p>
				</div>
				{statusBadge()}
			</div>
			<PipelineHealthCard />
		</div>
	);
}
