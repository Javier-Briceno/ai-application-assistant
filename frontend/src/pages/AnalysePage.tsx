import { useRef, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { useApp } from '@/context/AppContext'
import { api, streamAnalyze } from '@/lib/api'
import type { PipelineResult } from '@/types'
import { StepList } from '@/components/StepList'
import { Bewertung } from '@/components/Bewertung'
import { CvDiff } from '@/components/CvDiff'
import { Anschreiben } from '@/components/Anschreiben'
import { ChatPopup } from '@/components/ChatPopup'

const STEP_LABELS = [
  'Profil wird geladen...',
  'Unternehmen wird recherchiert & Lebenslauf wird vorbereitet...',
  'Stelle wird analysiert & bewertet...',
  'Lebenslauf wird angepasst...',
  'Anschreiben wird verfasst...',
  'Ergebnisse werden gespeichert...',
]

interface LoadingStep {
  label: string
  state: 'done' | 'active' | 'pending'
}

function buildSteps(activeMsg: string): LoadingStep[] {
  const matched = STEP_LABELS.findIndex((l) => l === activeMsg)
  return STEP_LABELS.map((label, i) => ({
    label,
    state: matched === -1
      ? (i === 0 ? 'active' : 'pending')
      : i < matched ? 'done' : i === matched ? 'active' : 'pending',
  }))
}

// Module-level reference keeps the Promise alive regardless of component lifecycle
// eslint-disable-next-line prefer-const
let _analyzeTask: Promise<void> | null = null

interface AnalyzeCallbacks {
  setAnalyzing: (v: boolean) => void
  setResult: (r: PipelineResult | null) => void
  setError: (s: string | null) => void
  setStepMsg: (s: string) => void
  qc: QueryClient
}

async function _runAnalysis(
  profileId: number,
  posting: string,
  cb: AnalyzeCallbacks,
) {
  cb.setAnalyzing(true)
  cb.setResult(null)
  cb.setError(null)
  cb.setStepMsg('')

  try {
    for await (const event of streamAnalyze(profileId, posting)) {
      if (event.type === 'step') {
        cb.setStepMsg(event.message)
      } else if (event.type === 'result') {
        cb.setResult(event.data)
        cb.qc.invalidateQueries({ queryKey: ['applications'] })
      } else if (event.type === 'error') {
        cb.setError(event.message)
      }
    }
  } catch (err: unknown) {
    cb.setError(err instanceof Error ? err.message : 'Unbekannter Fehler')
  } finally {
    cb.setAnalyzing(false)
    cb.setStepMsg('')
    _analyzeTask = null
  }
}

export function AnalysePage() {
  const qc = useQueryClient()
  const {
    activeProfileId, setActiveProfileId,
    analyzeResult: result, setAnalyzeResult: setResult,
    analyzePosting: posting, setAnalyzePosting: setPosting,
    analyzing, setAnalyzing,
    stepMsg, setStepMsg,
    analyzeError: error, setAnalyzeError: setError,
    showToast,
  } = useApp()
  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: api.profiles.list })
  const [showScrollHint, setShowScrollHint] = useState(false)
  const resultsRef = useRef<HTMLDivElement>(null)

  const resolvedProfileId = activeProfileId ?? profiles[0]?.id ?? null
  const activeProfile = profiles.find((p) => p.id === resolvedProfileId) ?? null

  // Auto-select first profile if none selected
  useEffect(() => {
    if (!activeProfileId && profiles.length > 0) {
      setActiveProfileId(profiles[0].id)
    }
  }, [profiles, activeProfileId, setActiveProfileId])

  // Show scroll hint when a result arrives while this component is mounted
  useEffect(() => {
    if (result && !analyzing) {
      setShowScrollHint(true)
      const t = setTimeout(() => {
        resultsRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
        setTimeout(() => setShowScrollHint(false), 1600)
      }, 100)
      return () => clearTimeout(t)
    }
  }, [result, analyzing])

  const analyze = () => {
    if (!resolvedProfileId || !posting.trim() || analyzing || _analyzeTask) return
    _analyzeTask = _runAnalysis(resolvedProfileId, posting, {
      setAnalyzing, setResult, setError, setStepMsg, qc,
    })
  }

  const profileName = activeProfile
    ? `${activeProfile.first_name ?? ''} ${activeProfile.last_name ?? ''}`.trim()
    : ''

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* ── Left panel — Input ─────────────────────────── */}
      <aside style={{
        width: '35%',
        minWidth: 280,
        maxWidth: 420,
        borderRight: '1px solid #1e1e22',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: '#080810',
      }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Textarea */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 11, fontWeight: 600, color: '#555', textTransform: 'uppercase', letterSpacing: '.08em' }}>
              Stellenausschreibung
            </label>
            <div style={{ position: 'relative', flex: 1 }}>
              <textarea
                value={posting}
                onChange={(e) => setPosting(e.target.value)}
                placeholder="Kopiere die Stellenausschreibung von der Unternehmenswebseite und füge sie hier ein."
                style={{
                  width: '100%',
                  minHeight: 360,
                  height: '100%',
                  background: '#0a0a0c',
                  border: `1px solid ${posting ? '#1e3a1e' : '#1e1e22'}`,
                  borderRadius: 8,
                  padding: '12px 14px',
                  fontSize: 13,
                  color: '#e8e8ea',
                  lineHeight: 1.6,
                  resize: 'none',
                  outline: 'none',
                  fontFamily: 'inherit',
                  transition: 'border-color .2s',
                }}
              />
            </div>
          </div>

          {/* Analyse button */}
          <button
            onClick={analyze}
            disabled={!resolvedProfileId || !posting.trim() || analyzing}
            style={{
              width: '100%',
              padding: '11px 0',
              background: analyzing ? '#09261a' : '#059669',
              border: `1px solid ${analyzing ? '#1e4a2a' : '#059669'}`,
              borderRadius: 8,
              color: analyzing ? '#2a5a3a' : '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: (!resolvedProfileId || !posting.trim() || analyzing) ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              transition: 'background .2s, color .2s',
              opacity: (!resolvedProfileId || !posting.trim()) ? 0.5 : 1,
            }}
          >
            {analyzing ? (
              <>
                <SpinnerIcon />
                Analysiere…
              </>
            ) : 'Analysieren'}
          </button>

          {!resolvedProfileId && (
            <p style={{ fontSize: 12, color: '#555', textAlign: 'center', margin: 0 }}>
              Wähle ein Profil über das Avatar-Symbol links
            </p>
          )}
        </div>
      </aside>

      {/* ── Right panel — Results ─────────────────────── */}
      <main
        ref={resultsRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          position: 'relative',
          background: '#0a0a0c',
        }}
      >
        {/* Scroll hint */}
        {showScrollHint && (
          <div
            className="fade-in"
            style={{
              position: 'sticky',
              top: 12,
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 10,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '4px 12px',
              background: '#041510',
              border: '1px solid #059669',
              borderRadius: 99,
              fontSize: 12,
              color: '#6ee7b7',
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
            }}
          >
            ↑ Neue Ergebnisse
          </div>
        )}

        {/* Loading */}
        {analyzing && (
          <div className="fade-in" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 400 }}>
            <StepList steps={buildSteps(stepMsg)} />
          </div>
        )}

        {/* Error */}
        {!analyzing && error && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            height: '100%', gap: 12, padding: 36,
          }}>
            <div style={{ fontSize: 13, color: '#b91c1c', textAlign: 'center', maxWidth: 340 }}>{error}</div>
            <button onClick={() => setError(null)} style={{
              background: 'none', border: '1px solid #2a2a2e', borderRadius: 6, color: '#888',
              fontSize: 12, padding: '5px 12px', cursor: 'pointer',
            }}>
              Verwerfen
            </button>
          </div>
        )}

        {/* Empty state */}
        {!analyzing && !error && !result && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            height: '100%', gap: 10, color: '#2a2a2e', userSelect: 'none',
          }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity=".4">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <p style={{ fontSize: 13, color: '#444', textAlign: 'center', maxWidth: 240 }}>
              Füge eine Stellenausschreibung ein und klicke Analysieren
            </p>
          </div>
        )}

        {/* Results */}
        {!analyzing && !error && result && (
          <div className="fade-in" style={{ padding: '28px 36px', display: 'flex', flexDirection: 'column', gap: 36 }}>
            {/* Header: company + score badge */}
            <div style={{ borderBottom: '1px solid #1e1e22', paddingBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e8e8ea', margin: 0, lineHeight: 1.2 }}>
                    {result.company.company_name}
                  </h1>
                  <div style={{ fontSize: 13, color: '#555', marginTop: 3 }}>
                    {new Date().toLocaleDateString('de-DE', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </div>
                </div>
                <ThresholdChip threshold={result.scoring.threshold} />
              </div>
            </div>

            {/* Bewertung */}
            <Bewertung scoring={result.scoring} />

            {/* CV Diff */}
            {result.tailoring?.cv_diff && (
              <CvDiff
                diff={result.tailoring.cv_diff}
                applicationId={result.job_application_id ?? undefined}
                onDownload={result.job_application_id ? () => api.applications.downloadCv(result.job_application_id!) : undefined}
              />
            )}

            {/* Anschreiben */}
            {result.anschreiben_text && (
              <Anschreiben
                text={result.anschreiben_text}
                profileName={profileName}
                profileCity={activeProfile?.home_location ?? ''}
                companyName={result.company.company_name}
                onDownload={result.job_application_id ? () => api.applications.downloadAnschreiben(result.job_application_id!) : undefined}
              />
            )}
          </div>
        )}

        {/* Chat pill — only when results are visible */}
        {result && !analyzing && (
          <ChatPopup
            companyName={result.company.company_name}
            jobApplicationId={result.job_application_id}
          />
        )}
      </main>
    </div>
  )
}

function SpinnerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" style={{ animation: 'spin 1s linear infinite' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
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
