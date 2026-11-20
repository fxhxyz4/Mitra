import { useMemo, useState } from "react"
import {
  Badge,
  Button,
  Card,
  CloseButton,
  Group,
  MultiSelect,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Tabs,
  Text,
  TextInput,
} from "@mantine/core"
import { notifications } from "@mantine/notifications"
import {
  IconArrowBackUp,
  IconBuildingCommunity,
  IconChartLine,
  IconFileSpreadsheet,
  IconListDetails,
  IconSearch,
  IconTimeline,
  IconUserCheck,
  IconUsers,
} from "@tabler/icons-react"
import { useSearchParams } from "react-router"
import type { MeasureStatus, PersonPerformance, TaskEvent, TaskRow } from "@/shared/api"

import { formatDate, formatPeriod, statusMeta, statusOrder } from "@/shared/lib"
import { DataTable, QueryError, SearchSelect } from "@/shared/ui"
import { exportPerformance, usePerformance } from "../../api"
import { AuditCharts } from "./AuditCharts"
import { DynamicsCharts, IndicatorsTab } from "./DynamicsCharts"
import { PersonDrawer } from "./PersonDrawer"
import {
  days,
  eventColumns,
  pct,
  personColumns,
  returnColumns,
  reviewerColumns,
  taskColumns,
  unitColumns,
} from "./tables"

const TABS = [
  "units",
  "people",
  "tasks",
  "returns",
  "events",
  "reviewers",
  "indicators",
] as const
type Tab = (typeof TABS)[number]
const isTab = (v: string | null): v is Tab => TABS.includes(v as Tab)

const kindOptions = [
  { value: "all", label: "Усі події" },
  { value: "submitted", label: "Подання" },
  { value: "approved", label: "Погодження" },
  { value: "returned", label: "Повернення" },
]

const matches = (q: string, ...parts: (string | null | undefined)[]) =>
  !q || parts.some(p => p?.toLowerCase().includes(q.toLowerCase()))

export function AuditView({ programId, withTrends }: { programId?: string | null; withTrends: boolean }) {
  const [params, setParams] = useSearchParams()
  const period = params.get("period")
  const orgUnitId = params.get("unit")
  const userId = params.get("user")
  const requested = params.get("tab")
  const tab: Tab = isTab(requested) && (withTrends || requested !== "indicators") ? requested : "units"

  const set = (patch: Record<string, string | null>) =>
    setParams(
      p => {
        for (const [k, v] of Object.entries(patch)) {
          if (v) p.set(k, v)
          else p.delete(k)
        }
        return p
      },
      { replace: true }
    )

  const base = usePerformance({ programId, period })
  const filtered = Boolean(orgUnitId || userId)
  const scoped = usePerformance({ programId, period, orgUnitId, userId }, filtered)
  const report = filtered ? scoped.data : base.data
  const loading = filtered ? scoped.isPending : base.isPending
  const t = report?.totals

  const [person, setPerson] = useState<PersonPerformance | null>(null)
  const [taskQuery, setTaskQuery] = useState("")
  const [taskStatus, setTaskStatus] = useState<string[]>([])
  const [problemsOnly, setProblemsOnly] = useState(false)
  const [noUnitOnly, setNoUnitOnly] = useState(false)
  const [eventQuery, setEventQuery] = useState("")
  const [eventKind, setEventKind] = useState("all")

  const unitOptions = (base.data?.units ?? [])
    .filter(u => u.orgUnitId)
    .map(u => ({ value: u.orgUnitId!, label: u.name }))
  const personOptions = (base.data?.people ?? []).map(p => ({ value: p.userId, label: `${p.name} · ${p.orgUnit}` }))
  const unitName = unitOptions.find(o => o.value === orgUnitId)?.label
  const personName = base.data?.people.find(p => p.userId === userId)?.name

  const tasks = useMemo(
    () =>
      (report?.tasks ?? []).filter(
        (r: TaskRow) =>
          matches(taskQuery, r.code, r.title, r.orgUnit, r.executors.join(" ")) &&
          (!taskStatus.length || taskStatus.includes(r.status)) &&
          (!problemsOnly || r.overdue || r.returns > 0 || r.openFlags.length > 0 || r.status === "NOT_DONE") &&
          (!noUnitOnly || r.orgUnitId === null)
      ),
    [
      report,
      taskQuery,
      taskStatus,
      problemsOnly,
      noUnitOnly,
    ]
  )
  const events = useMemo(
    () =>
      (report?.events ?? []).filter(
        (e: TaskEvent) =>
          (eventKind === "all" || e.kind === eventKind) &&
          matches(eventQuery, e.code, e.title, e.executor, e.actor, e.comment, e.orgUnit)
      ),
    [
      report,
      eventQuery,
      eventKind,
    ]
  )
  const returns = (report?.events ?? []).filter(e => e.kind === "returned")
  const unresolved = returns.filter(e => !e.resolved).length

  const runExport = () =>
    exportPerformance({ programId, period, orgUnitId, userId }).catch((e: Error) =>
      notifications.show({ color: "danger", message: e.message })
    )

  return (
    <Stack gap='lg'>
      <QueryError error={base.error ?? scoped.error} />

      <AuditCharts
        report={report}
        loading={loading && !report}
      />
      {withTrends && <DynamicsCharts programId={programId} />}

      <Card>
        <Stack gap='sm'>
          <Group
            gap='sm'
            align='flex-end'
          >
            <Select
              label='Півріччя'
              data={[
                { value: "", label: "Усі півріччя" },
                ...(base.data?.periods ?? []).map(p => ({ value: p, label: formatPeriod(p) })),
              ]}
              value={period ?? ""}
              onChange={v => set({ period: v || null })}
              allowDeselect={false}
              w={180}
            />
            <SearchSelect
              label='Підрозділ'
              placeholder='Усі підрозділи'
              data={unitOptions}
              value={orgUnitId}
              onChange={v => set({ unit: v })}
              clearable
              w={280}
            />
            <SearchSelect
              label='Виконавець'
              placeholder='Усі виконавці'
              data={personOptions}
              value={userId}
              onChange={v => set({ user: v })}
              clearable
              w={300}
            />
            <Button
              variant='light'
              leftSection={<IconFileSpreadsheet size={16} />}
              onClick={runExport}
              disabled={!report}
              ml='auto'
            >
              Експорт XLSX
            </Button>
          </Group>
          {report?.scope && (
            <Text
              size='xs'
              c='dimmed'
            >
              Аналітика за ваш підрозділ: <b>{report.scope}</b> (разом із підпорядкованими)
            </Text>
          )}
          {(filtered || period) && (
            <Group gap='xs'>
              <Text
                size='xs'
                c='dimmed'
              >
                Зріз:
              </Text>
              {period && (
                <FilterChip
                  label={formatPeriod(period)}
                  onClear={() => set({ period: null })}
                />
              )}
              {orgUnitId && (
                <FilterChip
                  label={unitName ?? "Підрозділ"}
                  onClear={() => set({ unit: null })}
                />
              )}
              {userId && (
                <FilterChip
                  label={personName ?? "Виконавець"}
                  onClear={() => set({ user: null })}
                />
              )}
              <Button
                size='compact-xs'
                variant='subtle'
                onClick={() => set({ period: null, unit: null, user: null })}
              >
                Скинути все
              </Button>
            </Group>
          )}
        </Stack>
      </Card>

      <SimpleGrid
        cols={{ base: 2, sm: 4, lg: 7 }}
        spacing='sm'
      >
        <Metric
          label='Завдань'
          value={t?.tasks}
          hint='захід × півріччя'
          loading={loading}
        />
        <Metric
          label='Виконано'
          value={t ? `${t.done} (${pct(t.donePercent)})` : undefined}
          loading={loading}
        />
        <Metric
          label='Вчасно'
          value={t ? pct(t.onTimePercent) : undefined}
          hint={t ? `із запізненням: ${t.lateDone}` : undefined}
          loading={loading}
        />
        <Metric
          label='Прострочено'
          value={t?.overdue}
          bad={Boolean(t?.overdue)}
          loading={loading}
        />
        <Metric
          label='Повернень'
          value={t ? `${t.returns} (${pct(t.returnRate)})` : undefined}
          hint={t ? `рішень: ${t.decisions}` : undefined}
          bad={Boolean(t?.returns)}
          loading={loading}
        />
        <Metric
          label='З першого разу'
          value={t ? pct(t.firstPassPercent) : undefined}
          hint='погоджено без повернень'
          loading={loading}
        />
        <Metric
          label='Сер. запізнення'
          value={t ? days(t.avgDelayDays) : undefined}
          hint={t ? `завдань із запізненням: ${t.delayed}` : undefined}
          bad={Boolean(t?.avgDelayDays)}
          loading={loading}
        />
      </SimpleGrid>

      <Tabs
        value={tab}
        onChange={v => set({ tab: v === "units" ? null : v })}
        keepMounted={false}
      >
        <Tabs.List>
          <Tabs.Tab
            value='units'
            leftSection={<IconBuildingCommunity size={16} />}
          >
            Підрозділи
          </Tabs.Tab>
          <Tabs.Tab
            value='people'
            leftSection={<IconUsers size={16} />}
          >
            Виконавці
          </Tabs.Tab>
          <Tabs.Tab
            value='tasks'
            leftSection={<IconListDetails size={16} />}
          >
            Заходи
          </Tabs.Tab>
          <Tabs.Tab
            value='returns'
            leftSection={<IconArrowBackUp size={16} />}
            rightSection={
              unresolved ? (
                <Badge
                  size='xs'
                  color='orange'
                  circle
                >
                  {unresolved}
                </Badge>
              ) : undefined
            }
          >
            Повернення
          </Tabs.Tab>
          <Tabs.Tab
            value='events'
            leftSection={<IconTimeline size={16} />}
          >
            Хронологія
          </Tabs.Tab>
          <Tabs.Tab
            value='reviewers'
            leftSection={<IconUserCheck size={16} />}
          >
            Перевіряючі
          </Tabs.Tab>
          {withTrends && (
            <Tabs.Tab
              value='indicators'
              leftSection={<IconChartLine size={16} />}
            >
              Індикатори
            </Tabs.Tab>
          )}
        </Tabs.List>

        <Card mt='md'>
          <Tabs.Panel value='units'>
            <Hint>Натисніть на підрозділ, щоб побачити його виконавців і заходи.</Hint>
            <DataTable
              rows={report?.units ?? []}
              columns={unitColumns}
              rowKey={u => u.orgUnitId ?? "none"}
              selected={orgUnitId}
              initialSort={{ key: "name", desc: false }}
              onRowClick={u => {
                if (u.orgUnitId) set({ unit: u.orgUnitId, tab: "people" })
                else {
                  setNoUnitOnly(true)
                  set({ tab: "tasks" })
                }
              }}
              empty={loading ? "Завантаження…" : "Немає завдань у вибраному зрізі"}
              minWidth={1200}
            />
          </Tabs.Panel>

          <Tabs.Panel value='people'>
            <Hint>
              Виконавцем вважається той, хто подавав результат; до першого подання — персонально призначений. Натисніть
              на рядок, щоб відкрити картку особи.
            </Hint>
            <DataTable
              rows={report?.people ?? []}
              columns={personColumns}
              rowKey={p => p.userId}
              selected={person?.userId ?? userId}
              initialSort={{ key: "name", desc: false }}
              onRowClick={setPerson}
              empty={loading ? "Завантаження…" : "Виконавців у вибраному зрізі немає"}
              minWidth={1300}
            />
          </Tabs.Panel>

          <Tabs.Panel value='tasks'>
            <Group
              gap='sm'
              mb='sm'
              align='flex-end'
            >
              <TextInput
                placeholder='Пошук: номер, назва, підрозділ, виконавець'
                leftSection={<IconSearch size={16} />}
                value={taskQuery}
                onChange={e => setTaskQuery(e.currentTarget.value)}
                w={320}
              />
              <MultiSelect
                placeholder={taskStatus.length ? undefined : "Усі статуси"}
                data={statusOrder.filter(s => s !== "DRAFT").map(s => ({ value: s, label: statusMeta[s].label }))}
                value={taskStatus}
                onChange={v => setTaskStatus(v as MeasureStatus[])}
                clearable
                w={280}
              />
              <Switch
                label='Лише проблемні'
                description='прострочені, повернені, з прапорцями, невиконані'
                checked={problemsOnly}
                onChange={e => setProblemsOnly(e.currentTarget.checked)}
              />
              {noUnitOnly && (
                <FilterChip
                  label='Без відповідального підрозділу'
                  onClear={() => setNoUnitOnly(false)}
                />
              )}
              <Text
                size='xs'
                c='dimmed'
                ml='auto'
              >
                {tasks.length} з {report?.tasks.length ?? 0}
              </Text>
            </Group>
            <DataTable
              rows={tasks}
              columns={taskColumns}
              rowKey={r => r.periodId}
              initialSort={{ key: "measure", desc: false }}
              empty='Завдань за цими умовами немає'
              minWidth={1400}
            />
          </Tabs.Panel>

          <Tabs.Panel value='returns'>
            <Hint>
              Кожне повернення на доопрацювання з коментарем перевіряючого. «Виправлено: ні» — після повернення
              результат ще не погоджено.
            </Hint>
            <DataTable
              rows={returns}
              columns={returnColumns}
              rowKey={e => `${e.measureId}-${e.period}-${e.at}`}
              initialSort={{ key: "at", desc: true }}
              empty='Повернень на доопрацювання немає'
              minWidth={1200}
            />
          </Tabs.Panel>

          <Tabs.Panel value='events'>
            <Group
              gap='sm'
              mb='sm'
            >
              <SegmentedControl
                size='xs'
                data={kindOptions}
                value={eventKind}
                onChange={setEventKind}
              />
              <TextInput
                placeholder='Пошук: захід, особа, коментар'
                leftSection={<IconSearch size={16} />}
                value={eventQuery}
                onChange={e => setEventQuery(e.currentTarget.value)}
                w={300}
              />
              <Text
                size='xs'
                c='dimmed'
                ml='auto'
              >
                {report ? `станом на ${formatDate(report.asOf)}` : ""}
              </Text>
            </Group>
            <DataTable
              rows={events}
              columns={eventColumns}
              rowKey={e => `${e.kind}-${e.measureId}-${e.period}-${e.at}`}
              initialSort={{ key: "at", desc: true }}
              empty='Подій немає'
              minWidth={1200}
            />
          </Tabs.Panel>

          <Tabs.Panel value='reviewers'>
            <Hint>Рішення координаторів щодо поданих результатів: скільки погоджено, повернено і як швидко.</Hint>
            <DataTable
              rows={report?.reviewers ?? []}
              columns={reviewerColumns}
              rowKey={r => r.userId}
              initialSort={{ key: "reviews", desc: true }}
              empty='Рішень у вибраному зрізі немає'
            />
          </Tabs.Panel>

          {withTrends && (
            <Tabs.Panel value='indicators'>
              <IndicatorsTab programId={programId} />
            </Tabs.Panel>
          )}
        </Card>
      </Tabs>

      <PersonDrawer
        person={person}
        report={report}
        onClose={() => setPerson(null)}
        onFilter={id => {
          setPerson(null)
          set({ user: id, tab: "tasks" })
        }}
      />
    </Stack>
  )
}

function Metric({
  label,
  value,
  hint,
  bad,
  loading,
}: {
  label: string
  value: string | number | undefined
  hint?: string
  bad?: boolean
  loading?: boolean
}) {
  return (
    <Card
      p='sm'
      withBorder
    >
      <Text
        size='xs'
        c='dimmed'
      >
        {label}
      </Text>
      <Text
        fw={700}
        size='lg'
        c={bad ? "danger" : undefined}
      >
        {loading && value === undefined ? "…" : (value ?? "—")}
      </Text>
      {hint && (
        <Text
          size='xs'
          c='dimmed'
        >
          {hint}
        </Text>
      )}
    </Card>
  )
}

function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <Badge
      variant='light'
      size='lg'
      rightSection={
        <CloseButton
          size='xs'
          onClick={onClear}
          aria-label={`Прибрати фільтр «${label}»`}
        />
      }
    >
      {label}
    </Badge>
  )
}

function Hint({ children }: { children: string }) {
  return (
    <Text
      size='xs'
      c='dimmed'
      mb='sm'
    >
      {children}
    </Text>
  )
}
