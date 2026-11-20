import { AreaChart, CompositeChart } from "@mantine/charts"

import "@mantine/charts/styles.css"

import type { FlagPoint, StatusPoint } from "@/shared/api"

import { formatDate, statusMeta, statusOrder } from "@/shared/lib"
import { EmptyState } from "@/shared/ui"

const shortDate = (iso: string) => formatDate(iso).slice(0, 5)

export function StatusTrendChart({ points }: { points: StatusPoint[] }) {
  const used = statusOrder.filter(s => points.some(p => p.counts[s]))
  if (!used.length)
    return (
      <EmptyState
        title='Немає історії статусів'
        text='Тренд зʼявиться після перших змін статусів заходів'
      />
    )
  const data = points.map(p => ({
    week: shortDate(p.date),
    ...Object.fromEntries(used.map(s => [statusMeta[s].label, p.counts[s] ?? 0])),
  }))
  return (
    <AreaChart
      h={300}
      data={data}
      dataKey='week'
      type='stacked'
      withLegend
      legendProps={{ verticalAlign: "bottom" }}
      curveType='monotone'
      fillOpacity={0.55}
      series={used.map(s => ({ name: statusMeta[s].label, color: `${statusMeta[s].color}.6` }))}
      xAxisProps={{ interval: "preserveStartEnd" }}
    />
  )
}

export function FlagTrendChart({ points }: { points: FlagPoint[] }) {
  if (!points.some(p => p.opened || p.resolved || p.open))
    return (
      <EmptyState
        title='Risk Flags не відкривались'
        text='За обраний період правила не спрацьовували'
      />
    )
  const data = points.map(p => ({
    week: shortDate(p.date),
    "Відкрито за тиждень": p.opened,
    "Знято за тиждень": p.resolved,
    "Відкритих на кінець тижня": p.open,
  }))
  return (
    <CompositeChart
      h={300}
      data={data}
      dataKey='week'
      withLegend
      legendProps={{ verticalAlign: "bottom" }}
      maxBarWidth={26}
      series={[
        { name: "Відкрито за тиждень", color: "danger.5", type: "bar" },
        { name: "Знято за тиждень", color: "success.6", type: "bar" },
        { name: "Відкритих на кінець тижня", color: "orange.6", type: "line" },
      ]}
      curveType='monotone'
      xAxisProps={{ interval: "preserveStartEnd" }}
    />
  )
}
