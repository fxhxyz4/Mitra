import { useState } from "react"
import { Anchor, Button, ScrollArea, Table, Text } from "@mantine/core"
import { IconPlus } from "@tabler/icons-react"
import { Link } from "react-router"

import { RiskRegisterForm } from "@/features/risk-model"
import { useRisks, useSession } from "@/shared/api"
import { paths } from "@/shared/config"
import { formatNumber } from "@/shared/lib"
import { EmptyState, LevelBadge, PageHeader, QueryError, Section, Seo } from "@/shared/ui"

export function RiskRegisterPage() {
  const { user } = useSession()
  const { data, isPending, error, refetch } = useRisks()
  const [adding, setAdding] = useState(false)
  const canCreate = user?.role === "COORDINATOR"

  return (
    <>
      <Seo title='Реєстр ризиків' />
      <PageHeader
        title='Реєстр корупційних ризиків'
        description='Ризики, бали ймовірності й наслідків від робочої групи і індикатори, за якими видно, чи ризик зменшується'
        actions={
          canCreate && (
            <Button
              leftSection={<IconPlus size={16} />}
              onClick={() => setAdding(true)}
            >
              Додати ризик
            </Button>
          )
        }
      />
      <QueryError
        error={error}
        onRetry={() => void refetch()}
      />
      <Section
        title='Ризики'
        subtitle={
          data ? `${data.length} у реєстрі · без заходів: ${data.filter(r => !r.measureCount).length}` : undefined
        }
        loading={isPending}
        padding={0}
      >
        {data && !data.length ? (
          <EmptyState
            title='Реєстр порожній'
            text='Додайте перший ризик за результатами оцінки робочої групи'
          />
        ) : (
          <ScrollArea type='auto'>
            <Table
              miw={900}
              verticalSpacing='sm'
              highlightOnHover
            >
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Ризик</Table.Th>
                  <Table.Th>Процес · власник</Table.Th>
                  <Table.Th>L·C</Table.Th>
                  <Table.Th>Індикатор ризику</Table.Th>
                  <Table.Th>Заходів</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data?.map(r => (
                  <Table.Tr key={r.id}>
                    <Table.Td maw={360}>
                      <Anchor
                        component={Link}
                        to={`${paths.riskModel}?risk=${r.id}`}
                        fw={600}
                      >
                        {r.code}
                      </Anchor>
                      <Text size='sm'>{r.description}</Text>
                      {r.content && (
                        <Text
                          size='xs'
                          c='dimmed'
                          lineClamp={2}
                        >
                          {r.content}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td maw={220}>
                      <Text size='sm'>{r.process || "—"}</Text>
                      <Text
                        size='xs'
                        c='dimmed'
                      >
                        {r.ownerUnitName ?? "власника не вказано"}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text
                        size='sm'
                        fw={600}
                      >
                        {r.probability && r.impact ? `${r.probability}·${r.impact} = ${r.score}` : "—"}
                      </Text>
                      <LevelBadge
                        level={r.level}
                        size='xs'
                      />
                    </Table.Td>
                    <Table.Td maw={280}>
                      {r.indicators.length ? (
                        r.indicators.map(i => (
                          <div key={i.id}>
                            <Text
                              size='sm'
                              lineClamp={2}
                            >
                              {i.name}
                            </Text>
                            <Text
                              size='xs'
                              c='dimmed'
                            >
                              {formatNumber(i.baseline)} → {formatNumber(i.target)} {i.unit} · зараз{" "}
                              {formatNumber(i.current)}
                            </Text>
                          </div>
                        ))
                      ) : (
                        <Text
                          size='sm'
                          c='danger'
                        >
                          Немає — зменшення ризику не оцінити
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text
                        size='sm'
                        c={r.measureCount ? undefined : "danger"}
                        fw={600}
                      >
                        {r.measureCount ?? 0}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
      </Section>
      {canCreate && (
        <RiskRegisterForm
          opened={adding}
          onClose={() => setAdding(false)}
        />
      )}
    </>
  )
}
