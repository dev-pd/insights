"use client"

import {
  Bar,
  BarChart,
  Legend,
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
import type { SentimentTrendPoint } from "@/lib/api/types"
import { UI_DIMENSIONS } from "@/lib/constants"
import { stats as statsCopy } from "@/locales/en/stats"

interface SentimentTrendChartProps {
  points: SentimentTrendPoint[]
}

// Sentiment colors are intentionally literal hex (not theme variables)
// so positive/neutral/negative read consistently across light + dark
// themes. Theme variables would shift the meaning of "positive green".
const COLOR_POSITIVE = "#1D9E75"
const COLOR_NEUTRAL = "#888780"
const COLOR_NEGATIVE = "#D85A30"

// Slice index 5 → keep "MM-DD" portion of "YYYY-MM-DD" for axis labels.
const ISO_DATE_MM_DD_OFFSET = 5

export function SentimentTrendChart({ points }: SentimentTrendChartProps) {
  // Hide chart when there's literally no extracted feedback in the window.
  const totalAcrossWindow = points.reduce(
    (acc, p) => acc + p.positive + p.neutral + p.negative,
    0,
  )

  if (totalAcrossWindow === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{statsCopy.charts.sentimentTrend.title}</CardTitle>
          <CardDescription>
            {statsCopy.charts.sentimentTrend.subtitle}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-8 text-center">
            {statsCopy.charts.sentimentTrend.emptyMessage}
          </p>
        </CardContent>
      </Card>
    )
  }

  const data = points.map((p) => ({
    bucket: p.bucket,
    label: p.bucket.slice(ISO_DATE_MM_DD_OFFSET),
    positive: p.positive,
    neutral: p.neutral,
    negative: p.negative,
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>{statsCopy.charts.sentimentTrend.title}</CardTitle>
        <CardDescription>
          {statsCopy.charts.sentimentTrend.subtitle}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div
          style={{
            width: "100%",
            height: UI_DIMENSIONS.sentimentTrendHeightPx,
          }}
        >
          <ResponsiveContainer>
            <BarChart
              data={data}
              margin={{ top: 8, right: 0, bottom: 0, left: 0 }}
              barCategoryGap="15%"
            >
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11 }}
                stroke="var(--muted-foreground)"
                interval="preserveStartEnd"
                tickMargin={6}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11 }}
                stroke="var(--muted-foreground)"
                width={28}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: "0.375rem",
                  fontSize: "0.875rem",
                }}
                cursor={{ fill: "var(--muted)" }}
              />
              <Legend
                wrapperStyle={{ fontSize: "0.75rem" }}
                iconType="circle"
              />
              <Bar
                dataKey="positive"
                stackId="sentiment"
                fill={COLOR_POSITIVE}
                name={statsCopy.charts.sentimentTrend.legendPositive}
              />
              <Bar
                dataKey="neutral"
                stackId="sentiment"
                fill={COLOR_NEUTRAL}
                name={statsCopy.charts.sentimentTrend.legendNeutral}
              />
              <Bar
                dataKey="negative"
                stackId="sentiment"
                fill={COLOR_NEGATIVE}
                name={statsCopy.charts.sentimentTrend.legendNegative}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
