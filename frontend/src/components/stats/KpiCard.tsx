import { Card, CardContent } from "@/components/ui/card"

interface KpiCardProps {
  label: string
  value: string | number
  unit?: string
  hint?: string
  ref?: React.Ref<HTMLDivElement>
}

export function KpiCard({ label, value, unit, hint, ref }: KpiCardProps) {
  return (
    <Card ref={ref}>
      <CardContent className="pt-6 pb-4">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {label}
          </span>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-semibold tabular-nums">{value}</span>
            {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
          </div>
          {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
        </div>
      </CardContent>
    </Card>
  )
}
