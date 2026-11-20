import { Badge, Card, Group, SimpleGrid, Stack, Text } from "@mantine/core"
import { IconEqual, IconTrendingDown } from "@tabler/icons-react"
import type { RiskState } from "@/shared/api"

import { EmptyState, IndicatorBlock, LevelBadge } from "@/shared/ui"

export function RiskStateList({ risks }: { risks: RiskState[] }) {
  if (!risks.length) return <EmptyState title='Ризики не повʼязані із заходами' />
  return (
    <SimpleGrid
      cols={{ base: 1, md: 2 }}
      spacing='md'
    >
      {risks.map(r => (
        <Card
          key={r.id}
          withBorder
          shadow='none'
        >
          <Stack gap='sm'>
            <Group
              justify='space-between'
              align='flex-start'
              gap={6}
            >
              <Group
                gap={6}
                style={{ minWidth: 0 }}
              >
                <Text fw={700}>{r.code}</Text>
                <LevelBadge
                  level={r.level}
                  size='xs'
                />
              </Group>
              <Badge
                color={r.reduced ? "success" : "gray"}
                variant={r.reduced ? "filled" : "light"}
                leftSection={r.reduced ? <IconTrendingDown size={12} /> : <IconEqual size={12} />}
                style={{ flexShrink: 0 }}
              >
                {r.reduced ? "Ризик зменшено" : "Без змін"}
              </Badge>
            </Group>
            <Text
              size='sm'
              lineClamp={2}
            >
              {r.description}
            </Text>
            {r.indicators.map(i => (
              <IndicatorBlock
                key={i.id}
                indicator={i}
              />
            ))}
            <Text
              size='xs'
              c='dimmed'
            >
              Заходів виконано {r.measuresDone} з {r.measuresTotal}
            </Text>
          </Stack>
        </Card>
      ))}
    </SimpleGrid>
  )
}
