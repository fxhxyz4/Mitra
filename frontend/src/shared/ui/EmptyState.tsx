import { Stack, Text, ThemeIcon } from "@mantine/core"
import { IconMoodSmile } from "@tabler/icons-react"
import type { Icon } from "@tabler/icons-react"
import type { ReactNode } from "react"

export function EmptyState({
  title,
  text,
  icon: StateIcon = IconMoodSmile,
}: {
  title: string
  text?: ReactNode
  icon?: Icon
}) {
  return (
    <Stack
      align='center'
      gap={6}
      py='xl'
    >
      <ThemeIcon
        variant='light'
        size={44}
        radius='xl'
        color='gray'
      >
        <StateIcon
          size={22}
          stroke={1.6}
        />
      </ThemeIcon>
      <Text fw={600}>{title}</Text>
      {text && (
        <Text
          size='sm'
          c='dimmed'
          ta='center'
          maw={420}
        >
          {text}
        </Text>
      )}
    </Stack>
  )
}
