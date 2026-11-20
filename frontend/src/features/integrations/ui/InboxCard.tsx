import { useState } from "react"
import { Badge, Button, Card, Collapse, Group, Stack, Text, Textarea } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconLink, IconX } from "@tabler/icons-react"
import { Link } from "react-router"
import type { IntegraInboxItem } from "@/shared/api"
import type { SearchOption } from "@/shared/ui/SearchSelect"

import { formatDate, formatDateTime } from "@/shared/lib"
import { measurePath, SearchSelect } from "@/shared/ui"
import { useDecideInbox } from "../api"
import { inboxStateMeta, statusLabel } from "./labels"

type Mode = null | "link" | "reject"

export function InboxCard({
  item,
  measures,
  canDecide,
}: {
  item: IntegraInboxItem
  measures: SearchOption[]
  canDecide: boolean
}) {
  const [mode, setMode] = useState<Mode>(null)
  const [measureId, setMeasureId] = useState<string | null>(null)
  const [comment, setComment] = useState("")
  const decide = useDecideInbox()
  const state = inboxStateMeta[item.state]
  const open = canDecide && item.state !== "LINKED"

  const done = (message: string) => {
    setMode(null)
    notifications.show({ color: "success", message })
  }

  return (
    <Card
      withBorder
      shadow='none'
    >
      <Stack gap='sm'>
        <Group
          justify='space-between'
          align='flex-start'
          wrap='nowrap'
        >
          <Group gap={6}>
            <Badge variant='outline'>Integra</Badge>
            {item.catalogNumber && (
              <Badge
                variant='outline'
                color='gray'
              >
                Додаток Д, п. {item.catalogNumber}
              </Badge>
            )}
            <Badge
              variant='light'
              color='gray'
            >
              у них: {statusLabel(item.externalStatus)}
            </Badge>
          </Group>
          <Badge
            color={state.color}
            style={{ flexShrink: 0 }}
          >
            {state.label}
          </Badge>
        </Group>

        <Text fw={600}>{item.title}</Text>
        {item.description && (
          <Text
            size='sm'
            c='dimmed'
            style={{ whiteSpace: "pre-line" }}
          >
            {item.description}
          </Text>
        )}
        <Text size='sm'>
          Відповідальний: {item.owner || "—"} · Строк: {formatDate(item.dueDate)}
        </Text>
        <Text
          size='xs'
          c='dimmed'
        >
          Отримано {formatDateTime(item.receivedAt)}
          {item.updatedAt !== item.receivedAt && ` · оновлено ${formatDateTime(item.updatedAt)}`}
        </Text>

        {item.state === "LINKED" && item.measureId && (
          <Text size='sm'>
            Повʼязано із заходом{" "}
            <Text
              component={Link}
              to={measurePath(item.measureId)}
              fw={600}
              inherit
            >
              {item.measureCode} {item.measureTitle}
            </Text>
            {item.reportedStatus && ` · передано в Integra: ${statusLabel(item.reportedStatus)}`}
          </Text>
        )}
        {item.state === "REJECTED" && (
          <Text size='sm'>
            Відхилено: {item.rejectReason}
            {item.decidedBy && ` (${item.decidedBy}, ${formatDateTime(item.decidedAt)})`}
          </Text>
        )}

        {open && (
          <>
            <Group gap='xs'>
              <Button
                size='xs'
                leftSection={<IconLink size={14} />}
                variant={mode === "link" ? "filled" : "light"}
                onClick={() => setMode(mode === "link" ? null : "link")}
              >
                Повʼязати із заходом програми
              </Button>
              {item.state === "NEW" && (
                <Button
                  size='xs'
                  color='gray'
                  leftSection={<IconX size={14} />}
                  variant={mode === "reject" ? "filled" : "light"}
                  onClick={() => setMode(mode === "reject" ? null : "reject")}
                >
                  Відхилити
                </Button>
              )}
            </Group>
            <Collapse expanded={mode === "link"}>
              <Group
                align='flex-end'
                gap='sm'
              >
                <SearchSelect
                  label='Захід програми'
                  placeholder='Код або назва заходу'
                  data={measures}
                  value={measureId}
                  onChange={setMeasureId}
                  style={{ flex: 1 }}
                />
                <Button
                  disabled={!measureId}
                  loading={decide.isPending}
                  onClick={() =>
                    measureId &&
                    decide.mutate(
                      { id: item.id, decision: "link", measureId },
                      { onSuccess: () => done("Повʼязано. Статус заходу передаватиметься в Integra") }
                    )
                  }
                >
                  Повʼязати
                </Button>
              </Group>
            </Collapse>
            <Collapse expanded={mode === "reject"}>
              <Group
                align='flex-end'
                gap='sm'
              >
                <Textarea
                  label='Причина'
                  autosize
                  minRows={1}
                  value={comment}
                  onChange={e => setComment(e.currentTarget.value)}
                  style={{ flex: 1 }}
                />
                <Button
                  color='gray'
                  disabled={comment.trim().length < 3}
                  loading={decide.isPending}
                  onClick={() =>
                    decide.mutate(
                      { id: item.id, decision: "reject", comment: comment.trim() },
                      { onSuccess: () => done("Відхилено") }
                    )
                  }
                >
                  Відхилити
                </Button>
              </Group>
            </Collapse>
          </>
        )}
      </Stack>
    </Card>
  )
}
