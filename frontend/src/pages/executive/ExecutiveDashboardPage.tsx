import { Anchor, Grid, SimpleGrid, Stack, Text } from "@mantine/core"
import { IconAlarm, IconChecks, IconFlag, IconShieldCheck } from "@tabler/icons-react"
import { Link } from "react-router"

import {
  FlagsByType,
  RiskHeatMap,
  RiskStateList,
  StatusBar,
  StatusLegend,
  useExecutiveDashboard,
  WeeklyDigestCard,
} from "@/features/dashboards"
import { RecommendationCard } from "@/features/recommendations"
import { useSession } from "@/shared/api"
import { paths } from "@/shared/config"
import { formatDate } from "@/shared/lib"
import { KpiTile, MeasureList, measurePath, PageHeader, QueryError, Section, Seo, StatusBadge } from "@/shared/ui"

export function ExecutiveDashboardPage() {
  const { user } = useSession()
  const { data, isPending, error, refetch } = useExecutiveDashboard()
  const o = data?.overall

  return (
    <>
      <Seo title='Executive Dashboard' />
      <PageHeader
        title='Executive Dashboard'
        description='Головний показник — зміна стану корупційних ризиків, а не кількість закритих заходів'
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
            label='Ризиків зменшено'
            value={o ? `${o.risksReduced} з ${o.risksTotal}` : "—"}
            icon={IconShieldCheck}
            color='success'
            progress={o?.risksTotal ? (o.risksReduced / o.risksTotal) * 100 : 0}
            hint='Усі індикатори ризику покращились'
            loading={isPending}
          />
          <KpiTile
            label='Заходів виконано'
            value={o ? `${o.donePercent}%` : "—"}
            icon={IconChecks}
            progress={o?.donePercent}
            hint={o ? `${o.byStatus.DONE} з ${o.total}` : undefined}
            loading={isPending}
          />
          <KpiTile
            label='Прострочено'
            value={o?.overdue ?? 0}
            icon={IconAlarm}
            color='danger'
            loading={isPending}
          />
          <KpiTile
            label='Відкриті Risk Flags'
            value={o?.openFlags ?? 0}
            icon={IconFlag}
            color='orange'
            loading={isPending}
          />
        </SimpleGrid>

        <WeeklyDigestCard />

        {(o || isPending) && (
          <Section
            title='Загальний стан програми'
            loading={isPending}
            skeletonHeight={44}
          >
            {o && (
              <Stack gap='sm'>
                <StatusBar
                  byStatus={o.byStatus}
                  total={o.total}
                />
                <StatusLegend byStatus={o.byStatus} />
              </Stack>
            )}
          </Section>
        )}

        <Section
          title='Стан корупційних ризиків: до і після'
          subtitle='База → поточне значення → ціль за індикаторами'
          loading={isPending}
        >
          {data && <RiskStateList risks={data.risks} />}
        </Section>

        <Grid gap='lg'>
          <Grid.Col span={12}>
            <Section
              title='Критичні заходи'
              subtitle='Високий ризик невиконання або «формальне закриття» / невиконання показника'
              loading={isPending}
              padding={0}
            >
              <MeasureList
                items={data?.critical ?? []}
                empty='Критичних заходів немає'
                extra={m =>
                  m.nonExecutionRisk?.reasons.length ? (
                    <Text
                      size='xs'
                      c='dimmed'
                    >
                      {m.nonExecutionRisk.reasons.join(" · ")}
                    </Text>
                  ) : null
                }
              />
            </Section>
          </Grid.Col>
          <Grid.Col span={12}>
            <SimpleGrid
              cols={{ base: 1, md: 2 }}
              spacing='lg'
            >
              <Section
                title='Найближчі контрольні строки'
                subtitle='30 днів'
                loading={isPending}
              >
                <Stack gap='xs'>
                  {data?.upcomingDeadlines.map(i => (
                    <Anchor
                      key={i.measureId}
                      component={Link}
                      to={measurePath(i.measureId)}
                      c='inherit'
                      underline='never'
                    >
                      <Text
                        size='sm'
                        lineClamp={1}
                      >
                        <b>{formatDate(i.date)}</b> · {i.code} {i.title}
                      </Text>
                      <StatusBadge
                        status={i.status}
                        size='xs'
                      />
                    </Anchor>
                  ))}
                  {!data?.upcomingDeadlines.length && (
                    <Text
                      size='sm'
                      c='dimmed'
                    >
                      Строків немає
                    </Text>
                  )}
                </Stack>
              </Section>
              <Section
                title='Risk Flags за типами'
                loading={isPending}
              >
                {data && <FlagsByType counts={data.flagsByType} />}
              </Section>
            </SimpleGrid>
          </Grid.Col>
        </Grid>

        <Section
          title='Карта ризику невиконання за підрозділами'
          subtitle='Без рейтингування: підрозділи за алфавітом, рівень — за явними правилами'
          loading={isPending}
        >
          {data && <RiskHeatMap units={data.units} />}
        </Section>

        <Section
          title={`Рекомендації на рішення: ${data?.recommendations.length ?? 0}`}
          actions={
            <Anchor
              component={Link}
              to={paths.recommendations}
              size='sm'
            >
              Усі рекомендації
            </Anchor>
          }
          loading={isPending}
        >
          <SimpleGrid
            cols={{ base: 1, md: 2 }}
            spacing='md'
          >
            {data?.recommendations.slice(0, 4).map(r => (
              <RecommendationCard
                key={r.id}
                rec={r}
                canDecide={user?.role === "HEAD"}
              />
            ))}
          </SimpleGrid>
          {!data?.recommendations.length && (
            <Text
              size='sm'
              c='dimmed'
            >
              Нових рекомендацій немає
            </Text>
          )}
        </Section>
      </Stack>
    </>
  )
}
