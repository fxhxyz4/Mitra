import { Badge, Group, Progress, Stack, Text } from "@mantine/core"
import type { Indicator } from "@/shared/api"

import { formatNumber, toNumber } from "@/shared/lib"

function indicatorProgress(i: Indicator) {
  const base = toNumber(i.baseline) ?? 0
  const target = toNumber(i.target) ?? 0
  const current = toNumber(i.current) ?? base
  if (base === target) return 100
  return Math.max(0, Math.min(100, ((current - base) / (target - base)) * 100))
}

export function IndicatorBlock({ indicator }: { indicator: Indicator }) {
  const pct = indicatorProgress(indicator)
  return (
    <Stack gap={6}>
      <Group
        justify='space-between'
        align='flex-start'
        gap={6}
      >
        <Text
          size='sm'
          fw={500}
          style={{ flex: "1 1 160px", minWidth: 0 }}
        >
          {indicator.name}
        </Text>
        <Badge
          variant='light'
          color={indicator.isTargetReached ? "success" : indicator.isImproved ? "cyan" : "gray"}
          style={{ flexShrink: 0 }}
        >
          {indicator.isTargetReached ? "Ціль досягнуто" : indicator.isImproved ? "Покращено" : "Без змін"}
        </Badge>
      </Group>
      <Progress
        value={pct}
        aria-label='Прогрес до цілі'
        color={indicator.isTargetReached ? "success" : "brand"}
        size='md'
        radius='xl'
      />
      <Group
        justify='space-between'
        gap='xs'
      >
        <Text
          size='xs'
          c='dimmed'
        >
          База {formatNumber(indicator.baseline)} {indicator.unit}
        </Text>
        <Text
          size='xs'
          fw={600}
        >
          Зараз {formatNumber(indicator.current ?? indicator.baseline)} {indicator.unit}
        </Text>
        <Text
          size='xs'
          c='dimmed'
        >
          Ціль {formatNumber(indicator.target)} {indicator.unit}
        </Text>
      </Group>
    </Stack>
  )
}
