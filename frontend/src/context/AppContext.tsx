import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import type { PipelineResult } from '@/types'

interface Toast {
  id: number
  message: string
}

interface AppCtx {
  activeProfileId: number | null
  setActiveProfileId: (id: number | null) => void
  profileSliderOpen: boolean
  openProfileSlider: () => void
  closeProfileSlider: () => void
  toasts: Toast[]
  showToast: (message: string) => void
  analyzeResult: PipelineResult | null
  setAnalyzeResult: (r: PipelineResult | null) => void
  analyzePosting: string
  setAnalyzePosting: (s: string) => void
  analyzing: boolean
  setAnalyzing: (v: boolean) => void
  stepMsg: string
  setStepMsg: (s: string) => void
  analyzeError: string | null
  setAnalyzeError: (s: string | null) => void
}

const Ctx = createContext<AppCtx | null>(null)

let nextId = 0

export function AppProvider({ children }: { children: ReactNode }) {
  const [activeProfileId, setActiveProfileId] = useState<number | null>(null)
  const [profileSliderOpen, setProfileSliderOpen] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [analyzeResult, setAnalyzeResult] = useState<PipelineResult | null>(null)
  const [analyzePosting, setAnalyzePosting] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [stepMsg, setStepMsg] = useState('')
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)

  const openProfileSlider = useCallback(() => setProfileSliderOpen(true), [])
  const closeProfileSlider = useCallback(() => setProfileSliderOpen(false), [])

  const showToast = useCallback((message: string) => {
    const id = ++nextId
    setToasts((prev) => [...prev, { id, message }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 2800)
  }, [])

  return (
    <Ctx.Provider value={{
      activeProfileId, setActiveProfileId,
      profileSliderOpen, openProfileSlider, closeProfileSlider,
      toasts, showToast,
      analyzeResult, setAnalyzeResult,
      analyzePosting, setAnalyzePosting,
      analyzing, setAnalyzing,
      stepMsg, setStepMsg,
      analyzeError, setAnalyzeError,
    }}>
      {children}
    </Ctx.Provider>
  )
}

export function useApp(): AppCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp must be inside AppProvider')
  return ctx
}
