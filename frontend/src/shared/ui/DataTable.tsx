import { useMemo, useState } from "react"
import { Badge, Button, Center, Group, Table, Text, Tooltip, UnstyledButton } from "@mantine/core"
import { IconChevronDown, IconChevronUp, IconRestore, IconSelector } from "@tabler/icons-react"
import type { ReactNode } from "react"

import { compareValues, nextSort } from "./dataTableSort"
import type { SortRule } from "./dataTableSort"

export type SortValue = string | number | boolean | null | undefined

export type Column<T> = {
  key: string
  label: ReactNode
  hint?: string
  render: (row: T) => ReactNode
  sort?: (row: T) => SortValue
  align?: "left" | "right" | "center"
  width?: number | string
}

type DataTableProps<T> = {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  initialSort?: SortRule
  onRowClick?: (row: T) => void
  selected?: string | null
  empty?: ReactNode
  pageSize?: number
  minWidth?: number
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  initialSort,
  onRowClick,
  selected,
  empty = "Немає даних",
  pageSize = 50,
  minWidth = 720,
}: DataTableProps<T>) {
  const initial = useMemo(() => (initialSort ? [initialSort] : []), [initialSort])
  const [sorts, setSorts] = useState<SortRule[]>(initial)
  const [shown, setShown] = useState(pageSize)
  const changed = JSON.stringify(sorts) !== JSON.stringify(initial)

  const sorted = useMemo(() => {
    const active = sorts.flatMap(s => {
      const get = columns.find(c => c.key === s.key)?.sort
      return get ? [{ get, desc: Boolean(s.desc) }] : []
    })
    if (!active.length) return rows
    return [...rows].sort((a, b) => {
      for (const { get, desc } of active) {
        const r = compareValues(get(a), get(b), desc)
        if (r) return r
      }
      return 0
    })
  }, [
    rows,
    columns,
    sorts,
  ])

  const onHeader = (key: string) => setSorts(s => nextSort(s, key, !changed))
  if (!rows.length)
    return (
      <Text
        c='dimmed'
        size='sm'
        ta='center'
        py='lg'
      >
        {empty}
      </Text>
    )

  return (
    <>
      <Group
        justify='flex-end'
        mb='xs'
      >
        <Button
          size='compact-xs'
          variant='subtle'
          leftSection={<IconRestore size={14} />}
          onClick={() => setSorts(initial)}
          disabled={!changed}
        >
          Скинути
        </Button>
      </Group>
      <Table.ScrollContainer minWidth={minWidth}>
        <Table
          striped
          highlightOnHover={Boolean(onRowClick)}
          stickyHeader
          verticalSpacing='xs'
          fz='sm'
        >
          <Table.Thead>
            <Table.Tr>
              {columns.map(c => {
                const at = sorts.findIndex(s => s.key === c.key)
                const rule = at >= 0 ? sorts[at] : undefined
                const SortIcon = !rule ? IconSelector : rule.desc ? IconChevronDown : IconChevronUp
                const label = (
                  <Text
                    fz='xs'
                    fw={600}
                    c={rule ? undefined : "dimmed"}
                    style={{ textDecoration: c.hint ? "underline dotted" : undefined }}
                  >
                    {c.label}
                  </Text>
                )
                return (
                  <Table.Th
                    key={c.key}
                    w={c.width}
                    ta={c.align}
                    aria-sort={rule ? (rule.desc ? "descending" : "ascending") : undefined}
                  >
                    {c.sort ? (
                      <UnstyledButton
                        onClick={() => onHeader(c.key)}
                        w='100%'
                      >
                        <Group
                          gap={4}
                          wrap='nowrap'
                          justify={c.align === "right" ? "flex-end" : c.align === "center" ? "center" : "flex-start"}
                        >
                          {c.hint ? <Tooltip label={c.hint}>{label}</Tooltip> : label}
                          <Center>
                            <SortIcon
                              size={14}
                              stroke={1.5}
                            />
                          </Center>
                          {rule && sorts.length > 1 && (
                            <Badge
                              size='xs'
                              circle
                              variant='light'
                            >
                              {at + 1}
                            </Badge>
                          )}
                        </Group>
                      </UnstyledButton>
                    ) : c.hint ? (
                      <Tooltip label={c.hint}>{label}</Tooltip>
                    ) : (
                      label
                    )}
                  </Table.Th>
                )
              })}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sorted.slice(0, shown).map(row => {
              const key = rowKey(row)
              return (
                <Table.Tr
                  key={key}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  bg={selected === key ? "var(--mantine-primary-color-light)" : undefined}
                  style={onRowClick ? { cursor: "pointer" } : undefined}
                >
                  {columns.map(c => (
                    <Table.Td
                      key={c.key}
                      ta={c.align}
                    >
                      {c.render(row)}
                    </Table.Td>
                  ))}
                </Table.Tr>
              )
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {sorted.length > shown && (
        <Group
          justify='center'
          mt='sm'
        >
          <Button
            variant='subtle'
            size='xs'
            onClick={() => setShown(n => n + pageSize)}
          >
            Показати ще ({sorted.length - shown})
          </Button>
        </Group>
      )}
    </>
  )
}
