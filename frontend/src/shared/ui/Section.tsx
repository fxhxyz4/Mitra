import { Card, Group, Skeleton, Stack, Text } from "@mantine/core"
import type { ReactNode } from "react"

type SectionProps = {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  loading?: boolean
  skeletonHeight?: number
  children: ReactNode
  padding?: "md" | "lg" | 0
}

export function Section({ title, subtitle, actions, loading, skeletonHeight, children, padding = "lg" }: SectionProps) {
  return (
    <Card
      h='100%'
      p={padding}
    >
      <Group
        justify='space-between'
        align='flex-start'
        mb='md'
        gap='sm'
        px={padding === 0 ? "lg" : 0}
        pt={padding === 0 ? "lg" : 0}
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
        <Stack
          gap='sm'
          px={padding === 0 ? "lg" : 0}
          pb={padding === 0 ? "lg" : 0}
        >
          {skeletonHeight ? (
            <Skeleton h={skeletonHeight} />
          ) : (
            <>
              <Skeleton h={44} />
              <Skeleton h={44} />
              <Skeleton h={44} />
            </>
          )}
        </Stack>
      ) : (
        children
      )}
    </Card>
  )
}
