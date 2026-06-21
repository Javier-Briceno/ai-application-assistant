import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  companyName: string
  jobTitle?: string
  jobApplicationId: number | null
}

export function ChatPopup({ companyName, jobTitle, jobApplicationId }: Props) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const welcomeMsg: Message = {
    role: 'assistant',
    content: `Ich kenne deine Bewerbung bei ${companyName}${jobTitle ? ` als ${jobTitle}` : ''}. Stell mir Fragen zur Analyse, zum Lebenslauf oder zum Anschreiben.`,
  }

  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([welcomeMsg])
    }
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || streaming) return
    const userMsg: Message = { role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setStreaming(true)

    const history = [...messages, userMsg]
    const assistantMsg: Message = { role: 'assistant', content: '' }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_application_id: jobApplicationId,
          company_name: companyName,
          messages: history.map((m) => ({ role: m.role, content: m.content })),
        }),
      })
      if (!res.ok || !res.body) throw new Error('Chat nicht verfügbar')
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6))
              if (d.delta) {
                setMessages((prev) => {
                  const next = [...prev]
                  next[next.length - 1] = { role: 'assistant', content: next[next.length - 1].content + d.delta }
                  return next
                })
              }
            } catch { /* skip */ }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = { role: 'assistant', content: 'Entschuldigung, der Chat ist gerade nicht verfügbar.' }
        return next
      })
    } finally {
      setStreaming(false)
    }
  }

  return (
    <>
      {/* Trigger pill */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 16px',
            background: '#041510',
            border: '1px solid #059669',
            borderRadius: 99,
            color: '#6ee7b7',
            fontSize: 13,
            fontWeight: 500,
            cursor: 'pointer',
            zIndex: 40,
            boxShadow: '0 4px 20px rgba(5,150,105,.2)',
            transition: 'box-shadow .2s',
          }}
        >
          Frage stellen
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 17L17 7M17 7H7M17 7v10" />
          </svg>
        </button>
      )}

      {/* Chat popup */}
      {open && (
        <div
          className="fade-in"
          style={{
            position: 'fixed',
            bottom: 20,
            right: 20,
            width: 340,
            height: 440,
            background: '#0d0d12',
            border: '1px solid #1e3a1e',
            borderRadius: 12,
            display: 'flex',
            flexDirection: 'column',
            zIndex: 200,
            boxShadow: '0 8px 40px rgba(0,0,0,.8)',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 12px',
            borderBottom: '1px solid #1e1e22',
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%', background: '#059669',
              boxShadow: '0 0 6px #059669',
            }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#e8e8ea', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {companyName}
              </div>
              {jobTitle && (
                <div style={{ fontSize: 10, color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {jobTitle}
                </div>
              )}
            </div>
            <button
              onClick={() => setOpen(false)}
              style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', fontSize: 16, lineHeight: 1, padding: 2 }}
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
                <div style={{
                  maxWidth: '85%',
                  padding: '7px 10px',
                  borderRadius: m.role === 'user' ? '12px 12px 3px 12px' : '12px 12px 12px 3px',
                  background: m.role === 'user' ? '#1e1e22' : '#041510',
                  border: m.role === 'user' ? '1px solid #2a2a2e' : '1px solid #083a20',
                  fontSize: 12,
                  color: m.role === 'user' ? '#ccc' : '#a7f3d0',
                  lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}>
                  {m.content}
                  {streaming && i === messages.length - 1 && m.role === 'assistant' && m.content === '' && (
                    <span className="step-pulse" style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#059669', marginLeft: 2 }} />
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{ padding: '8px 10px', borderTop: '1px solid #1e1e22', display: 'flex', gap: 6 }}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
              placeholder="Frage stellen…"
              style={{
                flex: 1,
                background: '#0a0a0c',
                border: '1px solid #1e3a1e',
                borderRadius: 6,
                padding: '6px 10px',
                fontSize: 12,
                color: '#e8e8ea',
                outline: 'none',
              }}
            />
            <button
              onClick={send}
              disabled={!input.trim() || streaming}
              style={{
                padding: '6px 10px',
                background: input.trim() && !streaming ? '#059669' : '#041510',
                border: '1px solid #1e3a1e',
                borderRadius: 6,
                color: '#fff',
                fontSize: 12,
                cursor: input.trim() && !streaming ? 'pointer' : 'default',
                transition: 'background .15s',
              }}
            >
              ↑
            </button>
          </div>
        </div>
      )}
    </>
  )
}
