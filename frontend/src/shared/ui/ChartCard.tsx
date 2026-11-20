import { Card, Group, Skeleton, Text } from "@mantine/core"
import type { ReactNode } from "react"

import { Deferred } from "./Deferred"

type ChartCardProps = {
  title: string
  subtitle?: string
  actions?: ReactNode
  loading?: boolean
  height?: number
  children: ReactNode
}

export function ChartCard({ title, subtitle, actions, loading, height = 280, children }: ChartCardProps) {
  return (
    <Card
      className='hover-lift'
      h='100%'
    >
      <Group
        justify='space-between'
        align='flex-start'
        mb='lg'
        gap='sm'
      >
        <div style={{ flex: "1 1 12rem", minWidth: 0 }}>
          <Text fw={600}>{title}</Text>
          {subtitle && (
            <Text
              size='sm'
              c='dimmed'
            >
              {subtitle}
            </Text>
          )}
        </div>
        {actions}
      </Group>
      {loading ? (
        <Skeleton
          h={height}
          radius='md'
        />
      ) : (
        <Deferred height={height}>{children}</Deferred>
      )}
    </Card>
  )
}
