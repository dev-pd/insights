"use client"

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { ThemeCount } from "@/lib/api/types"
import { UI_DIMENSIONS } from "@/lib/constants"
import { stats as statsCopy } from "@/locales/en/stats"

interface ThemeFrequencyChartProps {
  themes: ThemeCount[]
}

const BAR_COLOR = "var(--primary)"

// Y-axis ticks generated from the configured max + step. Pinning the
// domain keeps the chart's vertical reference stable as data grows or
// shrinks; bars don't visually rescale just because counts moved.
const Y_TICKS = Array.from(
  { length: UI_DIMENSIONS.themeChartYAxisMax / UI_DIMENSIONS.themeChartYAxisStep + 1 },
  (_, i) => i * UI_DIMENSIONS.themeChartYAxisStep,
)

export function ThemeFrequencyChart({ themes }: ThemeFrequencyChartProps) {
  if (themes.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{statsCopy.charts.themeFrequency.title}</CardTitle>
          <CardDescription>
            {statsCopy.charts.themeFrequency.subtitle}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-8 text-center">
            {statsCopy.charts.themeFrequency.emptyMessage}
          </p>
        </CardContent>
      </Card>
    )
  }

  // Themes arrive sorted desc by count. Keep that order along the X axis
  // so the leftmost bar is the most-mentioned theme.
  const data = themes.map((t) => ({ theme: t.theme, count: t.count }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>{statsCopy.charts.themeFrequency.title}</CardTitle>
        <CardDescription>
          {statsCopy.charts.themeFrequency.subtitle}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div
          style={{
            width: "100%",
            height: UI_DIMENSIONS.themeChartHeightPx,
          }}
        >
          <ResponsiveContainer>
            <BarChart
              data={data}
              margin={{ top: 8, right: 8, bottom: 56, left: 8 }}
            >
              <XAxis
                dataKey="theme"
                tick={{ fontSize: 11 }}
                stroke="var(--muted-foreground)"
                interval={0}
                angle={-35}
                textAnchor="end"
                height={56}
              />
              <YAxis
                allowDecimals={false}
                domain={[0, UI_DIMENSIONS.themeChartYAxisMax]}
                ticks={Y_TICKS}
                tick={{ fontSize: 12 }}
                stroke="var(--muted-foreground)"
                width={32}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: "0.375rem",
                  fontSize: "0.875rem",
                }}
                cursor={{ fill: "var(--muted)" }}
                formatter={(value) => [
                  value as number,
                  statsCopy.charts.themeFrequency.countLabel,
                ]}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.map((_, idx) => (
                  <Cell key={idx} fill={BAR_COLOR} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
