import { Badge, Button, Table, Text } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import type { IntegraOutboxMessage } from "@/shared/api"

import { formatDateTime } from "@/shared/lib"
import { EmptyState } from "@/shared/ui"
import { useRetryOutbox } from "../api"
import { outboxStateMeta, statusLabel } from "./labels"

function when(m: IntegraOutboxMessage) {
  if (m.sentAt) return `надіслано ${formatDateTime(m.sentAt)}`
  if (m.state === "PENDING" && m.attempts) return `наступна спроба ${formatDateTime(m.nextAttemptAt)}`
  return formatDateTime(m.createdAt)
}

export function OutboxList({ items }: { items: IntegraOutboxMessage[] }) {
  const retry = useRetryOutbox()
  if (!items.length) return <EmptyState title='Відправлень ще не було' />
  return (
    <Table.ScrollContainer minWidth={640}>
      <Table verticalSpacing='xs'>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Захід Integra</Table.Th>
            <Table.Th>Статус</Table.Th>
            <Table.Th>Стан</Table.Th>
            <Table.Th>Спроби</Table.Th>
            <Table.Th>Час</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {items.map(m => (
            <Table.Tr key={m.id}>
              <Table.Td>
                <Text size='sm'>{m.title ?? "—"}</Text>
                {m.lastError && (
                  <Text
                    size='xs'
                    c='red'
                  >
                    {m.lastError}
                  </Text>
                )}
              </Table.Td>
              <Table.Td>{statusLabel(m.status)}</Table.Td>
              <Table.Td>
                <Badge
                  color={outboxStateMeta[m.state].color}
                  variant='light'
                >
                  {outboxStateMeta[m.state].label}
                </Badge>
              </Table.Td>
              <Table.Td>{m.attempts}</Table.Td>
              <Table.Td>
                <Text size='xs'>{when(m)}</Text>
              </Table.Td>
              <Table.Td>
                {m.state === "FAILED" && (
                  <Button
                    size='compact-xs'
                    variant='light'
                    loading={retry.isPending && retry.variables === m.id}
                    onClick={() =>
                      retry.mutate(m.id, {
                        onSuccess: r =>
                          notifications.show({
                            color: r.failed ? "danger" : "success",
                            message: r.failed ? "Integra знову відповіла помилкою" : "Надіслано",
                          }),
                      })
                    }
                  >
                    Повторити
                  </Button>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
