import { Grid, Group, Stack, Table, Text } from "@mantine/core"

import { useDictionaries, useRisks } from "@/shared/api"
import { flagMeta, statusOrder } from "@/shared/lib"
import { IndicatorBlock, LevelBadge, PageHeader, QueryError, Section, Seo, StatusBadge } from "@/shared/ui"

export function AdminDictionariesPage() {
  const risks = useRisks()
  const dict = useDictionaries()

  return (
    <>
      <Seo title='Довідники' />
      <PageHeader
        title='Довідники'
        description='Реєстр корупційних ризиків з індикаторами, розділи програми, правила Risk Flags, статуси'
      />
      <QueryError error={risks.error ?? dict.error} />
      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Section
            title='Реєстр корупційних ризиків'
            loading={risks.isPending}
          >
            <Stack gap='lg'>
              {risks.data?.map(r => (
                <Stack
                  key={r.id}
                  gap='xs'
                >
                  <Group gap='xs'>
                    <Text fw={700}>{r.code}</Text>
                    <LevelBadge
                      level={r.level}
                      size='sm'
                    />
                  </Group>
                  <Text size='sm'>{r.description}</Text>
                  {r.indicators.map(i => (
                    <IndicatorBlock
                      key={i.id}
                      indicator={i}
                    />
                  ))}
                </Stack>
              ))}
            </Stack>
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Stack gap='lg'>
            <Section
              title='Розділи програми (НАЗК)'
              loading={dict.isPending}
            >
              <Stack gap='xs'>
                {dict.data?.sections.map(s => (
                  <Text
                    key={s.number}
                    size='sm'
                  >
                    <b>{s.number}.</b> {s.title}
                  </Text>
                ))}
              </Stack>
            </Section>
            <Section
              title='Правила Risk Flags'
              loading={dict.isPending}
            >
              <Table verticalSpacing='xs'>
                <Table.Tbody>
                  {dict.data?.flagRules.map(r => (
                    <Table.Tr key={r.type}>
                      <Table.Td
                        ff='monospace'
                        fw={600}
                      >
                        {r.ruleCode}
                      </Table.Td>
                      <Table.Td>{flagMeta[r.type]?.label}</Table.Td>
                      <Table.Td c='dimmed'>{r.description}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Section>
            <Section title='Життєвий цикл заходу'>
              <Group gap='xs'>
                {statusOrder.map(s => (
                  <StatusBadge
                    key={s}
                    status={s}
                  />
                ))}
              </Group>
            </Section>
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  )
}
