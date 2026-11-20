import { Card, Group, Progress, Skeleton, Text, ThemeIcon, VisuallyHidden } from "@mantine/core"
import type { Icon } from "@tabler/icons-react"
import type { CSSProperties, KeyboardEvent, ReactNode } from "react"

import { HintLabel } from "./HintLabel"

type KpiTileProps = {
  label: string
  value: ReactNode
  hint?: ReactNode
  info?: { hint: ReactNode; formula?: string }
  icon?: Icon
  color?: string
  progress?: number
  loading?: boolean
  onClick?: () => void
}

export function KpiTile({
  label,
  value,
  hint,
  info,
  icon: TileIcon,
  color = "brand",
  progress,
  loading,
  onClick,
}: KpiTileProps) {
  const interactive = onClick
    ? {
        role: "button",
        tabIndex: 0,
        onClick,
        onKeyDown: (e: KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            onClick()
          }
        },
      }
    : {}
  return (
    <Card
      className='hover-lift app-kpi'
      h='100%'
      style={
        {
          "--kpi-tint": `var(--mantine-color-${color}-light)`,
          cursor: onClick ? "pointer" : undefined,
        } as CSSProperties
      }
      {...interactive}
    >
      <Group
        justify='space-between'
        align='flex-start'
        wrap='nowrap'
      >
        <Text
          size='sm'
          c='dimmed'
          fw={500}
        >
          {info ? (
            <HintLabel
              hint={info.hint}
              formula={info.formula}
            >
              {label}
            </HintLabel>
          ) : (
            label
          )}
        </Text>
        {TileIcon && (
          <ThemeIcon
            variant='light'
            color={color}
            radius='md'
            size='lg'
          >
            <TileIcon
              size={18}
              stroke={1.7}
            />
          </ThemeIcon>
        )}
      </Group>
      {loading ? (
        <Skeleton
          h={34}
          w='50%'
          mt={6}
        />
      ) : (
        <Text
          fz={30}
          fw={700}
          lh={1.2}
          mt={4}
        >
          {value}
        </Text>
      )}
      {progress !== undefined && (
        <Progress
          value={progress}
          aria-label={label}
          color={color}
          size='sm'
          mt='sm'
          radius='xl'
        />
      )}
      {hint && (
        <Text
          component='div'
          size='xs'
          c='dimmed'
          mt='xs'
        >
          {hint}
        </Text>
      )}
      {onClick && <VisuallyHidden> — показати перелік</VisuallyHidden>}
    </Card>
  )
}
