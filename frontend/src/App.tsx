import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppProvider } from './context/AppContext'
import { Sidebar } from './components/Sidebar'
import { ProfileSlider } from './components/ProfileSlider'
import { ToastContainer } from './components/Toast'
import { ProfileModal } from './components/ProfileModal'
import { AnalysePage } from './pages/AnalysePage'
import { VerlaufPage } from './pages/VerlaufPage'
import { EinstellungenPage } from './pages/EinstellungenPage'
import { useQueryClient } from '@tanstack/react-query'
import { useApp } from './context/AppContext'
import type { ProfileDetail } from './types'
import { api } from './lib/api'

const qc = new QueryClient()

function AppShell() {
  const { setActiveProfileId, closeProfileSlider, showToast } = useApp()
  const queryClient = useQueryClient()
  const [editProfileDetail, setEditProfileDetail] = useState<ProfileDetail | undefined>()
  const [editOpen, setEditOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)

  const handleCreateProfile = () => {
    setCreateOpen(true)
  }

  const handleEditProfile = async (id: number) => {
    try {
      const detail = await api.profiles.get(id)
      setEditProfileDetail(detail)
      setEditOpen(true)
      closeProfileSlider()
    } catch {
      showToast('Profil konnte nicht geladen werden')
    }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar />

      {/* Main content — offset by sidebar width */}
      <div style={{ flex: 1, marginLeft: 44, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <Routes>
          <Route path="/" element={<AnalysePage />} />
          <Route path="/verlauf" element={<VerlaufPage />} />
          <Route path="/einstellungen" element={<EinstellungenPage />} />
        </Routes>
      </div>

      <ProfileSlider
        onCreateProfile={handleCreateProfile}
        onEditProfile={handleEditProfile}
      />

      <ProfileModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSaved={(id) => {
          queryClient.invalidateQueries({ queryKey: ['profiles'] })
          setActiveProfileId(id)
          setCreateOpen(false)
          showToast('Profil erstellt')
        }}
      />

      <ProfileModal
        open={editOpen}
        onClose={() => { setEditOpen(false); setEditProfileDetail(undefined) }}
        onSaved={() => {
          queryClient.invalidateQueries({ queryKey: ['profiles'] })
          setEditOpen(false)
          showToast('Profil aktualisiert')
        }}
        existing={editProfileDetail}
      />

      <ToastContainer />
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AppProvider>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </AppProvider>
    </QueryClientProvider>
  )
}
