import { useState } from "react"
import { BarChart, LineChart } from "@mantine/charts"

import "@mantine/charts/styles.css"

import { Grid, Group, SegmentedControl, SimpleGrid, Stack, Text } from "@mantine/core"
import { useMediaQuery } from "@mantine/hooks"
import type { AnalyticsOverview, FlagType } from "@/shared/api"

import { flagMeta, flagOrder, formatDate, toNumber } from "@/shared/lib"
import { Deferred, EmptyState, QueryError, Section } from "@/shared/ui"
import { useAnalyticsOverview } from "../../api"
import { FlagTrendChart, StatusTrendChart } from "../TrendCharts"

const weekOptions = [
  { value: "4", label: "4 тиж." },
  { value: "12", label: "12 тиж." },
  { value: "26", label: "26 тиж." },
]

const indicatorsOf = (data: AnalyticsOverview | undefined) =>
  (data?.risks ?? []).flatMap(r => r.indicators.map(i => ({ ...i, riskCode: r.code })))

/** Тренди програми (лише для аналітика — ендпоінт /analytics/overview): стан заходів, Risk Flags, ризики. */
export function DynamicsCharts({ programId }: { programId?: string | null }) {
  const [weeks, setWeeks] = useState("12")
  const narrow = useMediaQuery("(max-width: 30em)")
  const { data, isPending, error } = useAnalyticsOverview(Number(weeks), programId)
  const beforeAfter = indicatorsOf(data).map(i => ({
    name: `${i.riskCode} · ${i.name.length > 28 ? `${i.name.slice(0, 28)}…` : i.name}`,
    База: toNumber(i.baseline),
    Зараз: toNumber(i.current ?? i.baseline),
    Ціль: toNumber(i.target),
  }))
  const flags = flagOrder
    .filter(t => t !== "TARGET_MISSED")
    .map(t => ({ type: flagMeta[t].label, count: data?.flagsByType[t as FlagType] ?? 0 }))

  return (
    <Stack gap='lg'>
      <QueryError error={error} />
      <Group
        justify='space-between'
        gap='sm'
      >
        <div>
          <Text fw={700}>Динаміка програми</Text>
          <Text
            size='sm'
            c='dimmed'
          >
            Як змінювались стан заходів, Risk Flags і ризики
          </Text>
        </div>
        <SegmentedControl
          size='xs'
          value={weeks}
          onChange={setWeeks}
          data={weekOptions}
          aria-label='Період трендів'
        />
      </Group>
      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Section
            title='Стан заходів на кінець тижня'
            subtitle={data ? `станом на ${formatDate(data.asOf)}` : undefined}
            loading={isPending}
          >
            {data && (
              <Deferred height={300}>
                <StatusTrendChart points={data.statusTrend} />
              </Deferred>
            )}
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Section
            title='Risk Flags: відкрито і знято'
            subtitle='стовпці — за тиждень, лінія — відкриті на кінець тижня'
            loading={isPending}
          >
            {data && (
              <Deferred height={300}>
                <FlagTrendChart points={data.flagTrend} />
              </Deferred>
            )}
          </Section>
        </Grid.Col>
      </Grid>

      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Section
            title='Ризики: база → зараз → ціль'
            subtitle='За кожним індикатором зменшення ризику'
            loading={isPending}
          >
            {beforeAfter.length ? (
              <Deferred height={300}>
                <BarChart
                  h={300}
                  data={beforeAfter}
                  dataKey='name'
                  withLegend
                  series={[
                    { name: "База", color: "gray.5" },
                    { name: "Зараз", color: "brand.6" },
                    { name: "Ціль", color: "success.6" },
                  ]}
                  tickLine='y'
                />
              </Deferred>
            ) : (
              <EmptyState title='Індикаторів немає' />
            )}
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Section
            title='Відкриті Risk Flags за типами'
            loading={isPending}
          >
            <Deferred height={300}>
              <BarChart
                h={300}
                data={flags}
                dataKey='type'
                orientation='vertical'
                yAxisProps={{ width: narrow ? 104 : 170 }}
                series={[{ name: "count", label: "Прапорців", color: "orange.6" }]}
              />
            </Deferred>
          </Section>
        </Grid.Col>
      </Grid>
    </Stack>
  )
}

/** Історія вимірювань кожного індикатора ризику. */
export function IndicatorsTab({ programId }: { programId?: string | null }) {
  const { data, isPending, error } = useAnalyticsOverview(12, programId)
  const indicators = indicatorsOf(data)

  return (
    <Stack gap='lg'>
      <QueryError error={error} />
      <Section
        title='Динаміка індикаторів'
        subtitle='Історія вимірювань; пунктир — цільове значення'
        loading={isPending}
      >
        <SimpleGrid
          cols={{ base: 1, md: 2 }}
          spacing='lg'
        >
          {indicators.map(i => (
            <Stack
              key={i.id}
              gap={4}
            >
              <Group justify='space-between'>
                <Text
                  size='sm'
                  fw={600}
                >
                  {i.riskCode} · {i.name}
                </Text>
                <Text
                  size='xs'
                  c='dimmed'
                >
                  {i.unit}
                </Text>
              </Group>
              <LineChart
                h={180}
                data={[...i.values]
                  .sort((a, b) => a.date.localeCompare(b.date))
                  .map(v => ({ date: formatDate(v.date), value: toNumber(v.value) }))}
                dataKey='date'
                series={[{ name: "value", label: i.name, color: i.isImproved ? "success.6" : "danger.6" }]}
                referenceLines={[
                  { y: toNumber(i.target) ?? 0, label: "Ціль", color: "success.4", strokeDasharray: "4 4" },
                ]}
                curveType='monotone'
                withDots
              />
            </Stack>
          ))}
        </SimpleGrid>
      </Section>
    </Stack>
  )
}
