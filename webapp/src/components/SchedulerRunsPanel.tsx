import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Bell, Clock, Loader2, type Play, RefreshCw, Zap } from "lucide-react";
import { apiFetch } from "../utils/api";

type SchedulerStatus = {
  running: boolean;
  feed_poll_interval_minutes: number;
  distillation_interval_hours: number;
  alert_hour_utc: number;
  alert_minute_utc: number;
  jobs: Array<{ id: string; next_run: string | null; trigger: string }>;
};

async function fetchScheduler(): Promise<SchedulerStatus> {
  const r = await apiFetch("/api/scheduler");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function postRun(path: string) {
  const r = await apiFetch(path, { method: "POST" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${r.status}`);
  }
  return r.json();
}

export function SchedulerRunsPanel() {
  const qc = useQueryClient();
  const { data, isLoading, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ["scheduler"],
    queryFn: fetchScheduler,
    refetchInterval: 30_000,
  });

  const pollMutation = useMutation({
    mutationFn: () => postRun("/api/poll"),
    onSuccess: () => qc.invalidateQueries(),
  });
  const distillMutation = useMutation({
    mutationFn: () => postRun("/api/distill"),
    onSuccess: () => qc.invalidateQueries(),
  });
  const alertsMutation = useMutation({
    mutationFn: () => postRun("/api/alerts/check"),
    onSuccess: () => qc.invalidateQueries(),
  });

  const anyPending =
    pollMutation.isPending ||
    distillMutation.isPending ||
    alertsMutation.isPending;

  return (
    <div
      className="rounded-xl border p-5 space-y-4"
      style={{ background: "var(--bg-surface)", borderColor: "var(--border)" }}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2
            className="text-sm font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Scheduled runs
          </h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            APScheduler jobs and manual pipeline triggers
          </p>
        </div>
        <span
          className={`text-[10px] font-bold uppercase px-2 py-1 rounded-full border ${
            data?.running
              ? "text-green-500 border-green-500/30 bg-green-500/10"
              : "text-amber-500 border-amber-500/30 bg-amber-500/10"
          }`}
        >
          {data?.running ? "Scheduler on" : "Scheduler off"}
        </span>
      </div>

      {isLoading ? (
        <div className="h-20 animate-pulse rounded-lg bg-zinc-800/40" />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
            <IntervalChip
              label="Poll feeds"
              value={`every ${data?.feed_poll_interval_minutes ?? "—"}m`}
            />
            <IntervalChip
              label="Distill"
              value={`every ${data?.distillation_interval_hours ?? "—"}h`}
            />
            <IntervalChip
              label="Alerts (UTC)"
              value={
                data
                  ? `${String(data.alert_hour_utc).padStart(2, "0")}:${String(data.alert_minute_utc).padStart(2, "0")}`
                  : "—"
              }
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <RunButton
              label="Poll now"
              icon={RefreshCw}
              pending={pollMutation.isPending}
              disabled={anyPending}
              onClick={() => pollMutation.mutate()}
            />
            <RunButton
              label="Distill now"
              icon={Zap}
              pending={distillMutation.isPending}
              disabled={anyPending}
              onClick={() => distillMutation.mutate()}
            />
            <RunButton
              label="Check alerts"
              icon={Bell}
              pending={alertsMutation.isPending}
              disabled={anyPending}
              onClick={() => alertsMutation.mutate()}
            />
          </div>

          {(pollMutation.isSuccess ||
            distillMutation.isSuccess ||
            alertsMutation.isSuccess) && (
            <p className="text-xs text-green-500">Last manual run completed.</p>
          )}

          <div className="space-y-1 max-h-48 overflow-y-auto">
            <div
              className="text-[10px] font-bold uppercase flex items-center gap-1 mb-1"
              style={{ color: "var(--text-muted)" }}
            >
              <Clock className="w-3 h-3" />
              Next scheduled jobs
              {dataUpdatedAt ? (
                <span className="font-normal normal-case ml-1">
                  (refreshed{" "}
                  {formatDistanceToNow(dataUpdatedAt, { addSuffix: true })})
                </span>
              ) : null}
            </div>
            {(data?.jobs ?? []).length === 0 ? (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {data?.running
                  ? "No jobs registered."
                  : "Start the backend API to enable the scheduler (not running in this session)."}
              </p>
            ) : (
              data?.jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex justify-between gap-2 text-[11px] py-1.5 px-2 rounded"
                  style={{ background: "rgba(255,255,255,0.02)" }}
                >
                  <span
                    className="font-medium"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {job.id}
                  </span>
                  <span style={{ color: "var(--text-muted)" }}>
                    {job.next_run
                      ? formatDistanceToNow(new Date(job.next_run), {
                          addSuffix: true,
                        })
                      : "—"}
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {isFetching && !isLoading && (
        <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
          Refreshing…
        </p>
      )}
    </div>
  );
}

function IntervalChip({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="rounded-lg px-3 py-2 border"
      style={{
        borderColor: "var(--border)",
        background: "rgba(255,255,255,0.02)",
      }}
    >
      <div
        className="text-[10px] uppercase"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </div>
      <div className="font-medium" style={{ color: "var(--text-primary)" }}>
        {value}
      </div>
    </div>
  );
}

function RunButton({
  label,
  icon: Icon,
  pending,
  disabled,
  onClick,
}: {
  label: string;
  icon: typeof Play;
  pending: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
      style={{ background: "var(--accent-amber)", color: "#000" }}
    >
      {pending ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <Icon className="w-3.5 h-3.5" />
      )}
      {label}
    </button>
  );
}
