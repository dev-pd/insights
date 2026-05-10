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

// Shared chart geometry. Both the frozen-Y chart and the scrollable
// bars chart use the same top + bottom margin AND the same XAxis band
// height so their plot areas line up pixel-for-pixel. If you change one,
// change the other.
const TOP_MARGIN_PX = 8
const BOTTOM_MARGIN_PX = 8

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

  const chartHeight = UI_DIMENSIONS.themeChartHeightPx
  const yAxisWidth = UI_DIMENSIONS.themeChartYAxisWidthPx
  const labelHeight = UI_DIMENSIONS.themeChartLabelHeightPx
  const innerWidthPx = themes.length * UI_DIMENSIONS.themeChartSlotMinPx

  return (
    <Card>
      <CardHeader>
        <CardTitle>{statsCopy.charts.themeFrequency.title}</CardTitle>
        <CardDescription>
          {statsCopy.charts.themeFrequency.subtitle}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/*
          Dual-chart "frozen Y axis" pattern. recharts has no native
          frozen-axis support, so we render two BarChart instances side by
          side: a fixed-width left chart that only shows the Y axis (zero
          plot area) and a scrollable right chart with the bars + X axis.

          For the Y labels to line up with the right chart's bars, both
          MUST share: domain, ticks, top + bottom margin, and XAxis band
          height. Diverge any of those and the alignment drifts.
        */}
        <div className="flex">
          {/* Frozen Y axis */}
          <div
            style={{ width: yAxisWidth, height: chartHeight }}
            className="flex-shrink-0"
            aria-hidden="true"
          >
            <ResponsiveContainer>
              <BarChart
                data={data}
                margin={{
                  top: TOP_MARGIN_PX,
                  right: 0,
                  bottom: BOTTOM_MARGIN_PX,
                  left: 0,
                }}
              >
                <YAxis
                  allowDecimals={false}
                  domain={[0, UI_DIMENSIONS.themeChartYAxisMax]}
                  ticks={Y_TICKS}
                  tick={{ fontSize: 12 }}
                  stroke="var(--muted-foreground)"
                  width={yAxisWidth}
                />
                {/* Same XAxis height as the scrolling chart, hidden so it
                    just reserves vertical space for alignment. */}
                <XAxis dataKey="theme" hide height={labelHeight} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Scrollable bars + X axis */}
          <div className="flex-1 overflow-x-auto">
            <div
              style={{
                width: `${innerWidthPx}px`,
                minWidth: "100%",
                height: chartHeight,
              }}
            >
              <ResponsiveContainer>
                <BarChart
                  data={data}
                  margin={{
                    top: TOP_MARGIN_PX,
                    right: 8,
                    bottom: BOTTOM_MARGIN_PX,
                    left: 0,
                  }}
                >
                  <YAxis
                    hide
                    domain={[0, UI_DIMENSIONS.themeChartYAxisMax]}
                    ticks={Y_TICKS}
                    width={0}
                  />
                  <XAxis
                    dataKey="theme"
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                    interval={0}
                    angle={-35}
                    textAnchor="end"
                    height={labelHeight}
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
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
