import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useApp } from '@/context/AppContext'
import { profileColor, profileInitials } from '@/lib/profileColor'
import { api } from '@/lib/api'
import type { ProfileSummary } from '@/types'

interface Props {
  onCreateProfile: () => void
  onEditProfile: (id: number) => void
}

function Avatar({ p, size = 32 }: { p: ProfileSummary; size?: number }) {
  const color = profileColor(p.id)
  const initials = profileInitials(p)
  return (
    <div style={{
      width: size,
      height: size,
      borderRadius: '50%',
      background: `${color}22`,
      border: `2px solid ${color}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: size * 0.35,
      fontWeight: 700,
      color,
      flexShrink: 0,
    }}>
      {initials}
    </div>
  )
}

export function ProfileSlider({ onCreateProfile, onEditProfile }: Props) {
  const { profileSliderOpen, closeProfileSlider, activeProfileId, setActiveProfileId, showToast } = useApp()
  const qc = useQueryClient()
  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: api.profiles.list })
  const panelRef = useRef<HTMLDivElement>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  useEffect(() => {
    if (!profileSliderOpen) return
    function handler(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        closeProfileSlider()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [profileSliderOpen, closeProfileSlider])

  const select = (id: number) => {
    setActiveProfileId(id)
    closeProfileSlider()
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('Profil und alle zugehörigen Daten wirklich löschen?')) return
    try {
      await api.profiles.delete(id)
      qc.invalidateQueries({ queryKey: ['profiles'] })
      qc.invalidateQueries({ queryKey: ['applications'] })
      if (activeProfileId === id) setActiveProfileId(null)
      showToast('Profil gelöscht')
    } catch {
      showToast('Löschen fehlgeschlagen')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 100,
          background: profileSliderOpen ? 'rgba(0,0,0,.4)' : 'transparent',
          pointerEvents: profileSliderOpen ? 'auto' : 'none',
          transition: 'background .2s',
        }}
        onClick={closeProfileSlider}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: 260,
          background: '#0d0d12',
          borderLeft: '1px solid #1e3a1e',
          zIndex: 101,
          display: 'flex',
          flexDirection: 'column',
          transform: profileSliderOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform .25s ease',
          boxShadow: '-8px 0 32px rgba(0,0,0,.7)',
        }}
      >
        {/* Header */}
        <div style={{ padding: '18px 18px 12px', borderBottom: '1px solid #1e1e22' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#059669', textTransform: 'uppercase', letterSpacing: '.08em' }}>
            Profile
          </div>
        </div>

        {/* Profile list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
          {profiles.length === 0 && (
            <div style={{ padding: '12px 8px', fontSize: 13, color: '#555' }}>
              Noch keine Profile. Erstelle dein erstes Profil.
            </div>
          )}
          {profiles.map((p) => {
            const isActive = p.id === activeProfileId
            const color = profileColor(p.id)
            const isConfirmingDelete = deletingId === p.id
            return (
              <div
                key={p.id}
                onClick={() => !isConfirmingDelete && select(p.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 10px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: isActive ? `${color}11` : 'transparent',
                  border: `1px solid ${isActive ? color + '44' : 'transparent'}`,
                  marginBottom: 4,
                  transition: 'background .15s, border .15s',
                }}
              >
                <Avatar p={p} size={28} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: isActive ? '#e8e8ea' : '#aaa', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {p.display_name}
                  </div>
                </div>
                {isActive && (
                  <span style={{ fontSize: 11, color: '#059669', flexShrink: 0 }}>✓</span>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); onEditProfile(p.id) }}
                  style={{ background: 'none', border: 'none', color: '#444', cursor: 'pointer', fontSize: 12, padding: '2px 4px', borderRadius: 4, flexShrink: 0 }}
                  title="Bearbeiten"
                >
                  ✎
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(p.id) }}
                  style={{ background: 'none', border: 'none', color: '#3a1414', cursor: 'pointer', fontSize: 12, padding: '2px 4px', borderRadius: 4, flexShrink: 0 }}
                  title="Profil löschen"
                >
                  <TrashIcon />
                </button>
              </div>
            )
          })}
        </div>

        {/* Footer — new profile */}
        <div style={{ padding: '12px 10px', borderTop: '1px solid #1e1e22' }}>
          <button
            onClick={() => { closeProfileSlider(); onCreateProfile() }}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 10px',
              borderRadius: 8,
              border: '1px dashed #1e3a1e',
              background: 'transparent',
              color: '#059669',
              fontSize: 13,
              cursor: 'pointer',
              transition: 'background .15s, border-color .15s',
            }}
          >
            <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
            Neues Profil erstellen
          </button>
        </div>
      </div>
    </>
  )
}

function TrashIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4h6v2" />
    </svg>
  )
}
