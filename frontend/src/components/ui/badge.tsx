import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'pass' | 'caution' | 'fail' | 'default'
}

const variantClass = {
  pass: 'bg-green-500/15 text-green-400 border-green-500/30',
  caution: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  fail: 'bg-red-500/15 text-red-400 border-red-500/30',
  default: 'bg-white/10 text-gray-300 border-white/20',
}

export function Badge({ className, variant = 'default', children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variantClass[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}
