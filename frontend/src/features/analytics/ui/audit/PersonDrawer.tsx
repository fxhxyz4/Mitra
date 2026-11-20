import { BarChart } from "@mantine/charts"

import "@mantine/charts/styles.css"

import { Badge, Button, Drawer, Group, SimpleGrid, Stack, Tabs, Text, Timeline } from "@mantine/core"
import { IconFilter } from "@tabler/icons-react"
import type { PerformanceReport, PersonPerformance } from "@/shared/api"

import { formatDateTime, formatPeriod, roleMeta } from "@/shared/lib"
import { DataTable, EmptyState } from "@/shared/ui"
import { days, kindMeta, pct, taskColumns } from "./tables"

const monthKey = (iso: string) => iso.slice(0, 7)
const monthLabel = (key: string) => {
  const [y, m] = key.split("-")
  return `${m}.${y?.slice(2)}`
}

type Props = {
  person: PersonPerformance | null
  report: PerformanceReport | undefined
  onClose: () => void
  onFilter: (userId: string) => void
}

export function PersonDrawer({ person, report, onClose, onFilter }: Props) {
  const tasks = person && report ? report.tasks.filter(t => t.executorIds.includes(person.userId)) : []
  const events = person && report ? report.events.filter(e => e.executorId === person.userId) : []

  const months = [...new Set(events.map(e => monthKey(e.at)))].sort()
  const byMonth = months.map(m => ({
    month: monthLabel(m),
    Подання: events.filter(e => e.kind === "submitted" && monthKey(e.at) === m).length,
    Погоджено: events.filter(e => e.kind === "approved" && monthKey(e.at) === m).length,
    Повернено: events.filter(e => e.kind === "returned" && monthKey(e.at) === m).length,
  }))

  return (
    <Drawer
      opened={person !== null}
      onClose={onClose}
      position='right'
      size='xl'
      title={
        person && (
          <Stack gap={0}>
            <Group gap='xs'>
              <Text fw={700}>{person.name}</Text>
              <Badge
                variant='light'
                size='sm'
              >
                {roleMeta[person.role].label}
              </Badge>
              {!person.active && (
                <Badge
                  color='gray'
                  size='sm'
                >
                  видалено
                </Badge>
              )}
            </Group>
            <Text
              size='sm'
              c='dimmed'
            >
              {person.orgUnit}
              {report?.period ? ` · ${formatPeriod(report.period)}` : " · усі півріччя"}
            </Text>
          </Stack>
        )
      }
    >
      {person && (
        <Stack gap='lg'>
          <SimpleGrid
            cols={{ base: 2, sm: 4 }}
            spacing='sm'
          >
            <Stat
              label='Завдань'
              value={person.tasks}
            />
            <Stat
              label='Виконано'
              value={`${person.done} (${pct(person.donePercent)})`}
            />
            <Stat
              label='Вчасно'
              value={person.done ? pct(person.onTimePercent) : "—"}
            />
            <Stat
              label='Прострочено'
              value={person.overdue}
              bad={person.overdue > 0}
            />
            <Stat
              label='Подань'
              value={person.submissions}
            />
            <Stat
              label='Повернень'
              value={`${person.returns}${person.decisions ? ` (${pct(person.returnRate)})` : ""}`}
              bad={person.returns > 0}
            />
            <Stat
              label='З першого разу'
              value={pct(person.firstPassPercent)}
            />
            <Stat
              label='Сер. запізнення'
              value={days(person.avgDelayDays)}
              bad={Boolean(person.avgDelayDays)}
            />
          </SimpleGrid>
          <Group justify='space-between'>
            <Text
              size='xs'
              c='dimmed'
            >
              Остання дія: {person.lastActivity ? formatDateTime(person.lastActivity) : "немає"} · документів:{" "}
              {person.evidence}
            </Text>
            <Button
              size='xs'
              variant='light'
              leftSection={<IconFilter size={14} />}
              onClick={() => onFilter(person.userId)}
            >
              Показати всю аналітику лише по цій особі
            </Button>
          </Group>

          <Tabs defaultValue='timeline'>
            <Tabs.List>
              <Tabs.Tab value='timeline'>Хронологія ({events.length})</Tabs.Tab>
              <Tabs.Tab value='tasks'>Завдання ({tasks.length})</Tabs.Tab>
              <Tabs.Tab value='months'>По місяцях</Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel
              value='timeline'
              pt='md'
            >
              {events.length ? (
                <Timeline
                  bulletSize={14}
                  lineWidth={2}
                >
                  {events.map(e => (
                    <Timeline.Item
                      key={`${e.kind}-${e.at}-${e.measureId}`}
                      color={kindMeta[e.kind].color}
                      title={
                        <Group gap='xs'>
                          <Badge
                            size='xs'
                            variant='light'
                            color={kindMeta[e.kind].color}
                          >
                            {kindMeta[e.kind].label}
                            {e.round ? ` №${e.round}` : ""}
                          </Badge>
                          <Text
                            size='sm'
                            fw={500}
                          >
                            {e.code} {e.title}
                          </Text>
                        </Group>
                      }
                    >
                      <Text
                        size='xs'
                        c='dimmed'
                      >
                        {formatDateTime(e.at)} · {formatPeriod(e.period)}
                        {e.kind !== "submitted" && e.actor ? ` · ${e.actor}` : ""}
                      </Text>
                      {e.comment && (
                        <Text
                          size='sm'
                          mt={4}
                          style={{ whiteSpace: "pre-wrap" }}
                          lineClamp={6}
                        >
                          {e.comment}
                        </Text>
                      )}
                    </Timeline.Item>
                  ))}
                </Timeline>
              ) : (
                <EmptyState
                  title='Подій немає'
                  text='Ця особа ще не подавала результатів у вибраному періоді'
                />
              )}
            </Tabs.Panel>

            <Tabs.Panel
              value='tasks'
              pt='md'
            >
              <DataTable
                rows={tasks}
                columns={taskColumns.filter(c => c.key !== "unit" && c.key !== "executors")}
                rowKey={t => t.periodId}
                initialSort={{ key: "deadline" }}
                empty='Завдань немає'
              />
            </Tabs.Panel>

            <Tabs.Panel
              value='months'
              pt='md'
            >
              {byMonth.length ? (
                <BarChart
                  h={260}
                  data={byMonth}
                  dataKey='month'
                  withLegend
                  series={[
                    { name: "Подання", color: "blue.6" },
                    { name: "Погоджено", color: "success.6" },
                    { name: "Повернено", color: "orange.6" },
                  ]}
                />
              ) : (
                <EmptyState title='Немає даних по місяцях' />
              )}
            </Tabs.Panel>
          </Tabs>
        </Stack>
      )}
    </Drawer>
  )
}

function Stat({ label, value, bad }: { label: string; value: string | number; bad?: boolean }) {
  return (
    <Stack gap={0}>
      <Text
        size='xs'
        c='dimmed'
      >
        {label}
      </Text>
      <Text
        fw={700}
        c={bad ? "danger" : undefined}
      >
        {value}
      </Text>
    </Stack>
  )
}
