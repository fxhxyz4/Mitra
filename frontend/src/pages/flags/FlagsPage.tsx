import { Button, Grid, Group, SegmentedControl, Select, Stack } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconPlayerPlay } from "@tabler/icons-react"
import { useSearchParams } from "react-router"
import type { FlagStatus, FlagType } from "@/shared/api"

import { canManage } from "@/features/auth"
import { FlagsByType, useCoordinatorDashboard, useRunDailyJob } from "@/features/dashboards"
import { FlagList, useFlags } from "@/features/flags"
import { useDictionaries, useSession } from "@/shared/api"
import { flagMeta, flagOrder } from "@/shared/lib"
import { PageHeader, QueryError, Section, Seo } from "@/shared/ui"

export function FlagsPage() {
  const { user } = useSession()
  const [params, setParams] = useSearchParams()
  const type = (params.get("type") as FlagType | null) ?? undefined
  const status = (params.get("status") as FlagStatus | "ALL" | null) ?? "OPEN"
  const flags = useFlags({ status, type })
  const dashboard = useCoordinatorDashboard()
  const dictionaries = useDictionaries()
  const job = useRunDailyJob()

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <>
      <Seo title='Risk Flags' />
      <PageHeader
        title='Risk Flags'
        description='Явні правила R1, R4, R6, E1 і F1–F3: що спрацювало, на яких даних і чому. Статус заходу прапорці не змінюють.'
        actions={
          canManage(user?.role) && (
            <Button
              variant='default'
              leftSection={<IconPlayerPlay size={16} />}
              loading={job.isPending}
              onClick={() =>
                job.mutate(undefined, {
                  onSuccess: r =>
                    notifications.show({
                      color: "success",
                      title: "Перевірку виконано",
                      message: `Нових прапорців: ${r.flagsOpened}, знято автоматично: ${r.flagsAutoResolved}, рекомендацій: ${r.recommendationsCreated}`,
                    }),
                  onError: e => notifications.show({ color: "danger", message: e.message }),
                })
              }
            >
              Запустити перевірку (06:00)
            </Button>
          )
        }
      />
      <QueryError error={flags.error} />
      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Stack gap='md'>
            <Group gap='sm'>
              <SegmentedControl
                value={status}
                onChange={v => update("status", v === "OPEN" ? null : v)}
                data={[
                  { value: "OPEN", label: "Відкриті" },
                  { value: "RESOLVED", label: "Зняті" },
                  { value: "ALL", label: "Усі" },
                ]}
              />
              <Select
                placeholder='Усі типи'
                clearable
                value={type ?? null}
                onChange={v => update("type", v)}
                data={flagOrder.map(t => ({ value: t, label: `${flagMeta[t].rule} · ${flagMeta[t].label}` }))}
                w={280}
              />
            </Group>
            <Section
              title={`Прапорців: ${flags.data?.length ?? 0}`}
              loading={flags.isPending}
            >
              <FlagList
                flags={flags.data ?? []}
                role={user?.role ?? null}
              />
            </Section>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap='lg'>
            <Section
              title='Відкриті за типами'
              loading={dashboard.isPending}
            >
              {dashboard.data && <FlagsByType counts={dashboard.data.flagsByType} />}
            </Section>
            <Section
              title='Правила'
              loading={dictionaries.isPending}
            >
              <Stack gap='xs'>
                {dictionaries.data?.flagRules.map(r => (
                  <div key={r.type}>
                    <strong>{r.ruleCode}</strong> · {r.description}
                  </div>
                ))}
              </Stack>
            </Section>
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  )
}
