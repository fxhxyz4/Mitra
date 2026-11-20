import { Card, Text, Timeline } from "@mantine/core"
import { IconArrowBackUp, IconCheck, IconPencil } from "@tabler/icons-react"
import type { MeasureDetail } from "@/shared/api"

import { formatDateTime, statusMeta } from "@/shared/lib"

type Item = { id: string; at: string; title: string; text: string; who?: string; kind: "update" | "approve" | "return" }

export function ActivityTimeline({ measure, plain }: { measure: MeasureDetail; plain?: boolean }) {
  const items: Item[] = [
    ...measure.updates.map(u => ({
      id: u.id,
      at: u.createdAt,
      title:
        u.statusFrom === u.statusTo
          ? "Проміжний результат"
          : `${statusMeta[u.statusFrom].label} → ${statusMeta[u.statusTo].label}`,
      text: u.text,
      who: u.author?.displayName,
      kind: "update" as const,
    })),
    ...measure.approvals.map(a => ({
      id: a.id,
      at: a.createdAt,
      title: a.decision === "APPROVED" ? "Погоджено" : "Повернено на доопрацювання",
      text: a.comment,
      who: a.reviewer?.displayName,
      kind: a.decision === "APPROVED" ? ("approve" as const) : ("return" as const),
    })),
  ].sort((a, b) => b.at.localeCompare(a.at))

  const body = items.length ? (
    <Timeline
      bulletSize={24}
      lineWidth={2}
    >
      {items.map(i => (
        <Timeline.Item
          key={i.id}
          title={i.title}
          color={i.kind === "approve" ? "success" : i.kind === "return" ? "orange" : "brand"}
          bullet={
            i.kind === "approve" ? (
              <IconCheck size={13} />
            ) : i.kind === "return" ? (
              <IconArrowBackUp size={13} />
            ) : (
              <IconPencil size={13} />
            )
          }
        >
          {i.text && (
            <Text
              size='sm'
              style={{ whiteSpace: "pre-wrap" }}
            >
              {i.text}
            </Text>
          )}
          <Text
            size='xs'
            c='dimmed'
            mt={2}
          >
            {formatDateTime(i.at)}
            {i.who ? ` · ${i.who}` : ""}
          </Text>
        </Timeline.Item>
      ))}
    </Timeline>
  ) : (
    <Text
      size='sm'
      c='dimmed'
    >
      Подій ще немає
    </Text>
  )

  if (plain) return body
  return (
    <Card>
      <Text
        fw={600}
        mb='md'
      >
        Історія і зауваження
      </Text>
      {body}
    </Card>
  )
}
