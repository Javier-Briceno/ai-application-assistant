import { useApp } from '@/context/AppContext'

export function ToastContainer() {
  const { toasts } = useApp()
  if (toasts.length === 0) return null
  return (
    <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8, pointerEvents: 'none' }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          className="fade-in"
          style={{
            background: '#0f1a12',
            border: '1px solid #059669',
            borderRadius: 8,
            padding: '8px 14px',
            fontSize: 13,
            color: '#6ee7b7',
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            boxShadow: '0 4px 20px rgba(0,0,0,.6)',
          }}
        >
          <span style={{ fontSize: 10 }}>●</span>
          {t.message}
        </div>
      ))}
    </div>
  )
}
