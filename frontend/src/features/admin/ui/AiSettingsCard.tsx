import { Alert, Badge, Card, Group, Skeleton, Stack, Switch, Text, Title } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconSparkles } from "@tabler/icons-react"
import type { ReactNode } from "react"

import { useAiStatus } from "@/shared/api"
import { useAiSettings, useSetAiSettings } from "../api"

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Group justify='space-between'>
      <Text
        size='sm'
        c='dimmed'
      >
        {label}
      </Text>
      {children}
    </Group>
  )
}

export function AiSettingsCard() {
  const settings = useAiSettings()
  const status = useAiStatus()
  const save = useSetAiSettings()
  const data = settings.data
  const st = status.data

  return (
    <Card withBorder>
      <Stack gap='md'>
        <Group gap='xs'>
          <IconSparkles size={20} />
          <Title order={4}>Локальна модель ШІ</Title>
        </Group>
        {settings.isPending ? (
          <Skeleton h={60} />
        ) : (
          <>
            <Switch
              size='md'
              label='Використовувати ШІ в системі'
              description='Вимкнений ШІ: пояснення, поради і внесення документом працюють лише за правилами; пропозиції моделі приховано для всіх'
              checked={data?.enabled ?? false}
              disabled={!data?.available || save.isPending}
              onChange={e =>
                save.mutate(e.currentTarget.checked, {
                  onSuccess: r =>
                    notifications.show({ color: "success", message: r.enabled ? "ШІ увімкнено" : "ШІ вимкнено" }),
                  onError: err => notifications.show({ color: "danger", message: err.message }),
                })
              }
            />
            {data && !data.available && (
              <Alert
                color='warning'
                variant='light'
              >
                ШІ вимкнено в налаштуваннях середовища (AI_ENABLED=false). Увімкніть його в .env і перезапустіть бекенд.
              </Alert>
            )}
          </>
        )}
        {settings.error && (
          <Alert
            color='danger'
            variant='light'
          >
            {settings.error.message}
          </Alert>
        )}
        <Stack gap={6}>
          <Row label='Сервер моделі'>
            <Badge
              variant='light'
              color={st?.reachable ? "success" : "danger"}
            >
              {st ? (st.reachable ? "доступний" : "недоступний") : "—"}
            </Badge>
          </Row>
          <Row label='Моделі завантажено'>
            <Badge
              variant='light'
              color={st?.ready ? "success" : "warning"}
            >
              {st ? (st.ready ? "так" : "ні") : "—"}
            </Badge>
          </Row>
          <Row label='Модель відповідей'>
            <Text size='sm'>{st?.chatModel || "—"}</Text>
          </Row>
          <Row label='Модель пошуку'>
            <Text size='sm'>{st?.embedModel || "—"}</Text>
          </Row>
        </Stack>
      </Stack>
    </Card>
  )
}
