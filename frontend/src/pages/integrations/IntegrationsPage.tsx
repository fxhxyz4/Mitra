import { useState } from "react"
import { Alert, Badge, Button, Group, SegmentedControl, SimpleGrid, Skeleton, Stack, Text, Title } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconSend } from "@tabler/icons-react"
import type { InboxState } from "@/shared/api"

import {
  InboxCard,
  OutboxList,
  useFlushOutbox,
  useIntegraInbox,
  useIntegraOutbox,
  useIntegraStatus,
} from "@/features/integrations"
import { useMeasures } from "@/features/measures"
import { useSession } from "@/shared/api"
import { EmptyState, PageHeader, QueryError, Seo } from "@/shared/ui"

export function IntegrationsPage() {
  const { user } = useSession()
  const [state, setState] = useState<InboxState | "ALL">("NEW")
  const status = useIntegraStatus()
  const inbox = useIntegraInbox(state === "ALL" ? undefined : state)
  const outbox = useIntegraOutbox()
  const measures = useMeasures()
  const flush = useFlushOutbox()
  const options = (measures.data ?? []).map(m => ({ value: m.id, label: `${m.code} ${m.title}` }))
  const counts = status.data?.inbox
  const queue = status.data?.outbox

  return (
    <>
      <Seo title='Інтеграції' />
      <PageHeader
        title='Інтеграції'
        description='Integra надсилає заходи, прийняті її керівником. Координатор повʼязує такий захід із наявним заходом програми або відхиляє його; нові заходи автоматично не створюються. Коли статус повʼязаного заходу змінюється, Mitra повідомляє Integra, а для «Виконано» передає опис результату і SHA-256 документів.'
      />
      <QueryError error={status.error ?? inbox.error ?? outbox.error} />
      <Stack gap='xl'>
        {status.data && !status.data.enabled && (
          <Alert
            color='yellow'
            title='Відправлення в Integra вимкнено'
          >
            Не задано INTEGRA_URL або INTEGRA_API_KEY. Статуси накопичуються в черзі й підуть після налаштування.
          </Alert>
        )}

        <Stack gap='md'>
          <Group justify='space-between'>
            <Title order={3}>Вхідні</Title>
            <SegmentedControl
              value={state}
              onChange={v => setState(v as InboxState | "ALL")}
              data={[
                { value: "NEW", label: counts ? `Нові · ${counts.NEW}` : "Нові" },
                { value: "LINKED", label: "Повʼязані" },
                { value: "REJECTED", label: "Відхилені" },
                { value: "ALL", label: "Усі" },
              ]}
            />
          </Group>
          {inbox.isPending ? (
            <Skeleton h={200} />
          ) : inbox.data?.length ? (
            <SimpleGrid
              cols={{ base: 1, lg: 2 }}
              spacing='md'
            >
              {inbox.data.map(item => (
                <InboxCard
                  key={item.id}
                  item={item}
                  measures={options}
                  canDecide={user?.role === "COORDINATOR"}
                />
              ))}
            </SimpleGrid>
          ) : (
            <EmptyState title={state === "NEW" ? "Нових заходів від Integra немає" : "Нічого немає"} />
          )}
        </Stack>

        <Stack gap='md'>
          <Group justify='space-between'>
            <Group gap='xs'>
              <Title order={3}>Відправлення в Integra</Title>
              {queue && queue.PENDING > 0 && <Badge color='yellow'>у черзі {queue.PENDING}</Badge>}
              {queue && queue.FAILED > 0 && <Badge color='red'>помилок {queue.FAILED}</Badge>}
            </Group>
            <Button
              size='xs'
              variant='light'
              leftSection={<IconSend size={14} />}
              disabled={!status.data?.enabled}
              loading={flush.isPending}
              onClick={() =>
                flush.mutate(undefined, {
                  onSuccess: r =>
                    notifications.show({
                      color: r.failed ? "danger" : "success",
                      message: `Надіслано ${r.sent}, помилок ${r.failed}, у черзі ${r.pending}`,
                    }),
                })
              }
            >
              Надіслати зараз
            </Button>
          </Group>
          <Text
            size='sm'
            c='dimmed'
          >
            Черга з повторами: недоступність Integra не блокує роботу, невдала спроба повторюється із зростаючою паузою
            до 20 разів. Відмову Integra (наприклад, недозволений перехід статусу) автоматично не повторюємо.
          </Text>
          {outbox.isPending ? <Skeleton h={120} /> : <OutboxList items={outbox.data ?? []} />}
        </Stack>
      </Stack>
    </>
  )
}
