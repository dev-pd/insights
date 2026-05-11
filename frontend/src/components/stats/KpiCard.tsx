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

// Unicode arrows (typography codepoints, not emojis) sit on the baseline
// next to the value. One config keeps icon/color/aria-label in sync.
const TREND_STYLE: Record<KpiTrend, { icon: string; color: string; label: string }> = {
  up: { icon: "↑", color: "text-emerald-600 dark:text-emerald-500", label: "trending up" },
  down: { icon: "↓", color: "text-rose-600 dark:text-rose-500", label: "trending down" },
  flat: { icon: "→", color: "text-muted-foreground", label: "flat" },
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
                className={cn("text-xs font-medium", TREND_STYLE[trend].color)}
                aria-label={TREND_STYLE[trend].label}
              >
                {TREND_STYLE[trend].icon}
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
