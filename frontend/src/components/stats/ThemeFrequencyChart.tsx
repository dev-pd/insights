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
// Reserve enough left-axis width for long theme labels ("realtime
// collaboration", "keyboard shortcuts") to render unwrapped.
const Y_AXIS_LABEL_WIDTH_PX = 140
const ROW_HEIGHT_PX = 28
const VERTICAL_PADDING_PX = 24

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

  // Preserves desc-by-count order: top row = most-mentioned.
  const data = themes.map((themeCount) => ({
    theme: themeCount.theme,
    count: themeCount.count,
  }))

  const chartHeight = themes.length * ROW_HEIGHT_PX + VERTICAL_PADDING_PX

  return (
    <Card>
      <CardHeader>
        <CardTitle>{statsCopy.charts.themeFrequency.title}</CardTitle>
        <CardDescription>
          {statsCopy.charts.themeFrequency.subtitle}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div style={{ height: chartHeight, width: "100%" }}>
          <ResponsiveContainer>
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 4, right: 16, bottom: 4, left: 0 }}
            >
              <CartesianGrid
                horizontal={false}
                vertical
                stroke="var(--border)"
                strokeDasharray="3 3"
              />
              <XAxis
                type="number"
                domain={[0, UI_DIMENSIONS.themeChartYAxisMax]}
                ticks={[
                  0,
                  UI_DIMENSIONS.themeChartYAxisStep,
                  UI_DIMENSIONS.themeChartYAxisStep * 2,
                  UI_DIMENSIONS.themeChartYAxisStep * 3,
                  UI_DIMENSIONS.themeChartYAxisStep * 4,
                  UI_DIMENSIONS.themeChartYAxisMax,
                ]}
                tick={{ fontSize: 11 }}
                stroke="var(--muted-foreground)"
                allowDecimals={false}
              />
              <YAxis
                type="category"
                dataKey="theme"
                tick={{ fontSize: 12 }}
                stroke="var(--muted-foreground)"
                width={Y_AXIS_LABEL_WIDTH_PX}
                interval={0}
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
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {data.map((_, index) => (
                  <Cell key={index} fill={BAR_COLOR} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
