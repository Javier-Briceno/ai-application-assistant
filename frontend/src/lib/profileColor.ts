const COLORS = ['#059669','#3b82f6','#a855f7','#f59e0b','#ef4444','#06b6d4','#ec4899','#84cc16']

export function profileColor(id: number): string {
  return COLORS[Math.abs(id) % COLORS.length]
}

export function profileInitials(p: { first_name?: string|null; last_name?: string|null; display_name?: string }): string {
  const f = p.first_name?.[0] ?? ''
  const l = p.last_name?.[0] ?? ''
  if (f || l) return (f + l).toUpperCase()
  return (p.display_name ?? '?').slice(0, 2).toUpperCase()
}
