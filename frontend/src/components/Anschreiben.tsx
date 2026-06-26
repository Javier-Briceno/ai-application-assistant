import { useRef, useState, useEffect } from 'react'
import { useApp } from '@/context/AppContext'
import { api } from '@/lib/api'

interface Props {
  text: string
  applicationId?: number
  profileName?: string
  profileStreet?: string
  profilePostalCode?: string
  profileCity?: string
  profilePhone?: string
  profileEmail?: string
  profileLinkedin?: string
  profileGithub?: string
  companyName?: string
  companyAddress?: string
  downloadHref?: string
}

function cleanUrl(url: string): string {
  return url.replace(/^https?:\/\//i, '')
}

function buildSenderLines(name: string, street: string, postalCode: string, city: string, phone: string, email: string, linkedin: string, github: string): string[] {
  const lines: string[] = []
  if (name) lines.push(name)
  if (street || postalCode) {
    const postalCity = [postalCode, city].filter(Boolean).join(' ')
    const addressLine = [street, postalCity].filter(Boolean).join(', ')
    if (addressLine) lines.push(addressLine)
  } else if (city) {
    lines.push(city)
  }
  if (phone) lines.push(phone)
  if (email) lines.push(email)
  if (linkedin) lines.push(cleanUrl(linkedin))
  if (github) lines.push(cleanUrl(github))
  return lines
}

// Build HTML for the editable region (company block + date + letter body only — no sender).
function buildHTML(recipientLines: string[], date: string, bodyText: string): string {
  const escape = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const line = (text: string, style = '') =>
    `<div${style ? ` style="${style}"` : ''}>${text ? escape(text) : '<br>'}</div>`

  return [
    ...recipientLines.map(l => line(l)),
    ...(recipientLines.length ? [line(date, 'text-align:right'), line('')] : []),
    line(''),
    ...bodyText.split('\n').map(l => line(l)),
  ].join('')
}

const DATE_RE = /^\d{1,2}\. \w+ \d{4}$/
const BODY_STARTERS = ['sehr geehrte', 'bewerbung', 'mit freundlichen', 'ich bewerbe', 'hochachtungsvoll', 'betreff']

// Parse a saved anschreiben text that may start with the company block.
// Returns null if no company block is detected (text starts directly with letter body).
function parseCompanyFromText(text: string): { recipientLines: string[]; date: string; body: string } | null {
  const lines = text.split('\n')
  const firstLine = lines[0]?.trim() ?? ''

  if (!firstLine || BODY_STARTERS.some(s => firstLine.toLowerCase().startsWith(s))) {
    return null
  }

  const recipientLines: string[] = []
  let dateFound = ''
  let i = 0

  while (i < lines.length && lines[i].trim()) {
    const stripped = lines[i].trim()
    if (DATE_RE.test(stripped)) {
      dateFound = stripped
    } else {
      recipientLines.push(stripped)
    }
    i++
  }

  if (recipientLines.length === 0) return null

  while (i < lines.length && !lines[i].trim()) i++

  return { recipientLines, date: dateFound, body: lines.slice(i).join('\n') }
}

// Read editor content as plain text without relying on innerText (which doubles newlines
// under certain white-space CSS settings). Each direct child <div> = one line.
function divToText(el: HTMLElement): string {
  const lines: string[] = []
  for (const node of Array.from(el.childNodes)) {
    const name = node.nodeName
    if (name === 'DIV' || name === 'P') {
      const div = node as HTMLElement
      const inner = div.innerHTML.toLowerCase()
      lines.push(inner === '<br>' || inner === '' ? '' : (div.textContent ?? ''))
    } else if (node.nodeType === Node.TEXT_NODE) {
      const t = (node as Text).textContent ?? ''
      if (t.trim()) lines.push(t)
    }
  }
  return lines.join('\n')
}

export function Anschreiben({ text: initialText, applicationId, profileName, profileStreet, profilePostalCode, profileCity, profilePhone, profileEmail, profileLinkedin, profileGithub, companyName, companyAddress, downloadHref }: Props) {
  const editorRef = useRef<HTMLDivElement>(null)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const prevHtml = useRef<string | null>(null)

  const [copied, setCopied] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const { showToast } = useApp()

  const today = new Date().toLocaleDateString('de-DE', { day: 'numeric', month: 'long', year: 'numeric' })

  const senderLines = buildSenderLines(
    profileName ?? '', profileStreet ?? '', profilePostalCode ?? '',
    profileCity ?? '', profilePhone ?? '', profileEmail ?? '',
    profileLinkedin ?? '', profileGithub ?? '',
  )

  // Determine what goes into the editable region.
  // If the saved text already has a company block at the top, use it directly.
  // Otherwise prepend the company block from props.
  const parsed = parseCompanyFromText(initialText)
  const effectiveRecipientLines = parsed?.recipientLines ?? [
    ...(companyName ? [companyName] : []),
    ...(companyAddress ? [companyAddress] : []),
  ]
  const effectiveDate = parsed?.date ?? today
  const effectiveBody = parsed?.body ?? initialText
  const html = buildHTML(effectiveRecipientLines, effectiveDate, effectiveBody)

  useEffect(() => {
    if (!editorRef.current) return
    if (html === prevHtml.current) return
    prevHtml.current = html
    editorRef.current.innerHTML = html
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialText, companyName, companyAddress])

  const handleInput = () => {
    if (!applicationId) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    setSaveStatus('saving')
    saveTimer.current = setTimeout(async () => {
      if (!editorRef.current) return
      const text = divToText(editorRef.current)
      try {
        await api.applications.patchAnschreiben(applicationId, text)
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      } catch {
        setSaveStatus('idle')
        showToast('Speichern fehlgeschlagen')
      }
    }, 800)
  }

  const copy = async () => {
    try {
      const senderText = senderLines.join('\n')
      const bodyText = editorRef.current ? divToText(editorRef.current) : ''
      const full = senderText ? `${senderText}\n\n${bodyText}` : bodyText
      await navigator.clipboard.writeText(full)
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
        {saveStatus !== 'idle' && (
          <span style={{ fontSize: 10, color: saveStatus === 'saved' ? '#059669' : '#555' }}>
            {saveStatus === 'saving' ? 'Speichern…' : 'Gespeichert ✓'}
          </span>
        )}
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, #083a20, transparent)', marginLeft: 4 }} />
        {downloadHref && (
          <a href={downloadHref} download style={{
            display: 'flex', alignItems: 'center', gap: 4, background: 'none', border: '1px solid #1e3a1e',
            borderRadius: 5, color: '#059669', fontSize: 11, padding: '2px 7px', cursor: 'pointer',
            textDecoration: 'none',
          }}>
            <DownloadIcon /> .docx
          </a>
        )}
      </div>

      {/* Card */}
      <div style={{ border: '1px solid #1e3a1e', borderRadius: 7, overflow: 'hidden' }}>

        {/* Locked sender block (profile data) */}
        {senderLines.length > 0 && (
          <div
            onClick={() => showToast('Absenderdaten im Profil bearbeiten')}
            style={{
              padding: '14px 48px 12px 14px',
              borderBottom: '1px dashed #1a2e1a',
              fontSize: 13,
              color: '#5a7a5a',
              lineHeight: 1.75,
              cursor: 'default',
              userSelect: 'none',
              background: '#080f08',
              position: 'relative',
            }}
          >
            {senderLines.map((line, i) => <div key={i}>{line}</div>)}
            <span style={{
              position: 'absolute',
              top: 8,
              right: 8,
              fontSize: 9,
              color: '#2a4a2a',
              border: '1px solid #1e2e1e',
              borderRadius: 3,
              padding: '1px 5px',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
            }}>
              Profil
            </span>
          </div>
        )}

        {/* Editable: company block + date + letter body */}
        <div style={{ position: 'relative', background: '#0a0f0d' }}>
          <button
            onClick={copy}
            title="Kopieren"
            style={{
              position: 'absolute',
              top: 8,
              right: 8,
              width: 28,
              height: 28,
              background: copied ? '#041510' : 'rgba(10,15,13,.9)',
              border: `1px solid ${copied ? '#059669' : '#1e3a1e'}`,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: '#059669',
              transition: 'all .2s',
              zIndex: 1,
            }}
          >
            {copied ? <CheckIcon /> : <ClipboardIcon />}
          </button>
          <div
            ref={editorRef}
            contentEditable
            suppressContentEditableWarning
            onInput={handleInput}
            style={{
              minHeight: 320,
              padding: '14px 48px 14px 14px',
              fontSize: 13,
              color: '#d4e8d4',
              lineHeight: 1.75,
              fontFamily: 'inherit',
              outline: 'none',
              wordBreak: 'break-word',
            }}
          />
        </div>
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
