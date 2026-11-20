import { Alert, ScrollArea, SegmentedControl, Text } from "@mantine/core"
import type { MeasureListItem, MeasureStatus } from "@/shared/api"

import { useMeasures } from "@/features/measures"
import { MeasureList, Section } from "@/shared/ui"

export const ALL_MEASURES_ID = "all-my-measures"

type Group = "active" | "review" | "done" | "not_done"
export type MeasureFilter = "all" | "overdue" | "returned" | Group

/** Групи станів для виконавця: що ще робити, що чекає координатора, чим усе скінчилось. */
const GROUP: Record<MeasureStatus, Group> = {
  DRAFT: "active",
  PLANNED: "active",
  IN_PROGRESS: "active",
  RETURNED: "active",
  ON_REVIEW: "review",
  DONE: "done",
  PARTIAL: "done",
  NOT_DONE: "not_done",
}

const LABELS: Record<MeasureFilter, string> = {
  all: "Усі",
  overdue: "Прострочені",
  returned: "Повернені",
  active: "В роботі",
  review: "На перевірці",
  done: "Виконані",
  not_done: "Не виконані",
}

const ORDER: Group[] = [
  "active",
  "review",
  "done",
  "not_done",
]

/** Без звітного періоду (status null) — ще в роботі. */
const groupOf = (m: MeasureListItem): Group => (m.status ? GROUP[m.status] : "active")

/** Прострочені й повернені — за тими самими правилами, що й плитки (isOverdue з сервера; стан «Повернено»). */
const matches = (m: MeasureListItem, f: MeasureFilter) => {
  if (f === "all") return true
  if (f === "overdue") return m.isOverdue
  if (f === "returned") return m.status === "RETURNED"
  return groupOf(m) === f
}

/** Спершу прострочені, потім повернені на доопрацювання, далі в роботі за строком; завершені — в кінці. */
const byPriority = (a: MeasureListItem, b: MeasureListItem) =>
  Number(b.isOverdue) - Number(a.isOverdue) ||
  Number(b.status === "RETURNED") - Number(a.status === "RETURNED") ||
  ORDER.indexOf(groupOf(a)) - ORDER.indexOf(groupOf(b)) ||
  a.deadline.localeCompare(b.deadline)

/**
 * Усі заходи виконавця — зокрема прострочені, завершені й ті, що зі строком за кілька місяців:
 * інакше на такий захід зі сторінки «Мої заходи» просто нема як перейти.
 */
export function AllMeasuresSection({
  filter,
  onFilterChange,
  comments = {},
}: {
  filter: MeasureFilter
  onFilterChange: (filter: MeasureFilter) => void
  /** Зауваження координатора до повернених заходів: id заходу → коментар. */
  comments?: Record<string, string>
}) {
  const { data, isPending } = useMeasures({ mine: true })
  const items = [...(data ?? [])].sort(byPriority)
  const shown = items.filter(m => matches(m, filter))

  return (
    <div id={ALL_MEASURES_ID}>
      <Section
        title={`Усі мої заходи (${items.length})`}
        subtitle='Прострочені, повернені, в роботі, на перевірці, виконані й не виконані'
        loading={isPending}
        padding={0}
      >
        <ScrollArea
          type='auto'
          px='md'
          pt='md'
        >
          <SegmentedControl
            size='xs'
            value={filter}
            onChange={v => onFilterChange(v as MeasureFilter)}
            data={(Object.keys(LABELS) as MeasureFilter[]).map(f => ({
              value: f,
              label: `${LABELS[f]} ${items.filter(m => matches(m, f)).length}`,
            }))}
            aria-label='Стан заходів'
            mb='sm'
          />
        </ScrollArea>
        <MeasureList
          items={shown}
          empty={filter === "all" ? "Заходів немає" : `${LABELS[filter]}: заходів немає`}
          showUnit={false}
          extra={item =>
            item.status === "RETURNED" && comments[item.id] ? (
              <Alert
                color='orange'
                variant='light'
                p='xs'
              >
                <Text size='sm'>{comments[item.id]}</Text>
              </Alert>
            ) : null
          }
        />
      </Section>
    </div>
  )
}
