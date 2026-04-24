import clsx from 'clsx'

export type Urgency = 'critical' | 'high' | 'medium' | 'low' | 'unscored'

export function urgencyFromScore(score: number | null | undefined): Urgency {
  if (score == null) return 'unscored'
  if (score >= 9) return 'critical'
  if (score >= 7) return 'high'
  if (score >= 5) return 'medium'
  return 'low'
}

const LABELS: Record<Urgency, string> = {
  critical: 'CRITICAL',
  high: 'HIGH',
  medium: 'MED',
  low: 'LOW',
  unscored: '—',
}

export function UrgencyBadge({ score }: { score: number | null | undefined }) {
  const u = urgencyFromScore(score)
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold tracking-wider',
        `badge-${u}`,
      )}
    >
      {LABELS[u]}
    </span>
  )
}
