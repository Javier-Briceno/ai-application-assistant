import { useState } from 'react'
import type { ScoringResult } from '@/types'

const DIMS = [
  {
    key: 'technical' as const,
    label: 'Technik',
    max: 40,
    info: 'Übereinstimmung der geforderten Technologien mit den Kernkompetenzen und Sekundärtools des Kandidaten. Bewertet sowohl Breite als auch Tiefe der technischen Passform.',
  },
  {
    key: 'requirements' as const,
    label: 'Anforderungen',
    max: 25,
    info: 'Formale und strukturelle Voraussetzungen: Studiengang, Verfügbarkeit, Arbeitszeit, Sprachkenntnisse und Erfahrungsniveau. Unerfüllte Pflichtanforderungen können das Gesamtergebnis herabstufen.',
  },
  {
    key: 'role_fit' as const,
    label: 'Rollenfit',
    max: 20,
    info: 'Wie gut die ausgeschriebene Rolle zum Karriereziel und Erfahrungsprofil des Kandidaten passt, basierend auf den intern berechneten Rollentyp-Scores.',
  },
  {
    key: 'location' as const,
    label: 'Standort',
    max: 10,
    info: 'Pendelbarkeit: Heimatstadt und Remote/Hybrid-Optionen erhalten volle Punkte. Fahrzeit über 2 Stunden bei Vor-Ort-Pflicht ergibt 0 Punkte.',
  },
  {
    key: 'strategic' as const,
    label: 'Strategie',
    max: 5,
    info: 'Langfristige Karriererelevanz: Ist diese Stelle ein klarer Schritt in Richtung Karriereziel, oder bietet sie nur indirekten Nutzen?',
  },
]

function scoreColor(s: number): string {
  if (s >= 70) return '#059669'
  if (s >= 40) return '#f59e0b'
  return '#b91c1c'
}

function InfoTooltip({ text }: { text: string }) {
  const [visible, setVisible] = useState(false)
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <svg
        width="11" height="11" viewBox="0 0 24 24" fill="none"
        stroke="#444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        style={{ cursor: 'default', display: 'block' }}
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
      {visible && (
        <span style={{
          position: 'absolute',
          left: '50%',
          bottom: 'calc(100% + 6px)',
          transform: 'translateX(-50%)',
          width: 220,
          background: '#18181b',
          border: '1px solid #2a2a2e',
          borderRadius: 6,
          padding: '7px 10px',
          fontSize: 11,
          color: '#aaa',
          lineHeight: 1.55,
          zIndex: 50,
          pointerEvents: 'none',
          whiteSpace: 'normal',
          boxShadow: '0 4px 16px rgba(0,0,0,.5)',
        }}>
          {text}
        </span>
      )}
    </span>
  )
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
  const [hoveredDim, setHoveredDim] = useState<string | null>(null)

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
        {DIMS.map(({ key, label, max, info }) => {
          const score = scoring[key].score
          const reasoning = scoring[key].reasoning
          const pct = (score / max) * 100
          const color = scoreColor(pct)
          const isOpen = expandedDim === key

          const isHovered = hoveredDim === key

          return (
            <div key={key}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  borderRadius: 6,
                  background: isHovered ? 'rgba(255,255,255,0.03)' : 'transparent',
                  transition: 'background .15s',
                  padding: '0 4px 0 0',
                  marginLeft: -4,
                }}
              >
                {/* Label + info icon */}
                <div style={{ width: 104, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4, flexShrink: 0 }}>
                  <span style={{ fontSize: 11, color: '#666' }}>{label}</span>
                  <InfoTooltip text={info} />
                </div>

                {/* Bar — clickable */}
                <button
                  onClick={() => toggle(key)}
                  onMouseEnter={() => setHoveredDim(key)}
                  onMouseLeave={() => setHoveredDim(null)}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '5px 0',
                  }}
                >
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
                        width: `${pct}%`,
                        background: color,
                        borderRadius: 99,
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 10, color: '#555', fontVariantNumeric: 'tabular-nums', width: 34, textAlign: 'right', flexShrink: 0 }}>
                    {score}/{max}
                  </span>
                  <ChevronIcon open={isOpen} hovered={isHovered} />
                </button>
              </div>

              {isOpen && reasoning && (
                <div
                  className="fade-in"
                  style={{
                    marginLeft: 112,
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

function ChevronIcon({ open, hovered }: { open: boolean; hovered: boolean }) {
  return (
    <svg
      width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke={open ? '#059669' : hovered ? '#888' : '#444'}
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, transition: 'transform .2s, stroke .15s', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

function BewertungIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  )
}
