import { Code, Group, Skeleton, Stack, Text, Timeline, Tooltip } from "@mantine/core"
import { IconLink } from "@tabler/icons-react"
import type { AuditEntry } from "@/shared/api"

import { describeAction, entityLabels, formatDateTime } from "@/shared/lib"

const preview = (value: Record<string, unknown> | null) => {
  if (!value) return null
  const text = Object.entries(value)
    .filter(([, v]) => v !== null && v !== "")
    .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ")
  return text.length > 220 ? `${text.slice(0, 220)}…` : text
}

export function AuditTimeline({ entries, loading }: { entries?: AuditEntry[]; loading?: boolean }) {
  if (loading)
    return (
      <Stack>
        <Skeleton h={48} />
        <Skeleton h={48} />
        <Skeleton h={48} />
      </Stack>
    )
  if (!entries?.length)
    return (
      <Text
        size='sm'
        c='dimmed'
      >
        Записів немає
      </Text>
    )
  return (
    <Timeline
      bulletSize={12}
      lineWidth={2}
    >
      {entries.map(e => (
        <Timeline.Item
          key={e.id}
          title={
            <Group gap={6}>
              <Text
                size='sm'
                fw={600}
              >
                {describeAction(e.action)}
              </Text>
              <Text
                size='xs'
                c='dimmed'
              >
                {entityLabels[e.entity] ?? e.entity}
              </Text>
            </Group>
          }
        >
          {preview(e.newValue) && (
            <Text
              size='xs'
              c='dimmed'
              lineClamp={2}
            >
              {preview(e.newValue)}
            </Text>
          )}
          <Group
            gap={6}
            mt={2}
          >
            <Text size='xs'>
              {formatDateTime(e.at)} · {e.user?.displayName ?? "Система"}
            </Text>
            <Tooltip
              label={`prevHash ${e.prevHash}\nhash ${e.hash}`}
              multiline
              maw={460}
              style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}
            >
              <Group gap={2}>
                <IconLink
                  size={12}
                  stroke={1.6}
                />
                <Code fz={10}>
                  #{e.id} {e.hash.slice(0, 8)}
                </Code>
              </Group>
            </Tooltip>
          </Group>
        </Timeline.Item>
      ))}
    </Timeline>
  )
}
