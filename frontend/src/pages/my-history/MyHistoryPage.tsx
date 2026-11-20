import { useState } from "react"
import { Grid, NavLink, ScrollArea, Skeleton, Stack, Text } from "@mantine/core"

import { ActivityTimeline, useMeasure, useMeasures } from "@/features/measures"
import { EmptyState, PageHeader, QueryError, Section, Seo, StatusBadge } from "@/shared/ui"

function Details({ id }: { id: string }) {
  const measure = useMeasure(id)
  if (measure.isPending) return <Skeleton h={320} />
  if (!measure.data) return null
  return <ActivityTimeline measure={measure.data} />
}

export function MyHistoryPage() {
  const { data, isPending, error } = useMeasures({ mine: true })
  const [selected, setSelected] = useState<string | null>(null)
  const current = selected ?? data?.[0]?.id ?? null

  return (
    <>
      <Seo title='Історія і зауваження' />
      <PageHeader
        title='Історія і зауваження'
        description='Що і коли змінювалось у ваших заходах, коментарі координатора'
      />
      <QueryError error={error} />
      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Section
            title='Мої заходи'
            loading={isPending}
            padding='md'
          >
            <ScrollArea.Autosize mah={640}>
              <Stack gap={2}>
                {data?.map(m => (
                  <NavLink
                    key={m.id}
                    active={m.id === current}
                    onClick={() => setSelected(m.id)}
                    label={
                      <Text
                        size='sm'
                        lineClamp={2}
                      >
                        {m.code} {m.title}
                      </Text>
                    }
                    description={
                      <StatusBadge
                        status={m.status}
                        size='xs'
                        mt={4}
                      />
                    }
                    styles={{ root: { borderRadius: "var(--mantine-radius-md)" } }}
                  />
                ))}
              </Stack>
            </ScrollArea.Autosize>
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8 }}>
          {current ? (
            <Details
              key={current}
              id={current}
            />
          ) : (
            !isPending && <EmptyState title='Заходів немає' />
          )}
        </Grid.Col>
      </Grid>
    </>
  )
}
