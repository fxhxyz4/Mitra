import { Badge, Group, ScrollArea, Skeleton, Stack, Table, Text } from "@mantine/core"
import { Link } from "react-router"
import type { NazkReport } from "@/shared/api"

import { formatDate, formatPeriod } from "@/shared/lib"
import { measurePath } from "@/shared/ui"

const stateColor = (state: string) => (state === "Виконано" ? "success" : state === "Не виконано" ? "danger" : "gray")

export function NazkReportView({ report, loading }: { report?: NazkReport; loading?: boolean }) {
  if (loading || !report) return <Skeleton h={320} />
  return (
    <Stack gap='lg'>
      <Group gap='xs'>
        <Text fw={600}>{report.programTitle}</Text>
        <Text c='dimmed'>· {report.orgUnit}</Text>
        <Badge variant='light'>{formatPeriod(report.period)}</Badge>
        {report.hasRestrictedInfo && (
          <Badge
            color='danger'
            variant='light'
          >
            Обмежений доступ — лише паперова форма
          </Badge>
        )}
      </Group>
      {report.sections.map(s => (
        <Stack
          key={s.number}
          gap='xs'
        >
          <Text fw={600}>
            Розділ {s.number}. {s.title}
          </Text>
          <ScrollArea type='auto'>
            <Table
              striped
              withTableBorder
              verticalSpacing='xs'
              miw={1180}
              fz='sm'
            >
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={56}>№</Table.Th>
                  <Table.Th miw={300}>Захід</Table.Th>
                  <Table.Th miw={200}>Виконавці</Table.Th>
                  <Table.Th w={110}>Плановий строк</Table.Th>
                  <Table.Th w={110}>Фактичний строк</Table.Th>
                  <Table.Th w={170}>Стан виконання</Table.Th>
                  <Table.Th miw={280}>Опис результату / причини</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {s.measures.map(m => (
                  <Table.Tr key={m.measureId}>
                    <Table.Td ff='monospace'>{m.code}</Table.Td>
                    <Table.Td>
                      <Text
                        component={Link}
                        to={measurePath(m.measureId)}
                        size='sm'
                        style={{ color: "inherit" }}
                      >
                        {m.title}
                      </Text>
                    </Table.Td>
                    <Table.Td>{m.executors}</Table.Td>
                    <Table.Td>
                      {/^\d{4}-/.test(m.plannedDeadline) ? formatDate(m.plannedDeadline) : m.plannedDeadline}
                    </Table.Td>
                    <Table.Td>
                      {m.actualDeadline && /^\d{4}-/.test(m.actualDeadline)
                        ? formatDate(m.actualDeadline)
                        : (m.actualDeadline ?? "—")}
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        variant='light'
                        styles={{ label: { overflow: "visible", whiteSpace: "normal" } }}
                        h='auto'
                        py={2}
                        color={stateColor(m.state)}
                      >
                        {m.state}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{m.resultOrReason || "—"}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Stack>
      ))}
    </Stack>
  )
}
