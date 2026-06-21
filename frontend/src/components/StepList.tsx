interface Step {
  label: string
  state: 'done' | 'active' | 'pending'
}

interface Props {
  steps: Step[]
}

export function StepList({ steps }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {steps.map((s, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Indicator */}
          {s.state === 'done' ? (
            <div style={{
              width: 22, height: 22, borderRadius: '50%',
              background: '#041510', border: '1.5px solid #059669',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
                <path d="M1 4.5L4 7.5L10 1.5" stroke="#059669" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          ) : s.state === 'active' ? (
            <div className="step-pulse" style={{
              width: 22, height: 22, borderRadius: '50%',
              border: '1.5px solid #059669',
              background: 'rgba(5,150,105,.15)',
              flexShrink: 0,
            }} />
          ) : (
            <div style={{
              width: 22, height: 22, borderRadius: '50%',
              border: '1.5px solid #2a2a2e',
              background: 'transparent',
              flexShrink: 0,
            }} />
          )}
          <span style={{
            fontSize: 14,
            color: s.state === 'done' ? '#6ee7b7' : s.state === 'active' ? '#e8e8ea' : '#444',
            fontWeight: s.state === 'active' ? 500 : 400,
          }}>
            {s.label}
          </span>
        </div>
      ))}
    </div>
  )
}
