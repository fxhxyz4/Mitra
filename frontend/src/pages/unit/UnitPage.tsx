import { Anchor, Group, SimpleGrid, Stack, Text } from "@mantine/core"
import { IconAlarm, IconArrowLeft, IconFlag, IconListCheck } from "@tabler/icons-react"
import { Link, useParams } from "react-router"

import { useUnitDashboard } from "@/features/dashboards"
import { paths } from "@/shared/config"
import { KpiTile, LevelBadge, MeasureList, PageHeader, QueryError, Section, Seo } from "@/shared/ui"

export function UnitPage() {
  const { id = "" } = useParams()
  const { data, isPending, error } = useUnitDashboard(id)

  return (
    <>
      <Seo title={data?.name ?? "Підрозділ"} />
      <Anchor
        component={Link}
        to={paths.dashboard}
        size='sm'
        mb='md'
        display='inline-block'
      >
        <Group gap={4}>
          <IconArrowLeft size={14} />
          Executive Dashboard
        </Group>
      </Anchor>
      <PageHeader
        title={data?.name ?? "Підрозділ"}
        description='Деталізація ризику невиконання по підрозділу'
        actions={
          data && (
            <LevelBadge
              level={data.cell.level}
              size='lg'
              prefix='Ризик невиконання'
            />
          )
        }
      />
      <QueryError error={error} />
      <Stack gap='lg'>
        <SimpleGrid
          cols={{ base: 1, sm: 3 }}
          spacing='md'
        >
          <KpiTile
            label='Заходів (відповідальний)'
            value={data?.cell.total ?? 0}
            icon={IconListCheck}
            loading={isPending}
          />
          <KpiTile
            label='Прострочено'
            value={data?.cell.overdue ?? 0}
            icon={IconAlarm}
            color='danger'
            loading={isPending}
          />
          <KpiTile
            label='Відкриті Risk Flags'
            value={data?.cell.openFlags ?? 0}
            icon={IconFlag}
            color='orange'
            loading={isPending}
          />
        </SimpleGrid>
        {data?.cell.reasons.length ? (
          <Section title='Чому такий рівень'>
            <Stack gap={4}>
              {data.cell.reasons.map(r => (
                <Text
                  key={r}
                  size='sm'
                >
                  • {r}
                </Text>
              ))}
            </Stack>
          </Section>
        ) : null}
        <Section
          title='Заходи підрозділу'
          loading={isPending}
          padding={0}
        >
          <MeasureList
            items={data?.measures ?? []}
            extra={m =>
              m.nonExecutionRisk && m.nonExecutionRisk.level !== "LOW" ? (
                <Group gap={6}>
                  <LevelBadge
                    level={m.nonExecutionRisk.level}
                    size='xs'
                    prefix='Ризик'
                  />
                  <Text
                    size='xs'
                    c='dimmed'
                  >
                    {m.nonExecutionRisk.reasons.join(" · ")}
                  </Text>
                </Group>
              ) : null
            }
          />
        </Section>
      </Stack>
    </>
  )
}
