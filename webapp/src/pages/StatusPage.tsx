import { Activity } from "lucide-react";
import { PipelineHealthCard } from "../components/PipelineHealthCard";

export default function StatusPage() {
	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">Pipeline Status</h1>
					<p className="text-muted-foreground text-sm mt-1">
						Fleet integration health checks and pipeline liveness monitoring.
					</p>
				</div>
				<div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold uppercase tracking-widest">
					<Activity className="w-3 h-3" />
					Live
				</div>
			</div>
			<PipelineHealthCard />
		</div>
	);
}
