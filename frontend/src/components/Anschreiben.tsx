import { useState, useEffect } from 'react'
import { useApp } from '@/context/AppContext'

interface Props {
  text: string
  profileName?: string
  profileCity?: string
  companyName?: string
  onDownload?: () => void
}

function buildHeader(name: string, city: string, company: string): string {
  const date = new Date().toLocaleDateString('de-DE', { day: 'numeric', month: 'long', year: 'numeric' })
  const lines: string[] = []
  if (name) lines.push(name)
  lines.push(city ? `${city}, ${date}` : date)
  lines.push('')
  if (company) lines.push(company)
  lines.push('')
  lines.push('')
  return lines.join('\n')
}

export function Anschreiben({ text: initialText, profileName, profileCity, companyName, onDownload }: Props) {
  const header = (profileName || companyName)
    ? buildHeader(profileName ?? '', profileCity ?? '', companyName ?? '')
    : ''
  const [text, setText] = useState(header + initialText)
  const [copied, setCopied] = useState(false)
  const { showToast } = useApp()

  useEffect(() => {
    const h = (profileName || companyName)
      ? buildHeader(profileName ?? '', profileCity ?? '', companyName ?? '')
      : ''
    setText(h + initialText)
  }, [initialText, profileName, profileCity, companyName])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      showToast('Anschreiben kopiert')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      showToast('Kopieren fehlgeschlagen')
    }
  }

  return (
    <div>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <AnschreibenIcon />
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.1em', color: '#888', textTransform: 'uppercase' }}>
          Anschreiben
        </span>
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, #083a20, transparent)', marginLeft: 4 }} />
        {onDownload && (
          <button onClick={onDownload} style={{
            display: 'flex', alignItems: 'center', gap: 4, background: 'none', border: '1px solid #1e3a1e',
            borderRadius: 5, color: '#059669', fontSize: 11, padding: '2px 7px', cursor: 'pointer',
          }}>
            <DownloadIcon /> .docx
          </button>
        )}
      </div>

      {/* Editable textarea with copy button in corner */}
      <div style={{ position: 'relative' }}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{
            width: '100%',
            minHeight: 380,
            background: '#0a0f0d',
            border: '1px solid #1e3a1e',
            borderRadius: 7,
            padding: '14px 44px 14px 14px',
            fontSize: 13,
            color: '#d4e8d4',
            lineHeight: 1.75,
            fontFamily: 'inherit',
            resize: 'vertical',
            outline: 'none',
          }}
        />
        {/* Copy icon in top-right corner of textarea */}
        <button
          onClick={copy}
          title="Kopieren"
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            width: 28,
            height: 28,
            background: copied ? '#041510' : 'rgba(10,15,13,.8)',
            border: `1px solid ${copied ? '#059669' : '#1e3a1e'}`,
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: '#059669',
            transition: 'all .2s',
          }}
        >
          {copied ? <CheckIcon /> : <ClipboardIcon />}
        </button>
      </div>
    </div>
  )
}

function AnschreibenIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
    </svg>
  )
}

function ClipboardIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="2" width="6" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="13" height="11" viewBox="0 0 13 11" fill="none">
      <path d="M1 5.5L5 9.5L12 1.5" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}
