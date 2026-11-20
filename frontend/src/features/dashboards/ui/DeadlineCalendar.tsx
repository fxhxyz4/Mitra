import { useMemo, useState } from "react"
import { ActionIcon, Group, Stack, Text, Tooltip } from "@mantine/core"
import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react"
import { Link } from "react-router"
import type { CalendarItem } from "@/shared/api"

import { formatDate, isoDate, statusMeta } from "@/shared/lib"
import { measurePath, StatusBadge } from "@/shared/ui"
import classes from "./DeadlineCalendar.module.scss"

const weekdays = [
  "Пн",
  "Вт",
  "Ср",
  "Чт",
  "Пт",
  "Сб",
  "Нд",
]
const monthFmt = new Intl.DateTimeFormat("uk-UA", { month: "long", year: "numeric" })

const colorOf = (item: CalendarItem) =>
  item.isOverdue && item.status !== "DONE" && item.status !== "PARTIAL" && item.status !== "NOT_DONE"
    ? "danger"
    : item.status
      ? statusMeta[item.status].color
      : "gray"

export function DeadlineCalendar({ items, initial }: { items: CalendarItem[]; initial?: Date }) {
  const [cursor, setCursor] = useState(() => {
    const d = initial ?? new Date()
    return new Date(d.getFullYear(), d.getMonth(), 1)
  })
  const today = isoDate(new Date())

  const byDate = useMemo(() => {
    const map = new Map<string, CalendarItem[]>()
    for (const i of items) map.set(i.date, [...(map.get(i.date) ?? []), i])
    return map
  }, [items])

  const days = useMemo(() => {
    const start = new Date(cursor)
    start.setDate(1 - ((cursor.getDay() + 6) % 7))
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start)
      d.setDate(start.getDate() + i)
      return d
    })
  }, [cursor])

  const monthItems = items.filter(i => i.date.startsWith(isoDate(cursor).slice(0, 7)))
  const shift = (n: number) => setCursor(c => new Date(c.getFullYear(), c.getMonth() + n, 1))

  return (
    <Stack gap='md'>
      <Group justify='space-between'>
        <Text
          fw={600}
          size='lg'
          tt='capitalize'
        >
          {monthFmt.format(cursor)}
        </Text>
        <Group gap={4}>
          <ActionIcon
            variant='default'
            aria-label='Попередній місяць'
            onClick={() => shift(-1)}
          >
            <IconChevronLeft size={16} />
          </ActionIcon>
          <ActionIcon
            variant='default'
            aria-label='Наступний місяць'
            onClick={() => shift(1)}
          >
            <IconChevronRight size={16} />
          </ActionIcon>
        </Group>
      </Group>

      <div className={classes.grid}>
        {weekdays.map(w => (
          <div
            key={w}
            className={classes.head}
          >
            {w}
          </div>
        ))}
        {days.map(d => {
          const key = isoDate(d)
          const list = byDate.get(key) ?? []
          return (
            <div
              key={key}
              className={classes.day}
              data-outside={d.getMonth() !== cursor.getMonth() || undefined}
              data-today={key === today || undefined}
            >
              <span className={classes.num}>{d.getDate()}</span>
              {list.slice(0, 3).map(i => {
                const color = colorOf(i)
                return (
                  <Tooltip
                    key={i.measureId}
                    label={`${i.code} ${i.title}`}
                    multiline
                    maw={280}
                  >
                    <Link
                      to={measurePath(i.measureId)}
                      className={classes.item}
                      style={{
                        ["--item-color" as string]: `var(--mantine-color-${color}-filled)`,
                        ["--item-bg" as string]: `var(--mantine-color-${color}-light)`,
                      }}
                    >
                      {i.code} {i.title}
                    </Link>
                  </Tooltip>
                )
              })}
              {list.length > 3 && (
                <Text
                  size='xs'
                  c='dimmed'
                >
                  +{list.length - 3}
                </Text>
              )}
            </div>
          )
        })}
      </div>

      <Stack
        gap='xs'
        className={classes.agenda}
      >
        {monthItems.map(i => (
          <Link
            key={i.measureId}
            to={measurePath(i.measureId)}
            style={{ color: "inherit", textDecoration: "none", display: "flex", gap: 12, alignItems: "center" }}
          >
            <Text
              size='sm'
              fw={600}
              w={86}
              c={colorOf(i) === "danger" ? "danger" : undefined}
            >
              {formatDate(i.date)}
            </Text>
            <Text
              size='sm'
              style={{ flex: 1 }}
              lineClamp={1}
            >
              {i.code} {i.title}
            </Text>
            <StatusBadge
              status={i.status}
              size='xs'
            />
          </Link>
        ))}
      </Stack>
    </Stack>
  )
}
