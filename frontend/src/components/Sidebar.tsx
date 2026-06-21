import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useApp } from '@/context/AppContext'
import { profileColor, profileInitials } from '@/lib/profileColor'
import { api } from '@/lib/api'

function SidebarIcon({ children }: { children: React.ReactNode }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  )
}

const AnalyseIcon = () => (
  <SidebarIcon>
    <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
  </SidebarIcon>
)

const VerlaufIcon = () => (
  <SidebarIcon>
    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
  </SidebarIcon>
)

const GearIcon = () => (
  <SidebarIcon>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </SidebarIcon>
)

const LogoIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <rect x="3" y="3" width="8" height="18" rx="1.5" fill="#041510" stroke="#059669" strokeWidth="1.4" />
    <rect x="13" y="3" width="8" height="8" rx="1.5" fill="#041510" stroke="#059669" strokeWidth="1.4" />
    <rect x="13" y="13" width="8" height="8" rx="1.5" fill="#059669" opacity=".25" stroke="#059669" strokeWidth="1.4" />
    <line x1="6" y1="7" x2="8" y2="7" stroke="#059669" strokeWidth="1.2" strokeLinecap="round" />
    <line x1="6" y1="10" x2="8" y2="10" stroke="#059669" strokeWidth="1.2" strokeLinecap="round" />
    <line x1="6" y1="13" x2="8" y2="13" stroke="#059669" strokeWidth="1.2" strokeLinecap="round" />
  </svg>
)

interface NavItemProps {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
}

function NavItem({ icon, label, active }: NavItemProps & { onClick: () => void }) {
  return (
    <div
      className="sb-item"
      style={{
        display: 'flex',
        alignItems: 'center',
        width: '100%',
        height: 40,
        borderRadius: 8,
        cursor: 'pointer',
        background: active ? 'rgba(5,150,105,.12)' : 'transparent',
        color: active ? '#059669' : '#666',
        position: 'relative',
        transition: 'background .15s',
      }}
    >
      {/* Fixed-width icon container — always visible, never displaced by label */}
      <span style={{ width: 32, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </span>
      {/* Label collapses to zero width so it can't push the icon off-screen */}
      <span
        className="sb-label"
        style={{
          fontSize: 13,
          fontWeight: active ? 600 : 400,
          color: active ? '#059669' : '#888',
          whiteSpace: 'nowrap',
          transition: 'opacity .15s, max-width .2s',
          pointerEvents: 'none',
        }}
      >
        {label}
      </span>
      {active && (
        <span style={{
          position: 'absolute',
          left: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          width: 3,
          height: 20,
          background: '#059669',
          borderRadius: '0 3px 3px 0',
        }} />
      )}
    </div>
  )
}

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { activeProfileId, openProfileSlider } = useApp()
  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: api.profiles.list })

  const activePro = profiles.find((p) => p.id === activeProfileId) ?? profiles[0] ?? null
  const color = activePro ? profileColor(activePro.id) : '#555'
  const initials = activePro ? profileInitials(activePro) : '?'

  const navItems = [
    { path: '/', label: 'Analysieren', icon: <AnalyseIcon /> },
    { path: '/verlauf', label: 'Verlauf', icon: <VerlaufIcon /> },
  ]

  return (
    <div
      className="sb-group"
      style={{
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 50,
        width: 44,
        overflow: 'visible',
      }}
    >
      <div
        className="sb-inner"
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          background: '#080810',
          borderRight: '1px solid #1a1a20',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'stretch',
          paddingTop: 10,
          paddingBottom: 10,
          overflow: 'hidden',
          transition: 'width .2s ease, box-shadow .2s ease',
        }}
      >
        {/* Logo */}
        <div
          onClick={() => navigate('/')}
          style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 44, marginBottom: 12, flexShrink: 0, cursor: 'pointer' }}
        >
          <LogoIcon />
        </div>

        {/* Nav items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '0 6px', flex: 1 }}>
          {navItems.map(({ path, label, icon }) => (
            <div key={path} onClick={() => navigate(path)} style={{ cursor: 'pointer' }}>
              <NavItem
                icon={icon}
                label={label}
                active={path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)}
                onClick={() => navigate(path)}
              />
            </div>
          ))}
        </div>

        {/* Bottom: gear + profile avatar */}
        <div style={{ padding: '0 6px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div onClick={() => navigate('/einstellungen')} style={{ cursor: 'pointer' }}>
            <NavItem
              icon={<GearIcon />}
              label="Einstellungen"
              active={location.pathname === '/einstellungen'}
              onClick={() => navigate('/einstellungen')}
            />
          </div>

          {/* Profile avatar */}
          <div
            className="sb-item"
            onClick={openProfileSlider}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              height: 40,
              marginTop: 4,
              cursor: 'pointer',
              padding: '0 3px',
              borderRadius: 8,
            }}
          >
            <div
              style={{
                width: 30,
                height: 30,
                borderRadius: '50%',
                background: `${color}22`,
                border: `2px solid ${color}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 700,
                color,
                flexShrink: 0,
              }}
            >
              {initials}
            </div>
            <span
              className="sb-label"
              style={{ fontSize: 12, color: '#888', whiteSpace: 'nowrap', transition: 'opacity .15s, max-width .2s' }}
            >
              {activePro?.display_name ?? 'Profil wählen'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
