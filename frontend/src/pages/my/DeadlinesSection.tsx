import { useMemo, useState } from "react"
import { ActionIcon, Button, Divider, Group, Indicator, Popover, SimpleGrid, Text, Tooltip } from "@mantine/core"
import { DatePicker } from "@mantine/dates"
import { IconCalendarSearch, IconX } from "@tabler/icons-react"
import type { MeasureListItem } from "@/shared/api"
import type { DatesRangeValue, DateStringValue } from "@mantine/dates"

import { useMeasures } from "@/features/measures"
import { formatDate, isoDate } from "@/shared/lib"
import { MeasureList, Section } from "@/shared/ui"

type Range = [string, string]

const addDays = (days: number) => {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return isoDate(d)
}

const presets: { label: string; range: () => Range }[] = [
  { label: "30 днів", range: () => [isoDate(new Date()), addDays(30)] },
  { label: "3 місяці", range: () => [isoDate(new Date()), addDays(91)] },
  { label: "Пів року", range: () => [isoDate(new Date()), addDays(182)] },
  { label: "До кінця року", range: () => [isoDate(new Date()), `${new Date().getFullYear()}-12-31`] },
]

type DeadlinesSectionProps = {
  upcoming: MeasureListItem[]
  loading: boolean
}

export function DeadlinesSection({ upcoming, loading }: DeadlinesSectionProps) {
  const [opened, setOpened] = useState(false)
  const [draft, setDraft] = useState<DatesRangeValue<DateStringValue>>([null, null])
  const [range, setRange] = useState<Range | null>(null)
  const mine = useMeasures({ mine: true })

  const deadlines = useMemo(() => new Set((mine.data ?? []).map(m => m.deadline.slice(0, 10))), [mine.data])
  const items = useMemo(() => {
    if (!range) return upcoming
    const [from, to] = range
    return (mine.data ?? [])
      .filter(m => m.deadline.slice(0, 10) >= from && m.deadline.slice(0, 10) <= to)
      .sort((a, b) => a.deadline.localeCompare(b.deadline))
  }, [
    range,
    mine.data,
    upcoming,
  ])

  const apply = (next: Range) => {
    setRange(next)
    setDraft(next)
    setOpened(false)
  }
  const reset = () => {
    setRange(null)
    setDraft([null, null])
  }

  const picker = (
    <Popover
      opened={opened}
      onChange={setOpened}
      position='bottom-end'
      shadow='md'
      withinPortal
    >
      <Popover.Target>
        <Tooltip
          label='Строки на інший період'
          disabled={opened}
        >
          <Button
            variant='light'
            size='xs'
            leftSection={<IconCalendarSearch size={16} />}
            onClick={() => setOpened(o => !o)}
            aria-label='Обрати період у календарі'
          >
            Календар
          </Button>
        </Tooltip>
      </Popover.Target>
      <Popover.Dropdown p='sm'>
        <SimpleGrid
          cols={2}
          spacing={6}
          mb='xs'
        >
          {presets.map(p => (
            <Button
              key={p.label}
              size='compact-sm'
              variant='default'
              onClick={() => apply(p.range())}
            >
              {p.label}
            </Button>
          ))}
        </SimpleGrid>
        <Divider
          label='або оберіть дати'
          labelPosition='center'
          mb='xs'
        />
        <DatePicker
          type='range'
          value={draft}
          onChange={v => {
            setDraft(v)
            if (v[0] && v[1]) apply([v[0], v[1]])
          }}
          allowSingleDateInRange
          renderDay={date => {
            const day = Number(date.slice(8, 10))
            return (
              <Indicator
                size={5}
                color='danger'
                offset={-3}
                disabled={!deadlines.has(date)}
              >
                <div>{day}</div>
              </Indicator>
            )
          }}
        />
        <Text
          size='xs'
          c='dimmed'
          mt={6}
        >
          Крапка — у цей день строк вашого заходу
        </Text>
      </Popover.Dropdown>
    </Popover>
  )

  return (
    <Section
      title={range ? `Строки ${formatDate(range[0])} – ${formatDate(range[1])}` : "Найближчі 30 днів"}
      subtitle={range ? `${items.length} ${plural(items.length)}` : undefined}
      loading={loading || (Boolean(range) && mine.isPending)}
      padding={0}
      actions={
        <Group
          gap={6}
          wrap='nowrap'
        >
          {range && (
            <Tooltip label='Повернутися до найближчих 30 днів'>
              <ActionIcon
                variant='subtle'
                color='gray'
                onClick={reset}
                aria-label='Скинути період'
              >
                <IconX size={16} />
              </ActionIcon>
            </Tooltip>
          )}
          {picker}
        </Group>
      }
    >
      <MeasureList
        items={items}
        empty={range ? "У цьому періоді строків немає" : "На найближчі 30 днів строків немає"}
        showUnit={false}
      />
    </Section>
  )
}

const plural = (n: number) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return "захід"
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "заходи"
  return "заходів"
}
