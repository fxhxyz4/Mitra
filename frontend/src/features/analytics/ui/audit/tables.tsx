import { Badge, Group, Stack, Text, Tooltip } from "@mantine/core"
import type {
  PerfCounters,
  PersonPerformance,
  ReviewerPerformance,
  TaskEvent,
  TaskRow,
  UnitPerformance,
} from "@/shared/api"
import type { Column } from "@/shared/ui"

import { formatDate, formatDateTime, formatNumber, formatPeriod } from "@/shared/lib"
import { FlagBadge, StatusBadge } from "@/shared/ui"
import { MeasureLink, Num } from "./cells"

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${formatNumber(v)} %`)
export const days = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${formatNumber(v)} дн.`)

export function counterColumns<T extends PerfCounters>(): Column<T>[] {
  return [
    {
      key: "tasks",
      label: "Завдань",
      hint: "Захід у звітному півріччі (постійні заходи — окреме завдання щопівроку)",
      render: r => r.tasks,
      sort: r => r.tasks,
      align: "right",
    },
    {
      key: "done",
      label: "Виконано",
      render: r => (
        <Text size='sm'>
          {r.done}{" "}
          <Text
            span
            c='dimmed'
            size='xs'
          >
            ({pct(r.donePercent)})
          </Text>
        </Text>
      ),
      sort: r => r.donePercent,
      align: "right",
    },
    {
      key: "onTime",
      label: "Вчасно",
      hint: "Частка виконаних не пізніше строку",
      render: r => (r.done ? pct(r.onTimePercent) : "—"),
      sort: r => (r.done ? r.onTimePercent : null),
      align: "right",
    },
    {
      key: "overdue",
      label: "Прострочено",
      hint: "Строк минув, результат не погоджено",
      render: r => (
        <Num
          value={r.overdue}
          bad
        />
      ),
      sort: r => r.overdue,
      align: "right",
    },
    {
      key: "notDone",
      label: "Не виконано",
      render: r => (
        <Num
          value={r.notDone}
          bad
        />
      ),
      sort: r => r.notDone,
      align: "right",
    },
    {
      key: "submissions",
      label: "Подань",
      hint: "Скільки разів результат подавали на перевірку",
      render: r => r.submissions,
      sort: r => r.submissions,
      align: "right",
    },
    {
      key: "returns",
      label: "Повернень",
      hint: "Скільки разів координатор повертав результат на доопрацювання",
      render: r => (
        <Num
          value={r.returns}
          bad
        />
      ),
      sort: r => r.returns,
      align: "right",
    },
    {
      key: "returnRate",
      label: "Частка повернень",
      hint: "Повернення / усі рішення координатора",
      render: r => (r.decisions ? pct(r.returnRate) : "—"),
      sort: r => (r.decisions ? r.returnRate : null),
      align: "right",
    },
    {
      key: "firstPass",
      label: "З першого разу",
      hint: "Частка завдань, погоджених без жодного повернення",
      render: r => (r.done + r.notDone + r.partial ? pct(r.firstPassPercent) : "—"),
      sort: r => (r.done + r.notDone + r.partial ? r.firstPassPercent : null),
      align: "right",
    },
    {
      key: "delay",
      label: "Сер. запізнення",
      hint: "Середня кількість днів запізнення серед виконаних пізно і прострочених",
      render: r => (
        <Text
          size='sm'
          c={r.avgDelayDays ? "danger" : "dimmed"}
        >
          {days(r.avgDelayDays)}
        </Text>
      ),
      sort: r => r.avgDelayDays,
      align: "right",
    },
    {
      key: "evidence",
      label: "Документів",
      render: r => r.evidence,
      sort: r => r.evidence,
      align: "right",
    },
    {
      key: "flags",
      label: "Risk Flags",
      render: r => (
        <Num
          value={r.openFlags}
          bad
        />
      ),
      sort: r => r.openFlags,
      align: "right",
    },
  ]
}

export const unitColumns: Column<UnitPerformance>[] = [
  {
    key: "name",
    label: "Підрозділ",
    render: u => (
      <Text
        size='sm'
        fw={500}
        c={u.orgUnitId ? undefined : "danger"}
      >
        {u.name}
      </Text>
    ),
    sort: u => u.name,
    width: 260,
  },
  { key: "people", label: "Виконавців", render: u => u.people, sort: u => u.people, align: "right" },
  ...counterColumns<UnitPerformance>(),
]

export const personColumns: Column<PersonPerformance>[] = [
  {
    key: "name",
    label: "Виконавець",
    render: p => (
      <Stack gap={0}>
        <Group gap={6}>
          <Text
            size='sm'
            fw={500}
          >
            {p.name}
          </Text>
          {!p.active && (
            <Badge
              size='xs'
              color='gray'
            >
              видалено
            </Badge>
          )}
          {p.tasks === 0 && (
            <Tooltip label='Виконавець підрозділу без завдань у вибраному періоді'>
              <Badge
                size='xs'
                variant='outline'
                color='gray'
              >
                без завдань
              </Badge>
            </Tooltip>
          )}
        </Group>
        <Text
          size='xs'
          c='dimmed'
        >
          {p.orgUnit}
        </Text>
      </Stack>
    ),
    sort: p => p.name,
    width: 260,
  },
  ...counterColumns<PersonPerformance>(),
  {
    key: "last",
    label: "Остання дія",
    render: p => (
      <Text
        size='xs'
        c='dimmed'
      >
        {p.lastActivity ? formatDateTime(p.lastActivity) : "—"}
      </Text>
    ),
    sort: p => p.lastActivity,
  },
]

export const reviewerColumns: Column<ReviewerPerformance>[] = [
  {
    key: "name",
    label: "Перевіряючий",
    render: r => (
      <Text
        size='sm'
        fw={500}
      >
        {r.name}
      </Text>
    ),
    sort: r => r.name,
  },
  { key: "reviews", label: "Рішень", render: r => r.reviews, sort: r => r.reviews, align: "right" },
  { key: "approved", label: "Погоджено", render: r => r.approved, sort: r => r.approved, align: "right" },
  { key: "returned", label: "Повернено", render: r => r.returned, sort: r => r.returned, align: "right" },
  {
    key: "rate",
    label: "Частка повернень",
    render: r => pct(r.returnRate),
    sort: r => r.returnRate,
    align: "right",
  },
  {
    key: "time",
    label: "Сер. час перевірки",
    hint: "Від подання на перевірку до рішення",
    render: r => days(r.avgReviewDays),
    sort: r => r.avgReviewDays,
    align: "right",
  },
]

export const taskColumns: Column<TaskRow>[] = [
  {
    key: "measure",
    label: "Захід",
    render: t => (
      <MeasureLink
        id={t.measureId}
        code={t.code}
        title={t.title}
      />
    ),
    sort: t => `${t.section}.${t.code.padStart(8, "0")}`,
    width: 320,
  },
  { key: "period", label: "Півріччя", render: t => formatPeriod(t.period), sort: t => t.period },
  {
    key: "status",
    label: "Статус",
    render: t => (
      <StatusBadge
        status={t.status}
        size='sm'
      />
    ),
    sort: t => t.status,
  },
  { key: "deadline", label: "Строк", render: t => formatDate(t.deadline), sort: t => t.deadline },
  { key: "actual", label: "Фактично", render: t => formatDate(t.actualDate), sort: t => t.actualDate },
  {
    key: "delay",
    label: "Запізнення",
    hint: "Для виконаних — на скільки днів пізніше строку; для прострочених — скільки днів минуло",
    render: t => (
      <Text
        size='sm'
        c={t.delayDays ? "danger" : "dimmed"}
        fw={t.overdue ? 600 : undefined}
      >
        {t.delayDays ? `${t.delayDays} дн.${t.overdue ? " (триває)" : ""}` : "—"}
      </Text>
    ),
    sort: t => t.delayDays,
    align: "right",
  },
  { key: "unit", label: "Підрозділ", render: t => t.orgUnit ?? "—", sort: t => t.orgUnit },
  {
    key: "executors",
    label: "Виконавці",
    render: t => (t.executors.length ? t.executors.join(", ") : "—"),
    sort: t => t.executors.join(", "),
  },
  { key: "subs", label: "Подань", render: t => t.submissions, sort: t => t.submissions, align: "right" },
  {
    key: "returns",
    label: "Повернень",
    render: t => (
      <Num
        value={t.returns}
        bad
      />
    ),
    sort: t => t.returns,
    align: "right",
  },
  {
    key: "evidence",
    label: "Документів",
    render: t => (
      <Num
        value={t.evidence}
        muted
      />
    ),
    sort: t => t.evidence,
    align: "right",
  },
  {
    key: "flags",
    label: "Risk Flags",
    render: t => (
      <Group gap={4}>
        {t.openFlags.map(f => (
          <FlagBadge
            key={f}
            type={f}
            size='xs'
          />
        ))}
      </Group>
    ),
    sort: t => t.openFlags.length,
  },
]

export const kindMeta: Record<TaskEvent["kind"], { label: string; color: string }> = {
  submitted: { label: "Подано", color: "blue" },
  approved: { label: "Погоджено", color: "success" },
  returned: { label: "Повернено", color: "orange" },
}

export const eventColumns: Column<TaskEvent>[] = [
  { key: "at", label: "Дата", render: e => formatDateTime(e.at), sort: e => e.at, width: 140 },
  {
    key: "kind",
    label: "Подія",
    render: e => (
      <Badge
        variant='light'
        color={kindMeta[e.kind].color}
        size='sm'
      >
        {kindMeta[e.kind].label}
        {e.round ? ` №${e.round}` : ""}
      </Badge>
    ),
    sort: e => e.kind,
  },
  {
    key: "measure",
    label: "Захід",
    render: e => (
      <MeasureLink
        id={e.measureId}
        code={e.code}
        title={e.title}
      />
    ),
    sort: e => e.code,
    width: 280,
  },
  { key: "period", label: "Півріччя", render: e => formatPeriod(e.period), sort: e => e.period },
  { key: "executor", label: "Виконавець", render: e => e.executor ?? "—", sort: e => e.executor },
  { key: "actor", label: "Хто", render: e => e.actor ?? "—", sort: e => e.actor },
  {
    key: "comment",
    label: "Коментар",
    render: e => (
      <Text
        size='sm'
        style={{ whiteSpace: "pre-wrap" }}
        lineClamp={4}
      >
        {e.comment || "—"}
      </Text>
    ),
    width: 320,
  },
]

export const returnColumns: Column<TaskEvent>[] = [
  ...eventColumns.filter(c => c.key !== "kind"),
  {
    key: "round",
    label: "№",
    hint: "Котре повернення цього завдання",
    render: e => e.round,
    sort: e => e.round,
    align: "right",
  },
  {
    key: "resolved",
    label: "Виправлено",
    hint: "Після повернення результат погоджено",
    render: e => (
      <Badge
        variant='light'
        color={e.resolved ? "success" : "warning"}
        size='sm'
      >
        {e.resolved ? "так" : "ні"}
      </Badge>
    ),
    sort: e => e.resolved,
  },
]
