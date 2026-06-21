import { useState } from 'react'
import type { ScoringResult } from '@/types'

const DIMS = [
  { key: 'technical' as const,    label: 'Technik' },
  { key: 'requirements' as const, label: 'Anforderungen' },
  { key: 'role_fit' as const,     label: 'Rollenfit' },
  { key: 'location' as const,     label: 'Standort' },
  { key: 'strategic' as const,    label: 'Strategie' },
]

function scoreColor(s: number): string {
  if (s >= 70) return '#059669'
  if (s >= 40) return '#f59e0b'
  return '#b91c1c'
}

function ThresholdBadge({ threshold }: { threshold: string }) {
  const map: Record<string, { label: string; color: string; bg: string; border: string }> = {
    pass:    { label: 'Empfohlen',       color: '#6ee7b7', bg: '#041510', border: '#059669' },
    caution: { label: 'Grenzfall',       color: '#fbbf24', bg: '#1a1000', border: '#f59e0b' },
    fail:    { label: 'Nicht empfohlen', color: '#fca5a5', bg: '#1a0505', border: '#b91c1c' },
  }
  const s = map[threshold] ?? map.fail
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '2px 8px',
      borderRadius: 99,
      border: `1px solid ${s.border}`,
      background: s.bg,
      color: s.color,
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '.02em',
    }}>
      {s.label}
    </span>
  )
}

interface Props {
  scoring: ScoringResult
}

export function Bewertung({ scoring }: Props) {
  const [expandedDim, setExpandedDim] = useState<string | null>(null)

  const toggle = (key: string) => setExpandedDim((prev) => (prev === key ? null : key))

  return (
    <div>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <BewertungIcon />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.1em', color: '#888', textTransform: 'uppercase' }}>
          Bewertung
        </span>
        <ThresholdBadge threshold={scoring.threshold} />
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, #083a20, transparent)', marginLeft: 4 }} />
      </div>

      {/* Dimension bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {DIMS.map(({ key, label }) => {
          const score = scoring[key].score
          const reasoning = scoring[key].reasoning
          const color = scoreColor(score)
          const isOpen = expandedDim === key

          return (
            <div key={key}>
              <button
                onClick={() => toggle(key)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '4px 0',
                }}
              >
                <span style={{ width: 78, fontSize: 11, color: '#666', textAlign: 'right', flexShrink: 0 }}>
                  {label}
                </span>
                <div style={{
                  flex: 1,
                  height: 6,
                  background: '#1e1e22',
                  borderRadius: 99,
                  overflow: 'hidden',
                }}>
                  <div
                    className="bar-anim"
                    style={{
                      height: '100%',
                      width: `${score}%`,
                      background: color,
                      borderRadius: 99,
                    }}
                  />
                </div>
                <span style={{
                  fontSize: 9,
                  color: isOpen ? '#059669' : '#333',
                  flexShrink: 0,
                  transition: 'color .15s',
                }}>
                  {isOpen ? '▼' : '▶'}
                </span>
              </button>
              {isOpen && reasoning && (
                <div
                  className="fade-in"
                  style={{
                    marginLeft: 86,
                    marginTop: 4,
                    marginBottom: 4,
                    padding: '7px 10px',
                    background: '#0a1a0f',
                    borderLeft: `2px solid ${color}`,
                    borderRadius: '0 5px 5px 0',
                    fontSize: 12,
                    color: '#aaa',
                    lineHeight: 1.6,
                  }}
                >
                  {reasoning}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function BewertungIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  )
}
