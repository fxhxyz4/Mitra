import { useMemo } from "react"
import { AreaChart, BarChart, DonutChart, FunnelChart, Heatmap, RadarChart } from "@mantine/charts"

import "@mantine/charts/styles.css"

import { Grid, Group, RingProgress, ScrollArea, SimpleGrid, Stack, Text } from "@mantine/core"
import { useMediaQuery } from "@mantine/hooks"
import type { MeasureStatus, PerformanceReport } from "@/shared/api"

import { formatDate, isoDate, statusMeta, statusOrder } from "@/shared/lib"
import { ChartCard, EmptyState } from "@/shared/ui"

const primary = (pct: number) => `color-mix(in srgb, var(--mantine-primary-color-filled) ${pct}%, transparent)`
const PRIMARY = "var(--mantine-primary-color-filled)"

const short = (s: string, n = 24) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)

const weekStart = (iso: string) => {
  const d = new Date(iso)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7))
  return isoDate(d)
}

type Props = { report: PerformanceReport | undefined; loading: boolean }

export function AuditCharts({ report, loading }: Props) {
  const narrow = useMediaQuery("(max-width: 30em)")
  const statuses = useMemo(() => {
    const counts = new Map<MeasureStatus, number>()
    for (const t of report?.tasks ?? []) counts.set(t.status, (counts.get(t.status) ?? 0) + 1)
    return statusOrder
      .filter(s => counts.get(s))
      .map(s => ({ name: statusMeta[s].label, value: counts.get(s)!, color: `${statusMeta[s].color}.6` }))
  }, [report])

  const units = useMemo(
    () =>
      (report?.units ?? [])
        .filter(u => u.tasks)
        .sort((a, b) => a.name.localeCompare(b.name, "uk"))
        .map(u => ({
          unit: short(u.name, narrow ? 16 : 26),
          Вчасно: u.onTime,
          "Із запізненням": u.lateDone,
          "В роботі": u.inWork + u.onReview,
          Прострочено: u.overdue,
        })),
    [report, narrow]
  )

  const weekly = useMemo(() => {
    const byWeek = new Map<string, { submitted: number; approved: number; returned: number }>()
    for (const e of report?.events ?? []) {
      const w = weekStart(e.at)
      const row = byWeek.get(w) ?? { submitted: 0, approved: 0, returned: 0 }
      row[e.kind] += 1
      byWeek.set(w, row)
    }
    return [...byWeek.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-16)
      .map(([w, r]) => ({
        week: formatDate(w).slice(0, 5),
        Подання: r.submitted,
        Погоджено: r.approved,
        Повернено: r.returned,
      }))
  }, [report])

  const sections = useMemo(() => {
    const by = new Map<number, { total: number; done: number; onTime: number; overdue: number }>()
    for (const t of report?.tasks ?? []) {
      const s = by.get(t.section) ?? { total: 0, done: 0, onTime: 0, overdue: 0 }
      s.total += 1
      if (t.status === "DONE" || t.status === "PARTIAL") s.done += 1
      if (t.onTime) s.onTime += 1
      if (t.overdue) s.overdue += 1
      by.set(t.section, s)
    }
    return [...by.entries()]
      .sort(([a], [b]) => a - b)
      .map(([n, s]) => ({
        section: `Розділ ${n}`,
        "Виконано, %": Math.round((100 * s.done) / s.total),
        "Вчасно, %": Math.round((100 * s.onTime) / s.total),
        "Без прострочень, %": Math.round((100 * (s.total - s.overdue)) / s.total),
      }))
  }, [report])

  const total = report?.tasks.length ?? 0
  const unitsHeight = Math.max(220, units.length * 34 + 60)

  const heat = useMemo(() => {
    const data: Record<string, number> = {}
    for (const e of report?.events ?? []) {
      const d = e.at.slice(0, 10)
      data[d] = (data[d] ?? 0) + 1
    }
    const end = report ? new Date(report.asOf) : new Date()
    const start = new Date(end)
    start.setDate(start.getDate() - (narrow ? 12 : 26) * 7)
    return { data, start: isoDate(start), end: isoDate(end), max: Math.max(1, ...Object.values(data)) }
  }, [report, narrow])

  const funnel = useMemo(() => {
    const tasks = report?.tasks ?? []
    const submitted = tasks.filter(t => t.submissions > 0).length
    const done = tasks.filter(t => t.status === "DONE" || t.status === "PARTIAL").length
    const onTime = tasks.filter(t => t.onTime).length
    return [
      { name: "Завдань", value: tasks.length, color: primary(35) },
      { name: "Подано результат", value: submitted, color: primary(60) },
      { name: "Погоджено", value: done, color: primary(85) },
      { name: "Вчасно", value: onTime, color: "success.6" },
    ]
  }, [report])

  const delays = useMemo(() => {
    const labels = [
      "Вчасно",
      "1–7 дн.",
      "8–30 дн.",
      "31–90 дн.",
      "> 90 дн.",
    ]
    const counts = [
      0,
      0,
      0,
      0,
      0,
    ]
    for (const t of report?.tasks ?? []) {
      const d = t.delayDays ?? 0
      const i = t.onTime ? 0 : d <= 0 ? -1 : d <= 7 ? 1 : d <= 30 ? 2 : d <= 90 ? 3 : 4
      if (i >= 0) counts[i] = (counts[i] ?? 0) + 1
    }
    return labels.map((range, i) => ({
      range,
      Вчасно: i === 0 ? counts[i] : 0,
      "Із запізненням": i === 0 ? 0 : counts[i],
    }))
  }, [report])

  const t = report?.totals
  const rings = t
    ? [
        { label: "Виконано", value: t.donePercent, color: PRIMARY },
        { label: "Вчасно", value: t.onTimePercent, color: "success.6" },
        { label: "З першого разу", value: t.firstPassPercent, color: "teal.5" },
        { label: "Без прострочень", value: t.tasks ? (100 * (t.tasks - t.overdue)) / t.tasks : 0, color: "orange.5" },
      ]
    : []

  return (
    <Grid gap='lg'>
      <Grid.Col span={{ base: 12, md: 5, lg: 4 }}>
        <ChartCard
          title='Стан заходів'
          subtitle='Розподіл завдань у зрізі за статусом'
          loading={loading}
        >
          {statuses.length ? (
            <Stack
              align='center'
              gap='md'
            >
              <DonutChart
                data={statuses}
                size={narrow ? 160 : 190}
                thickness={26}
                paddingAngle={2}
                chartLabel={total}
                tooltipDataSource='segment'
                withTooltip
              />
              <Group
                gap='xs'
                justify='center'
              >
                {statuses.map(s => (
                  <Group
                    key={s.name}
                    gap={6}
                    wrap='nowrap'
                  >
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 3,
                        background: `var(--mantine-color-${s.color.replace(".", "-")})`,
                      }}
                    />
                    <Text size='xs'>
                      {s.name} · {s.value}
                    </Text>
                  </Group>
                ))}
              </Group>
            </Stack>
          ) : (
            <EmptyState title='Немає завдань у зрізі' />
          )}
        </ChartCard>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 7, lg: 8 }}>
        <ChartCard
          title='Активність по тижнях'
          subtitle='Подання результатів, погодження і повернення на доопрацювання'
          loading={loading}
        >
          {weekly.length ? (
            <AreaChart
              h={280}
              data={weekly}
              dataKey='week'
              curveType='monotone'
              withLegend
              legendProps={{ verticalAlign: "bottom" }}
              fillOpacity={0.35}
              withGradient
              series={[
                { name: "Подання", color: PRIMARY },
                { name: "Погоджено", color: "success.6" },
                { name: "Повернено", color: "orange.6" },
              ]}
              xAxisProps={{ interval: "preserveStartEnd" }}
            />
          ) : (
            <EmptyState title='Подій у зрізі немає' />
          )}
        </ChartCard>
      </Grid.Col>

      <Grid.Col span={{ base: 12, lg: 8 }}>
        <ChartCard
          title='Виконання за підрозділами'
          height={unitsHeight}
          subtitle='Підрозділи за алфавітом, без рейтингування'
          loading={loading}
        >
          {units.length ? (
            <BarChart
              h={unitsHeight}
              data={units}
              dataKey='unit'
              type='stacked'
              orientation='vertical'
              yAxisProps={{ width: narrow ? 96 : 170 }}
              withLegend
              legendProps={{ verticalAlign: "bottom" }}
              maxBarWidth={22}
              series={[
                { name: "Вчасно", color: "success.6" },
                { name: "Із запізненням", color: "teal.4" },
                { name: "В роботі", color: primary(55) },
                { name: "Прострочено", color: "danger.6" },
              ]}
            />
          ) : (
            <EmptyState title='Підрозділів у зрізі немає' />
          )}
        </ChartCard>
      </Grid.Col>

      <Grid.Col span={{ base: 12, lg: 4 }}>
        <ChartCard
          title='Розділи програми'
          height={300}
          subtitle='Частка виконаних, вчасних і без прострочень'
          loading={loading}
        >
          {sections.length > 2 ? (
            <RadarChart
              h={300}
              data={sections}
              dataKey='section'
              withPolarRadiusAxis={false}
              radarChartProps={{ outerRadius: narrow ? "58%" : "72%" }}
              withLegend
              withTooltip
              series={[
                { name: "Без прострочень, %", color: "teal.5", opacity: 0.15 },
                { name: "Виконано, %", color: PRIMARY, opacity: 0.25 },
                { name: "Вчасно, %", color: "success.6", opacity: 0.2 },
              ]}
            />
          ) : sections.length ? (
            <BarChart
              h={300}
              data={sections}
              dataKey='section'
              withLegend
              legendProps={{ verticalAlign: "bottom" }}
              yAxisProps={{ domain: [0, 100] }}
              series={[
                { name: "Виконано, %", color: PRIMARY },
                { name: "Вчасно, %", color: "success.6" },
              ]}
            />
          ) : (
            <EmptyState title='Немає даних' />
          )}
        </ChartCard>
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 8 }}>
        <ChartCard
          title='Календар активності'
          height={200}
          subtitle='Скільки подань, погоджень і повернень було щодня'
          loading={loading}
        >
          <ScrollArea
            type='auto'
            offsetScrollbars
          >
            <Heatmap
              data={heat.data}
              startDate={heat.start}
              endDate={heat.end}
              domain={[0, heat.max]}
              firstDayOfWeek={1}
              withMonthLabels
              withWeekdayLabels
              withTooltip
              withLegend
              legendLabels={["Менше", "Більше"]}
              rectSize={narrow ? 13 : 17}
              gap={3}
              rectRadius={3}
              monthLabels={[
                "Січ",
                "Лют",
                "Бер",
                "Кві",
                "Тра",
                "Чер",
                "Лип",
                "Сер",
                "Вер",
                "Жов",
                "Лис",
                "Гру",
              ]}
              weekdayLabels={[
                "",
                "Пн",
                "",
                "Ср",
                "",
                "Пт",
                "",
              ]}
              colors={[
                primary(14),
                primary(38),
                primary(66),
                PRIMARY,
              ]}
              getTooltipLabel={({ date, value }) =>
                `${formatDate(date)} — ${value ? `${value} ${value === 1 ? "подія" : value < 5 ? "події" : "подій"}` : "без подій"}`
              }
            />
          </ScrollArea>
        </ChartCard>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6, lg: 4 }}>
        <ChartCard
          title='Воронка виконання'
          height={230}
          subtitle='Від завдання до погодженого вчасно'
          loading={loading}
        >
          {total ? (
            <Group
              justify='center'
              wrap='nowrap'
            >
              <FunnelChart
                data={funnel}
                size={narrow ? 190 : 230}
                withLabels
                labelsPosition='right'
                withTooltip
                tooltipDataSource='segment'
              />
            </Group>
          ) : (
            <EmptyState title='Немає завдань у зрізі' />
          )}
        </ChartCard>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <ChartCard
          title='Запізнення виконання'
          height={260}
          subtitle='Наскільки пізніше строку погоджено результат'
          loading={loading}
        >
          <BarChart
            h={260}
            data={delays}
            dataKey='range'
            type='stacked'
            series={[
              { name: "Вчасно", color: "success.6" },
              { name: "Із запізненням", color: "orange.6" },
            ]}
            maxBarWidth={48}
          />
        </ChartCard>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        <ChartCard
          title='Ключові показники'
          height={330}
          subtitle='Частки від усіх завдань у зрізі'
          loading={loading}
        >
          <SimpleGrid
            cols={2}
            spacing='lg'
            verticalSpacing='lg'
          >
            {rings.map(r => (
              <Stack
                key={r.label}
                gap={4}
                align='center'
              >
                <RingProgress
                  size={narrow ? 104 : 120}
                  thickness={narrow ? 10 : 12}
                  roundCaps
                  sections={[{ value: Math.max(0, Math.min(100, r.value)), color: r.color }]}
                  label={
                    <Text
                      ta='center'
                      fw={700}
                      size={narrow ? "md" : "lg"}
                    >
                      {Math.round(r.value)}%
                    </Text>
                  }
                />
                <Text
                  size='sm'
                  c='dimmed'
                  ta='center'
                >
                  {r.label}
                </Text>
              </Stack>
            ))}
          </SimpleGrid>
        </ChartCard>
      </Grid.Col>
    </Grid>
  )
}
