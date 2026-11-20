import { Stack, Table, Text } from "@mantine/core"
import type { PeerStats } from "@/shared/api"

import { formatDate, formatNumber } from "@/shared/lib"
import { QueryError, Section } from "@/shared/ui"
import { usePeers } from "../api"

const pct = (v: number | null) => (v === null ? "—" : `${formatNumber(v)} %`)
const days = (v: number | null) => (v === null ? "—" : `${formatNumber(v)} дн.`)

const metrics: { key: keyof PeerStats; label: string; hint: string; format: (v: number | null) => string }[] = [
  { key: "donePercent", label: "Виконано", hint: "Частка завдань зі статусом «Виконано»", format: pct },
  { key: "onTimePercent", label: "Вчасно", hint: "Серед виконаних — не пізніше строку", format: pct },
  {
    key: "firstPassPercent",
    label: "З першого разу",
    hint: "Частка результатів, погоджених без повернення на доопрацювання",
    format: pct,
  },
  { key: "returnRate", label: "Частка повернень", hint: "Повернення / усі рішення координатора", format: pct },
  { key: "avgDelayDays", label: "Сер. запізнення", hint: "Серед виконаних пізно і прострочених", format: days },
]

export function PeersView({ programId }: { programId?: string | null }) {
  const { data, isPending, error } = usePeers(programId)

  if (error) return <QueryError error={error} />

  return (
    <Stack gap='lg'>
      <Text
        size='sm'
        c='dimmed'
      >
        Порівняння з колегами, з якими ви виконуєте спільні заходи: лише середнє, без імен і показників окремих людей
        {data ? ` · ${data.programTitle} · станом на ${formatDate(data.asOf)}` : ""}.
      </Text>

      <Section
        title='Ви і колеги'
        subtitle={
          data
            ? data.sharedMeasures
              ? `Спільних заходів: ${data.sharedMeasures}`
              : "У вас немає спільних заходів з іншими виконавцями"
            : undefined
        }
        loading={isPending}
      >
        {data && !data.average && (
          <Text
            size='sm'
            c='dimmed'
            mb='sm'
          >
            Середнє показується, коли колег зі спільними заходами щонайменше {data.minGroup}: інакше воно розкриває
            показники конкретних людей.
          </Text>
        )}
        {data && (
          <Table.ScrollContainer minWidth={520}>
            <Table
              verticalSpacing='sm'
              fz='sm'
            >
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Показник</Table.Th>
                  <Table.Th ta='right'>Ви</Table.Th>
                  <Table.Th ta='right'>Колеги в середньому</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                <Table.Tr>
                  <Table.Td>Завдань</Table.Td>
                  <Table.Td ta='right'>{data.me.tasks}</Table.Td>
                  <Table.Td ta='right'>{data.average?.tasks ?? "—"}</Table.Td>
                </Table.Tr>
                {metrics.map(m => (
                  <Table.Tr key={m.key}>
                    <Table.Td>
                      <Text size='sm'>{m.label}</Text>
                      <Text
                        size='xs'
                        c='dimmed'
                      >
                        {m.hint}
                      </Text>
                    </Table.Td>
                    <Table.Td
                      ta='right'
                      fw={600}
                    >
                      {m.format(data.me[m.key] as number | null)}
                    </Table.Td>
                    <Table.Td ta='right'>
                      {data.average ? m.format(data.average[m.key] as number | null) : "—"}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Section>
    </Stack>
  )
}
