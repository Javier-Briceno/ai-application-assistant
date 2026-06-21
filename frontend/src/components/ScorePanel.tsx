import { Badge } from '@/components/ui/badge'
import type { ScoringResult } from '@/types'
import { cn } from '@/lib/utils'

const DIMS = [
  { key: 'technical', label: 'Technisch', max: 40 },
  { key: 'requirements', label: 'Anforderungen', max: 25 },
  { key: 'role_fit', label: 'Rollenfit', max: 20 },
  { key: 'location', label: 'Standort', max: 10 },
  { key: 'strategic', label: 'Strategisch', max: 5 },
] as const

const THRESHOLD_LABEL = {
  pass: '✅ Empfohlen',
  caution: '⚠️ Grenzfall',
  fail: '❌ Nicht empfohlen',
}

function DimBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = Math.round((score / max) * 100)
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{label}</span>
        <span className="tabular-nums">
          {score}/{max}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-white/10">
        <div
          className={cn(
            'h-full rounded-full transition-all',
            pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function ScorePanel({ scoring, company }: { scoring: ScoringResult; company: string }) {
  const { total_score, threshold } = scoring
  const scoreColor =
    threshold === 'pass' ? 'text-green-400' : threshold === 'caution' ? 'text-yellow-400' : 'text-red-400'

  return (
    <div className="rounded-xl border border-white/10 bg-[hsl(240_5%_10%)] p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">Gesamtscore</p>
          <div className="flex items-baseline gap-1">
            <span className={cn('text-5xl font-bold tabular-nums', scoreColor)}>{total_score}</span>
            <span className="text-gray-500 text-sm">/100</span>
          </div>
          <p className="text-sm text-gray-400 mt-1">{company}</p>
        </div>
        <Badge variant={threshold}>{THRESHOLD_LABEL[threshold]}</Badge>
      </div>

      <div className="space-y-3 pt-2 border-t border-white/10">
        {DIMS.map(({ key, label, max }) => (
          <DimBar key={key} label={label} score={(scoring as unknown as Record<string, { score: number; reasoning: string }>)[key].score} max={max} />
        ))}
      </div>
    </div>
  )
}
