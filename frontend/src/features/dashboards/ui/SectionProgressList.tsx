import { Group, Progress, Stack, Text, Tooltip } from "@mantine/core"
import type { MeasureStatus, SectionProgress } from "@/shared/api"

import { sectionShort, statusMeta, statusOrder } from "@/shared/lib"

export function StatusBar({ byStatus, total }: { byStatus: Record<MeasureStatus, number>; total: number }) {
  return (
    <Progress.Root size={14}>
      {statusOrder
        .filter(s => byStatus[s])
        .map(s => (
          <Tooltip
            key={s}
            label={`${statusMeta[s].label}: ${byStatus[s]}`}
          >
            <Progress.Section
              value={(byStatus[s] / Math.max(total, 1)) * 100}
              color={statusMeta[s].color}
              aria-label={`${statusMeta[s].label}: ${byStatus[s]}`}
            />
          </Tooltip>
        ))}
    </Progress.Root>
  )
}

export function StatusLegend({ byStatus }: { byStatus: Record<MeasureStatus, number> }) {
  return (
    <Group gap='md'>
      {statusOrder
        .filter(s => byStatus[s])
        .map(s => (
          <Group
            key={s}
            gap={6}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 3,
                background: `var(--mantine-color-${statusMeta[s].color}-filled)`,
              }}
            />
            <Text size='xs'>
              {statusMeta[s].label} · {byStatus[s]}
            </Text>
          </Group>
        ))}
    </Group>
  )
}

export function SectionProgressList({ sections }: { sections: SectionProgress[] }) {
  return (
    <Stack gap='lg'>
      {sections.map(s => (
        <Stack
          key={s.number}
          gap={6}
        >
          <Group
            justify='space-between'
            wrap='nowrap'
          >
            <Text
              size='sm'
              fw={500}
              lineClamp={1}
            >
              {s.number}. {sectionShort[s.number] ?? s.title}
            </Text>
            <Text
              size='sm'
              fw={600}
              style={{ flexShrink: 0 }}
            >
              {s.donePercent}%
            </Text>
          </Group>
          <StatusBar
            byStatus={s.byStatus}
            total={s.total}
          />
          <Text
            size='xs'
            c={s.overdue ? "danger" : "dimmed"}
          >
            Заходів {s.total}
            {s.overdue ? ` · прострочено ${s.overdue}` : ""}
          </Text>
        </Stack>
      ))}
    </Stack>
  )
}
