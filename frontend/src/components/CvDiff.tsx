import { useState, useEffect } from 'react'

interface Props {
  diff: string
  applicationId?: number
  onDownload?: () => void
}

// Number of total lines shown before the "show all" button appears.
const PREVIEW_LINES = 30

function stripMarkdown(text: string): string {
  return text
    .replace(/^#{1,6}\s+/, '')          // ## headings
    .replace(/\*\*(.+?)\*\*/g, '$1')    // **bold**
    .replace(/\*(.+?)\*/g, '$1')        // *italic*
    .replace(/__(.+?)__/g, '$1')        // __bold__
    .replace(/_([^_\s][^_]*)_/g, '$1') // _italic_
    .replace(/`([^`]+)`/g, '$1')        // `code`
}

type LineType = 'add' | 'del' | 'ctx' | 'hunk'

function parseLine(line: string): { type: LineType; text: string } {
  // Unified diff hunk header: @@ -a,b +c,d @@
  if (line.startsWith('@@')) return { type: 'hunk', text: line }
  // Added line: + (new) or +<space> (old format)
  if (line.startsWith('+')) return { type: 'add', text: stripMarkdown(line.slice(1).trimStart()) }
  // Removed line: - (new) or -<space> (old format)
  if (line.startsWith('-')) return { type: 'del', text: stripMarkdown(line.slice(1).trimStart()) }
  // Context: single-space prefix (new unified diff) or two-space prefix (old format)
  const content = line.startsWith('  ') ? line.slice(2) : line.startsWith(' ') ? line.slice(1) : line
  return { type: 'ctx', text: stripMarkdown(content) }
}

export function CvDiff({ diff, applicationId, onDownload }: Props) {
  const [showAll, setShowAll] = useState(false)

  useEffect(() => { setShowAll(false) }, [diff])

  if (!diff?.trim()) {
    return (
      <div>
        <SectionHeader onDownload={applicationId !== undefined ? onDownload : undefined} />
        <p style={{ fontSize: 13, color: '#555', marginTop: 10 }}>Keine Änderungen.</p>
      </div>
    )
  }

  // All non-empty lines, preserving context and hunk headers
  const lines = diff.split('\n').filter((l) => l !== '')

  // Count changed lines for the summary shown in the "show more" button
  const changedCount = lines.filter((l) => l.startsWith('+') || l.startsWith('-')).length

  const preview = lines.slice(0, PREVIEW_LINES)
  const hasMore = lines.length > PREVIEW_LINES
  const displayed = showAll ? lines : preview

  return (
    <div>
      <SectionHeader onDownload={applicationId !== undefined ? onDownload : undefined} />
      <div style={{
        fontFamily: 'ui-monospace, monospace',
        fontSize: 12,
        lineHeight: 1.8,
        background: '#080810',
        border: '1px solid #1e1e22',
        borderRadius: 7,
        overflow: 'hidden',
        padding: '4px 0',
        marginTop: 14,
      }}>
        {displayed.map((line, i) => {
          const { type, text } = parseLine(line)

          if (type === 'hunk') {
            return (
              <div key={i} style={{
                padding: '2px 10px',
                color: '#2a4a5a',
                fontSize: 10,
                borderTop: i > 0 ? '1px solid #111116' : undefined,
                borderBottom: '1px solid #111116',
                userSelect: 'none',
                letterSpacing: '.04em',
              }}>
                {text}
              </div>
            )
          }

          return (
            <div key={i} style={{ display: 'flex', alignItems: 'baseline' }}>
              <span style={{
                width: 20,
                flexShrink: 0,
                textAlign: 'center',
                color: type === 'add' ? '#059669' : type === 'del' ? '#7f1d1d' : '#222',
                fontSize: 11,
                userSelect: 'none',
              }}>
                {type === 'add' ? '+' : type === 'del' ? '−' : ' '}
              </span>
              <span
                className={type === 'add' ? 'diff-add' : type === 'del' ? 'diff-del' : 'diff-ctx'}
                style={{ flex: 1, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                {text || ' '}
              </span>
            </div>
          )
        })}
      </div>

      {hasMore && (
        <button
          onClick={() => setShowAll((v) => !v)}
          style={{
            marginTop: 8, background: 'none', border: '1px solid #1e3a1e', borderRadius: 6,
            color: '#059669', fontSize: 12, padding: '4px 12px', cursor: 'pointer',
          }}
        >
          {showAll
            ? 'Weniger anzeigen ↑'
            : `Alle ${changedCount} Änderungen anzeigen (${lines.length - PREVIEW_LINES} weitere Zeilen)`}
        </button>
      )}
    </div>
  )
}

function SectionHeader({ onDownload }: { onDownload?: () => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
      <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.1em', color: '#888', textTransform: 'uppercase' }}>
        Lebenslauf-Änderungen
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
  )
}

function DownloadIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}
