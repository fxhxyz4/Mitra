import { Badge, Group, Text, Tooltip } from "@mantine/core"
import { IconFileText, IconRuler2, IconSparkles } from "@tabler/icons-react"
import type { DraftSource } from "@/shared/api"
import type { BadgeProps } from "@mantine/core"

const meta: Record<DraftSource, { label: string; color: string; hint: string; icon: typeof IconSparkles }> = {
  document: {
    label: "З документа",
    color: "blue",
    hint: "Значення взято з перетягнутого документа без змін",
    icon: IconFileText,
  },
  rule: {
    label: "За правилом",
    color: "teal",
    hint: "Визначено явним правилом системи",
    icon: IconRuler2,
  },
  model: {
    label: "Пропозиція моделі",
    color: "violet",
    hint: "Запропоновано локальною моделлю ШІ — перевірте",
    icon: IconSparkles,
  },
}

export function SourceBadge({
  source,
  ...props
}: Omit<BadgeProps, "color"> & { source: DraftSource | null | undefined }) {
  if (!source) return null
  const m = meta[source]
  return (
    <Tooltip label={m.hint}>
      <Badge
        variant='light'
        color={m.color}
        size='sm'
        leftSection={<m.icon size={12} />}
        {...props}
      >
        {m.label}
      </Badge>
    </Tooltip>
  )
}

export function AiNote({ children }: { children: string }) {
  return (
    <Group
      gap={6}
      wrap='nowrap'
      align='flex-start'
    >
      <IconSparkles
        size={14}
        style={{ flexShrink: 0, marginTop: 2 }}
        color='var(--mantine-color-violet-filled)'
      />
      <Text
        size='xs'
        c='dimmed'
      >
        {children}
      </Text>
    </Group>
  )
}
