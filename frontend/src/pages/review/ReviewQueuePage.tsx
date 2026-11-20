import { Grid, Stack, Text } from "@mantine/core"

import { useCoordinatorDashboard } from "@/features/dashboards"
import { formatPeriod } from "@/shared/lib"
import { MeasureList, PageHeader, QueryError, Section, Seo } from "@/shared/ui"

export function ReviewQueuePage() {
  const { data, isPending, error, refetch } = useCoordinatorDashboard()

  return (
    <>
      <Seo title='Черга на перевірку' />
      <PageHeader
        title='Черга на перевірку'
        description='Виконавці внесли результат — погодьте або поверніть з коментарем'
      />
      <QueryError
        error={error}
        onRetry={() => void refetch()}
      />
      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Section
            title={`На перевірці: ${data?.reviewQueue.length ?? 0}`}
            loading={isPending}
            padding={0}
          >
            <MeasureList
              items={data?.reviewQueue ?? []}
              empty='Черга порожня'
              emptyText='Нові результати від виконавців зʼявляться тут'
            />
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Section
            title='Готовність звіту'
            subtitle={data ? formatPeriod(data.reportReadiness.period) : undefined}
            loading={isPending}
          >
            {data && (
              <Stack gap='xs'>
                <Text
                  fz={34}
                  fw={700}
                >
                  {data.reportReadiness.percent}%
                </Text>
                <Text
                  size='sm'
                  c='dimmed'
                >
                  Готові {data.reportReadiness.ready} з {data.reportReadiness.total} заходів. Потребують закриття:
                </Text>
                {data.reportReadiness.missing.slice(0, 8).map(m => (
                  <Text
                    key={m.id}
                    size='sm'
                    lineClamp={1}
                  >
                    {m.code} {m.title}
                  </Text>
                ))}
              </Stack>
            )}
          </Section>
        </Grid.Col>
      </Grid>
    </>
  )
}
