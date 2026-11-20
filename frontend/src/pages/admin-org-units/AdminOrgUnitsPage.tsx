import { useState } from "react"
import { Button, Group, Stack, Text, TextInput } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconBuilding, IconPlus } from "@tabler/icons-react"
import type { OrgUnit } from "@/shared/api"

import { useCreateOrgUnit } from "@/features/admin"
import { useOrgUnits } from "@/shared/api"
import { PageHeader, QueryError, SearchSelect, Section, Seo } from "@/shared/ui"

function Tree({ units, parentId, depth }: { units: OrgUnit[]; parentId: string | null; depth: number }) {
  const children = units.filter(u => (u.parentId ?? null) === parentId).sort((a, b) => a.name.localeCompare(b.name))
  return (
    <>
      {children.map(u => (
        <div key={u.id}>
          <Group
            gap='xs'
            py={6}
            pl={depth * 24}
          >
            <IconBuilding
              size={16}
              stroke={1.6}
            />
            <Text
              size='sm'
              fw={depth === 0 ? 600 : 400}
            >
              {u.name}
            </Text>
          </Group>
          <Tree
            units={units}
            parentId={u.id}
            depth={depth + 1}
          />
        </div>
      ))}
    </>
  )
}

export function AdminOrgUnitsPage() {
  const { data = [], isPending, error } = useOrgUnits()
  const create = useCreateOrgUnit()
  const [name, setName] = useState("")
  const [parentId, setParentId] = useState<string | null>(null)
  const roots = data.filter(u => !u.parentId || !data.some(p => p.id === u.parentId))

  return (
    <>
      <Seo title='Підрозділи' />
      <PageHeader
        title='Підрозділи'
        description='Структура органу: відповідальні та співвиконавці заходів'
      />
      <QueryError error={error} />
      <Stack gap='lg'>
        <Section title='Додати підрозділ'>
          <form
            onSubmit={e => {
              e.preventDefault()
              if (!name.trim()) return
              create.mutate(
                { name: name.trim(), parentId },
                {
                  onSuccess: () => {
                    setName("")
                    notifications.show({ color: "success", message: "Підрозділ додано" })
                  },
                  onError: err => notifications.show({ color: "danger", message: err.message }),
                }
              )
            }}
          >
            <Group align='flex-end'>
              <TextInput
                label='Назва'
                value={name}
                onChange={e => setName(e.currentTarget.value)}
                style={{ flex: 1, minWidth: 240 }}
              />
              <SearchSelect
                label='Входить до'
                data={data.map(u => ({ value: u.id, label: u.name }))}
                value={parentId}
                onChange={setParentId}
                clearable
                w={300}
              />
              <Button
                type='submit'
                leftSection={<IconPlus size={16} />}
                loading={create.isPending}
              >
                Додати
              </Button>
            </Group>
          </form>
        </Section>
        <Section
          title={`Підрозділів: ${data.length}`}
          loading={isPending}
        >
          {roots.map(r => (
            <div key={r.id}>
              <Group
                gap='xs'
                py={6}
              >
                <IconBuilding
                  size={16}
                  stroke={1.6}
                />
                <Text
                  size='sm'
                  fw={600}
                >
                  {r.name}
                </Text>
              </Group>
              <Tree
                units={data}
                parentId={r.id}
                depth={1}
              />
            </div>
          ))}
        </Section>
      </Stack>
    </>
  )
}
