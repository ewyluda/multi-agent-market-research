import { Card } from '@/components/ui/card'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function KpiCard({ icon: Icon, label, value, trend, trendLabel, className }) {
  const isPositive = trend > 0
  const isNegative = trend < 0
  const TrendIcon = isPositive ? TrendingUp : TrendingDown

  return (
    <Card className={cn('p-4 relative overflow-hidden', className)}>
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: 'rgba(232, 134, 12, 0.1)' }}>
          <Icon className="w-4.5 h-4.5 text-[var(--primary)]" />
        </div>
        {trend !== undefined && trend !== null && (
          <div className={cn(
            'flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded',
            isPositive && 'text-[var(--success)] bg-[rgba(23,201,100,0.1)]',
            isNegative && 'text-[var(--danger)] bg-[rgba(243,18,96,0.1)]',
            !isPositive && !isNegative && 'text-[var(--muted-foreground)]'
          )}>
            {(isPositive || isNegative) && <TrendIcon className="w-3 h-3" />}
            <span>{isPositive ? '+' : ''}{typeof trend === 'number' ? trend.toFixed(1) : trend}%</span>
          </div>
        )}
      </div>
      <p className="text-xs text-[var(--muted-foreground)] mb-1">{label}</p>
      <p className="text-2xl font-semibold font-data text-[var(--text-primary)]">{value}</p>
      {trendLabel && <p className="text-[11px] text-[var(--text-muted)] mt-1">{trendLabel}</p>}
    </Card>
  )
}
