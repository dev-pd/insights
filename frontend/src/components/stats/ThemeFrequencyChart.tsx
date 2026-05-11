"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
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

const Y_TICKS = Array.from(
  { length: UI_DIMENSIONS.themeChartYAxisMax / UI_DIMENSIONS.themeChartYAxisStep + 1 },
  (_, index) => index * UI_DIMENSIONS.themeChartYAxisStep,
)

// MUST match the BarChart margins — the HTML YAxis sidecar uses these.
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

  // Preserves the desc-by-count order: leftmost bar = most-mentioned.
  const data = themes.map((themeCount) => ({
    theme: themeCount.theme,
    count: themeCount.count,
  }))

  const chartHeight = UI_DIMENSIONS.themeChartHeightPx
  const yAxisWidth = UI_DIMENSIONS.themeChartYAxisWidthPx
  const labelHeight = UI_DIMENSIONS.themeChartLabelHeightPx
  const yAxisMax = UI_DIMENSIONS.themeChartYAxisMax
  const innerWidthPx = themes.length * UI_DIMENSIONS.themeChartSlotMinPx

  // Tick V renders at fraction V/max up the plot area; geometry matches
  // the recharts plot bounds (top/bottom margins + XAxis label band).
  const plotTopPx = TOP_MARGIN_PX
  const plotBottomPx = chartHeight - BOTTOM_MARGIN_PX - labelHeight
  const plotInnerHeight = plotBottomPx - plotTopPx
  const LABEL_VERTICAL_OFFSET_PX = 7

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
          "Frozen Y axis" via HTML labels positioned to match the recharts
          plot-area pixel coordinates. The recharts chart on the right hides
          its own YAxis (width=0) but keeps the same domain + ticks so bar
          heights map to the same scale our HTML labels reference. A
          CartesianGrid with horizontal lines makes the alignment visible.

          Why HTML, not a second recharts chart: a YAxis-only BarChart with
          width=44 leaves zero plot area, and recharts won't render tick
          labels against a zero-width plot. HTML sidesteps this entirely.
        */}
        <div className="flex">
          {/* Frozen Y axis (HTML labels at computed pixel positions) */}
          <div
            style={{
              width: yAxisWidth,
              height: chartHeight,
              position: "relative",
            }}
            className="flex-shrink-0"
            aria-hidden="true"
          >
            {Y_TICKS.map((tick) => {
              const topPx =
                plotBottomPx -
                (tick / yAxisMax) * plotInnerHeight -
                LABEL_VERTICAL_OFFSET_PX
              return (
                <span
                  key={tick}
                  className="absolute text-xs text-muted-foreground tabular-nums"
                  style={{ top: `${topPx}px`, right: "8px" }}
                >
                  {tick}
                </span>
              )
            })}
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
                  <CartesianGrid
                    horizontal
                    vertical={false}
                    stroke="var(--border)"
                    strokeDasharray="3 3"
                  />
                  <YAxis
                    hide
                    domain={[0, yAxisMax]}
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
                    {data.map((_, index) => (
                      <Cell key={index} fill={BAR_COLOR} />
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
