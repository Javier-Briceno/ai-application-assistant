import { createContext, useContext, useState } from 'react'
import { cn } from '@/lib/utils'

const TabsContext = createContext<{ active: string; set: (v: string) => void }>({
  active: '', set: () => {},
})

export function Tabs({
  defaultValue,
  children,
  className,
}: {
  defaultValue: string
  children: React.ReactNode
  className?: string
}) {
  const [active, set] = useState(defaultValue)
  return (
    <TabsContext.Provider value={{ active, set }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabsList({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex gap-1 border-b border-white/10 mb-4', className)}>
      {children}
    </div>
  )
}

export function Tab({ value, children }: { value: string; children: React.ReactNode }) {
  const { active, set } = useContext(TabsContext)
  return (
    <button
      onClick={() => set(value)}
      className={cn(
        'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
        active === value
          ? 'border-blue-500 text-white'
          : 'border-transparent text-gray-400 hover:text-gray-200'
      )}
    >
      {children}
    </button>
  )
}

export function TabPanel({ value, children }: { value: string; children: React.ReactNode }) {
  const { active } = useContext(TabsContext)
  if (active !== value) return null
  return <div>{children}</div>
}
