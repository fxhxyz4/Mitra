import { useState } from "react"
import { Grid, SimpleGrid, Stack, Text } from "@mantine/core"
import { IconAlarm, IconArrowBackUp, IconBell, IconChecklist } from "@tabler/icons-react"
import { Link, useNavigate } from "react-router"

import { useExecutorDashboard } from "@/features/dashboards"
import { ReportIntake } from "@/features/measures"
import { useSession } from "@/shared/api"
import { formatDateTime } from "@/shared/lib"
import { KpiTile, measurePath, PageHeader, QueryError, Section, Seo } from "@/shared/ui"
import { ALL_MEASURES_ID, AllMeasuresSection } from "./AllMeasuresSection"
import { DeadlinesSection } from "./DeadlinesSection"
import type { MeasureFilter } from "./AllMeasuresSection"

const UPCOMING_ID = "upcoming-30-days"

export function MyMeasuresPage() {
  const { user } = useSession()
  const { data, isPending, error, refetch } = useExecutorDashboard()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<MeasureFilter>("all")
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
  const showAll = (next: MeasureFilter) => {
    setFilter(next)
    scrollTo(ALL_MEASURES_ID)
  }
  const comments = Object.fromEntries((data?.returned ?? []).map(r => [r.measure.id, r.comment]))

  return (
    <>
      <Seo title='Мої заходи' />
      <PageHeader
        title='Мої заходи'
        description={`${user?.displayName ?? ""} — заходи на найближчі 30 днів, повернені та прострочені`}
      />
      <QueryError
        error={error}
        onRetry={() => void refetch()}
      />

      <Stack gap='lg'>
        <SimpleGrid
          cols={{ base: 2, md: 4 }}
          spacing='md'
        >
          <KpiTile
            label='Усього моїх'
            value={data?.totalMine ?? 0}
            icon={IconChecklist}
            loading={isPending}
            onClick={() => showAll("all")}
          />
          <KpiTile
            label='На 30 днів'
            value={data?.upcoming.length ?? 0}
            icon={IconBell}
            color='cyan'
            loading={isPending}
            onClick={() => scrollTo(UPCOMING_ID)}
          />
          <KpiTile
            label='Повернені'
            value={data?.returned.length ?? 0}
            icon={IconArrowBackUp}
            color='orange'
            loading={isPending}
            onClick={() => showAll("returned")}
          />
          <KpiTile
            label='Прострочені'
            value={data?.overdue.length ?? 0}
            icon={IconAlarm}
            color='danger'
            loading={isPending}
            onClick={() => showAll("overdue")}
          />
        </SimpleGrid>

        <Section
          title='Внести звіт документом'
          subtitle='Перетягніть звіт виконавця — система знайде захід і заповнить форму, ви лише перевірите'
        >
          <ReportIntake onDraft={draft => navigate(measurePath(draft.measureId), { state: { draft } })} />
        </Section>

        <Grid gap='lg'>
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Stack gap='lg'>
              <div id={UPCOMING_ID}>
                <DeadlinesSection
                  upcoming={data?.upcoming ?? []}
                  loading={isPending}
                />
              </div>
              <AllMeasuresSection
                filter={filter}
                onFilterChange={setFilter}
                comments={comments}
              />
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Section
              title='Нагадування'
              subtitle='За 7, 3 і 1 день до строку'
              loading={isPending}
            >
              <Stack gap='sm'>
                {data?.reminders.map(r => (
                  <Link
                    key={r.id}
                    to={measurePath(r.measureId)}
                    style={{ color: "inherit", textDecoration: "none" }}
                  >
                    <Text
                      size='sm'
                      fw={500}
                    >
                      {r.text}
                    </Text>
                    <Text
                      size='xs'
                      c='dimmed'
                    >
                      {formatDateTime(r.sendAt)}
                    </Text>
                  </Link>
                ))}
                {!data?.reminders.length && (
                  <Text
                    size='sm'
                    c='dimmed'
                  >
                    Нагадувань немає
                  </Text>
                )}
              </Stack>
            </Section>
          </Grid.Col>
        </Grid>
      </Stack>
    </>
  )
}
