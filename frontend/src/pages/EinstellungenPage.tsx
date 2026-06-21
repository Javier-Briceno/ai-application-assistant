export function EinstellungenPage() {
  return (
    <div style={{ padding: '40px 48px', maxWidth: 560 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, color: '#e8e8ea', marginBottom: 6 }}>Einstellungen</h1>
      <p style={{ fontSize: 13, color: '#555', marginBottom: 32 }}>Konfiguration und App-Einstellungen</p>
      <div style={{
        background: '#0f0f12', border: '1px solid #1e1e22', borderRadius: 10,
        padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#059669', textTransform: 'uppercase', letterSpacing: '.08em' }}>
          App-Info
        </div>
        <InfoRow label="Version" value="1.0.0" />
        <InfoRow label="Modell Analyse" value="GPT-4.1" />
        <InfoRow label="Modell Generator" value="Claude Haiku" />
        <InfoRow label="Modell Anschreiben" value="Claude Sonnet" />
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, borderBottom: '1px solid #1a1a1e', paddingBottom: 8 }}>
      <span style={{ color: '#666' }}>{label}</span>
      <span style={{ color: '#aaa', fontWeight: 500 }}>{value}</span>
    </div>
  )
}
