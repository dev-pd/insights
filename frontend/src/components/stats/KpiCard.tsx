import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export type KpiTrend = "up" | "down" | "flat"

interface KpiCardProps {
  label: string
  value: string | number
  unit?: string
  hint?: string
  trend?: KpiTrend | null
  ref?: React.Ref<HTMLDivElement>
}

// Unicode arrows (typography codepoints, not emojis) — render at the font's
// glyph size so they sit on the baseline next to the value.
const trendIcon: Record<KpiTrend, string> = {
  up: "↑",
  down: "↓",
  flat: "→",
}

const trendColor: Record<KpiTrend, string> = {
  up: "text-emerald-600 dark:text-emerald-500",
  down: "text-rose-600 dark:text-rose-500",
  flat: "text-muted-foreground",
}

const trendLabel: Record<KpiTrend, string> = {
  up: "trending up",
  down: "trending down",
  flat: "flat",
}

export function KpiCard({
  label,
  value,
  unit,
  hint,
  trend,
  ref,
}: KpiCardProps) {
  return (
    <Card ref={ref}>
      <CardContent className="pt-4 pb-4 px-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {label}
          </span>
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-semibold tabular-nums">{value}</span>
            {unit && (
              <span className="text-xs text-muted-foreground">{unit}</span>
            )}
            {trend && (
              <span
                className={cn("text-xs font-medium", trendColor[trend])}
                aria-label={trendLabel[trend]}
              >
                {trendIcon[trend]}
              </span>
            )}
          </div>
          {hint && (
            // No truncate — let long hints wrap to a second line rather than
            // ellipsis away half the content. CSS grid aligns row heights to
            // the tallest tile, so a 2-line hint on Total Feedback doesn't
            // misalign the other 5 cards.
            <span className="text-[11px] text-muted-foreground leading-snug">
              {hint}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
