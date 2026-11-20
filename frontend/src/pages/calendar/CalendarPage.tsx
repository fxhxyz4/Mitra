import { useState } from "react"
import { Grid, Group, ScrollArea, Stack, Text } from "@mantine/core"
import type { CalendarItem } from "@/shared/api"

import { DeadlineCalendar, useCoordinatorDashboard } from "@/features/dashboards"
import { statusMeta } from "@/shared/lib"
import { MeasureList, PageHeader, QueryError, Section, Seo } from "@/shared/ui"

export function CalendarPage() {
  const { data, isPending, error } = useCoordinatorDashboard()
  const [today] = useState(() => new Date())
  const in30 = new Date(today.getTime() + 30 * 86_400_000)
  const calendar = data?.calendar ?? []
  const soon = calendar.filter(i => i.status !== "DONE" && new Date(i.date) <= in30)
  const done = calendar.filter(i => i.status === "DONE").sort((a, b) => b.date.localeCompare(a.date))
  const missing = data?.reportReadiness.missing ?? []

  return (
    <>
      <Seo title='Контрольні строки' />
      <PageHeader
        title='Контрольні строки'
        description='Строки поточного періоду за всіма заходами програми'
      />
      <QueryError error={error} />
      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, xl: 9 }}>
          <Section
            title='Календар'
            loading={isPending}
            skeletonHeight={700}
            actions={
              <Group
                gap='sm'
                visibleFrom='sm'
              >
                {(
                  [
                    "IN_PROGRESS",
                    "ON_REVIEW",
                    "RETURNED",
                    "DONE",
                  ] as const
                ).map(s => (
                  <LegendItem
                    key={s}
                    color={statusMeta[s].color}
                    label={statusMeta[s].label}
                  />
                ))}
                <LegendItem
                  color='danger'
                  label='Прострочено'
                />
              </Group>
            }
          >
            {data && (
              <DeadlineCalendar
                items={data.calendar}
                initial={today}
              />
            )}
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, xl: 3 }}>
          <Stack gap='lg'>
            <Section
              title={`Найближчі строки${soon.length ? ` · ${soon.length}` : ""}`}
              loading={isPending}
            >
              <DeadlineList
                items={soon}
                empty='Найближчих строків немає'
              />
            </Section>
            <Section
              title={`Виконані${done.length ? ` · ${done.length}` : ""}`}
              loading={isPending}
            >
              <DeadlineList
                items={done}
                empty='Виконаних заходів ще немає'
              />
            </Section>
          </Stack>
        </Grid.Col>
        <Grid.Col span={12}>
          <Section
            title='Ще не готові до звіту за півріччя'
            loading={isPending}
            padding={0}
          >
            <MeasureList
              items={missing}
              empty='Усі заходи готові до звіту'
            />
          </Section>
        </Grid.Col>
      </Grid>
    </>
  )
}

function DeadlineList({ items, empty }: { items: CalendarItem[]; empty: string }) {
  if (!items.length)
    return (
      <Text
        size='sm'
        c='dimmed'
      >
        {empty}
      </Text>
    )
  return (
    <ScrollArea.Autosize
      mah={320}
      type='auto'
      offsetScrollbars
    >
      <Stack gap='xs'>
        {items.map(i => (
          <Text
            key={i.measureId}
            size='sm'
            c={i.isOverdue && i.status !== "DONE" ? "danger" : undefined}
            lineClamp={2}
          >
            <b>{new Date(i.date).toLocaleDateString("uk-UA")}</b> · {i.code} {i.title}
          </Text>
        ))}
      </Stack>
    </ScrollArea.Autosize>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <Group
      gap={6}
      wrap='nowrap'
    >
      <span
        aria-hidden
        style={{ width: 8, height: 8, borderRadius: "50%", background: `var(--mantine-color-${color}-filled)` }}
      />
      <Text size='xs'>{label}</Text>
    </Group>
  )
}
