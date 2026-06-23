import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { profileColor } from '@/lib/profileColor'
import { api } from '@/lib/api'
import { CvDiff } from '@/components/CvDiff'
import { Anschreiben } from '@/components/Anschreiben'
import { Bewertung } from '@/components/Bewertung'
import { ChatPopup } from '@/components/ChatPopup'
import type { Application, RequirementsAnalysisData, ScoringResult } from '@/types'

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('de-DE', { day: 'numeric', month: 'short' })
}

function thresholdLabel(t: string): string {
  return t === 'pass' ? 'Empfohlen' : t === 'caution' ? 'Grenzfall' : 'Nicht empfohlen'
}

function thresholdColors(t: string) {
  if (t === 'pass') return { color: '#6ee7b7', border: '#059669', bg: '#041510', bar: '#059669' }
  if (t === 'caution') return { color: '#fbbf24', border: '#f59e0b', bg: '#1a1000', bar: '#f59e0b' }
  return { color: '#fca5a5', border: '#b91c1c', bg: '#1a0505', bar: '#b91c1c' }
}

function appToScoring(app: Application): ScoringResult {
  const empty = { score: 0, reasoning: '' }
  return {
    total_score: app.score,
    threshold: app.threshold,
    technical:    app.scoring_details?.technical    ?? empty,
    requirements: app.scoring_details?.requirements ?? empty,
    role_fit:     app.scoring_details?.role_fit     ?? empty,
    location:     app.scoring_details?.location     ?? empty,
    strategic:    app.scoring_details?.strategic    ?? empty,
  }
}

export function VerlaufPage() {
  const navigate = useNavigate()

  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: api.profiles.list })
  const [filterProfileId, setFilterProfileId] = useState<number | null>(null)
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null)

  // null = "Alle Profile" (no fallback — explicitly show all)
  const profileId = filterProfileId

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ['applications', profileId],
    queryFn: () => api.applications.list(profileId),
    enabled: profiles.length > 0,
  })

  // Auto-select newest entry
  useEffect(() => {
    if (apps.length > 0 && selectedAppId === null) {
      setSelectedAppId(apps[0].id)
    }
  }, [apps])

  // Reset selection on profile change
  useEffect(() => {
    setSelectedAppId(null)
  }, [profileId])

  const selectedApp = apps.find((a) => a.id === selectedAppId) ?? null
  const selectedProfile = profiles.find((p) => p.id === selectedApp?.profile_id) ?? null
  const profileName = selectedProfile
    ? `${selectedProfile.first_name ?? ''} ${selectedProfile.last_name ?? ''}`.trim()
    : ''

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* ── Timeline ─────────────────────────────── */}
      <aside style={{
        width: 300,
        minWidth: 240,
        borderRight: '1px solid #1e1e22',
        display: 'flex',
        flexDirection: 'column',
        background: '#080810',
        overflow: 'hidden',
      }}>
        {/* Filter */}
        <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid #1e1e22', flexShrink: 0 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: '#555', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 }}>
            Verlauf
          </div>
          <select
            value={filterProfileId ?? ''}
            onChange={(e) => {
              setFilterProfileId(e.target.value ? Number(e.target.value) : null)
              setSelectedAppId(null)
            }}
            style={{
              width: '100%',
              background: '#0a0a0c',
              border: '1px solid #1e1e22',
              borderRadius: 6,
              padding: '5px 8px',
              fontSize: 12,
              color: '#aaa',
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            <option value="">Alle Profile</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>{p.display_name}</option>
            ))}
          </select>
        </div>

        {/* Entries */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
          {isLoading && (
            <div style={{ padding: 12, fontSize: 12, color: '#444' }}>Lade…</div>
          )}
          {!isLoading && apps.length === 0 && (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '100%', gap: 12, padding: 20,
            }}>
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#2a2a2e" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              <p style={{ fontSize: 12, color: '#444', textAlign: 'center' }}>Noch keine Analysen</p>
              <button
                onClick={() => navigate('/')}
                style={{
                  background: 'none', border: '1px solid #1e3a1e', borderRadius: 6,
                  color: '#059669', fontSize: 12, padding: '5px 12px', cursor: 'pointer',
                }}
              >
                Zur Analyse →
              </button>
            </div>
          )}
          {apps.map((app) => {
            const isSelected = app.id === selectedAppId
            const tc = thresholdColors(app.threshold)
            const pColor = profileColor(app.profile_id)

            return (
              <div
                key={app.id}
                onClick={() => setSelectedAppId(app.id)}
                style={{
                  padding: '9px 11px',
                  borderRadius: 8,
                  marginBottom: 6,
                  cursor: 'pointer',
                  background: isSelected ? '#0a1a0f' : 'transparent',
                  border: isSelected ? '1px solid #1e3a1e' : '1px solid transparent',
                  boxShadow: isSelected ? '0 2px 10px rgba(5,150,105,.1)' : 'none',
                  transition: 'all .15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: pColor, flexShrink: 0, marginTop: 4 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: isSelected ? '#e8e8ea' : '#aaa', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {app.company}
                    </div>
                    <div style={{ fontSize: 11, color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 1 }}>
                      {app.role_title}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6, marginLeft: 14 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 99,
                    color: tc.color, border: `1px solid ${tc.border}55`, background: tc.bg,
                  }}>
                    {thresholdLabel(app.threshold)}
                  </span>
                  <span style={{ fontSize: 10, color: '#444' }}>{formatDate(app.date_applied)}</span>
                </div>
              </div>
            )
          })}
        </div>
      </aside>

      {/* ── Detail panel ─────────────────────────── */}
      <main style={{ flex: 1, overflowY: 'auto', background: '#0a0a0c' }}>
        {!selectedApp ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            height: '100%', gap: 10, color: '#2a2a2e', userSelect: 'none',
          }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity=".3">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <p style={{ fontSize: 13, color: '#333' }}>Eintrag auswählen</p>
          </div>
        ) : (
          <div className="fade-in" style={{ padding: '28px 36px', display: 'flex', flexDirection: 'column', gap: 36 }}>
            {/* Header */}
            <div style={{ borderBottom: '1px solid #1e1e22', paddingBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e8e8ea', margin: 0, lineHeight: 1.2 }}>
                    {selectedApp.company}
                  </h1>
                  {selectedApp.role_title && (
                    <div style={{ fontSize: 14, color: '#666', marginTop: 3 }}>{selectedApp.role_title}</div>
                  )}
                  <div style={{ fontSize: 12, color: '#444', marginTop: 4 }}>
                    {formatDate(selectedApp.date_applied)}
                  </div>
                </div>
                <ThresholdChip threshold={selectedApp.threshold} />
              </div>
            </div>

            {/* Requirements warning — shown before score so blockers are seen first */}
            {selectedApp.scoring_details?.requirements_analysis && (
              <RequirementsWarning analysis={selectedApp.scoring_details.requirements_analysis} />
            )}

            {/* Bewertung with per-dimension scores when available */}
            <Bewertung scoring={appToScoring(selectedApp)} />

            {/* CV Diff */}
            {selectedApp.cv_diff && (
              <CvDiff
                diff={selectedApp.cv_diff}
                applicationId={selectedApp.id}
                downloadHref={selectedApp.has_tailored_cv ? api.applications.cvDocxUrl(selectedApp.id) : undefined}
              />
            )}

            {/* Truthfulness warning — persisted from scoring_details */}
            {(selectedApp.scoring_details?.truthfulness_warning ?? []).length > 0 && (
              <div style={{
                background: '#1a1100',
                border: '1px solid #854d0e',
                borderRadius: 8,
                padding: '12px 16px',
                color: '#fbbf24',
                fontSize: 12,
                lineHeight: 1.6,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  Hinweis: Das Anschreiben enthält möglicherweise nicht vollständig belegte Angaben.
                </div>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {selectedApp.scoring_details!.truthfulness_warning!.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Anschreiben */}
            {selectedApp.anschreiben && (
              <Anschreiben
                text={selectedApp.anschreiben}
                profileName={profileName}
                companyName={selectedApp.company}
                downloadHref={api.applications.anschreibenDocxUrl(selectedApp.id)}
              />
            )}
          </div>
        )}

        {/* Chat popup — shown whenever an app is selected */}
        {selectedApp && (
          <ChatPopup
            key={selectedApp.id}
            companyName={selectedApp.company}
            jobApplicationId={selectedApp.id}
          />
        )}
      </main>
    </div>
  )
}

function RequirementsWarning({ analysis }: { analysis: RequirementsAnalysisData }) {
  const dealbreakers = analysis.triggered_dealbreakers ?? []
  const hardMissing = analysis.missing_hard_requirements ?? []
  if (dealbreakers.length === 0 && hardMissing.length === 0) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {dealbreakers.length > 0 && (
        <div style={{ background: '#140a0a', border: '1px solid #7f1d1d', borderRadius: 8, padding: '12px 16px', fontSize: 12, lineHeight: 1.6 }}>
          <div style={{ fontWeight: 600, color: '#fca5a5', marginBottom: 4 }}>Mögliche Ausschlusskriterien</div>
          <div style={{ color: '#f87171', marginBottom: 8, fontSize: 11 }}>
            Die Bewerbungsunterlagen wurden trotzdem erstellt. Bitte prüfen Sie diese Anforderungen sorgfältig.
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, color: '#fca5a5' }}>
            {dealbreakers.map((d, i) => <li key={i}><strong>{d.requirement}</strong> — {d.reason}</li>)}
          </ul>
        </div>
      )}
      {hardMissing.length > 0 && (
        <div style={{ background: '#1a1100', border: '1px solid #854d0e', borderRadius: 8, padding: '12px 16px', fontSize: 12, lineHeight: 1.6 }}>
          <div style={{ fontWeight: 600, color: '#fbbf24', marginBottom: 6 }}>Fehlende Pflichtanforderungen</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: '#fbbf24' }}>
            {hardMissing.map((m, i) => <li key={i}><strong>{m.requirement}</strong> — {m.reason}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function ThresholdChip({ threshold }: { threshold: string }) {
  const m: Record<string, { label: string; color: string; border: string; bg: string }> = {
    pass:    { label: 'Empfohlen',       color: '#6ee7b7', border: '#059669', bg: '#041510' },
    caution: { label: 'Grenzfall',       color: '#fbbf24', border: '#f59e0b', bg: '#1a1000' },
    fail:    { label: 'Nicht empfohlen', color: '#fca5a5', border: '#b91c1c', bg: '#1a0505' },
  }
  const s = m[threshold] ?? m.fail
  return (
    <span style={{
      padding: '3px 10px', borderRadius: 99, border: `1px solid ${s.border}`,
      background: s.bg, color: s.color, fontSize: 11, fontWeight: 600, flexShrink: 0,
    }}>
      {s.label}
    </span>
  )
}
