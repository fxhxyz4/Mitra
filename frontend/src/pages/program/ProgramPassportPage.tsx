import { useMemo, useState } from "react"
import { Badge, Button, Group, SegmentedControl, SimpleGrid, Skeleton, Stack, TextInput } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import {
  IconAlarm,
  IconChecks,
  IconListCheck,
  IconPlus,
  IconRosetteDiscountCheck,
  IconSearch,
  IconShieldCheck,
} from "@tabler/icons-react"
import type { MeasureDraft, MeasureListItem } from "@/shared/api"

import { canManage, STAFF } from "@/features/auth"
import { MeasureForm } from "@/features/measures"
import { CoverageGaps, PassportView, useApproveProgram, usePassport } from "@/features/program"
import { usePrograms, useSession } from "@/shared/api"
import { formatDate, matchScore, useDebouncedSearch } from "@/shared/lib"
import { KpiTile, MeasureListModal, PageHeader, QueryError, Seo } from "@/shared/ui"

type Filter = "all" | "attention" | "review" | "done"

const matches = (m: MeasureListItem, filter: Filter, q: string) => {
  if (q && !matchScore(`${m.code} ${m.title} ${m.responsibleUnit ?? ""} ${m.risk?.code ?? ""}`, q)) return false
  if (filter === "attention")
    return (m.isOverdue && m.status !== "DONE") || m.openFlags.length > 0 || m.status === "RETURNED"
  if (filter === "review") return m.status === "ON_REVIEW"
  if (filter === "done") return m.status === "DONE" || m.status === "PARTIAL" || m.status === "NOT_DONE"
  return true
}

export function ProgramPassportPage() {
  const { user } = useSession()
  const programs = usePrograms()
  const program = programs.data?.find(p => p.status === "APPROVED") ?? programs.data?.[0]
  const { data, isPending, error } = usePassport(program?.id)
  const approve = useApproveProgram()
  const [filter, setFilter] = useState<Filter>("all")
  const search = useDebouncedSearch()
  const q = search.query
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<MeasureDraft | null>(null)
  const manage = canManage(user?.role)
  const staff = Boolean(user && STAFF.includes(user.role))
  const openCreate = (next: MeasureDraft | null) => {
    setDraft(next)
    setCreating(true)
  }

  const sections = useMemo(
    () => data?.sections.map(s => ({ ...s, measures: s.measures.filter(m => matches(m, filter, q)) })) ?? [],
    [
      data,
      filter,
      q,
    ]
  )
  const all = data?.sections.flatMap(s => s.measures) ?? []
  const doneItems = all.filter(m => m.status === "DONE")
  const overdueItems = all.filter(
    m => m.isOverdue && m.status !== "DONE" && m.status !== "PARTIAL" && m.status !== "NOT_DONE"
  )
  const flaggedItems = all.filter(m => m.openFlags.length)
  const done = doneItems.length
  const overdue = overdueItems.length
  const flagged = flaggedItems.length
  const tiles: Record<string, MeasureListItem[]> = {
    "Усі заходи": all,
    Виконано: doneItems,
    Прострочено: overdueItems,
    "З Risk Flags": flaggedItems,
  }
  const [tile, setTile] = useState<string | null>(null)

  return (
    <>
      <Seo title='Паспорт програми' />
      <PageHeader
        title='Паспорт програми'
        description={
          data ? (
            <>
              {data.title} · {data.orgUnitName} · {formatDate(data.periodStart)} – {formatDate(data.periodEnd)}
            </>
          ) : (
            "Електронний паспорт антикорупційної програми"
          )
        }
        actions={
          <>
            {data && (
              <Badge
                size='lg'
                variant='light'
                color={data.status === "APPROVED" ? "success" : "gray"}
                leftSection={<IconShieldCheck size={14} />}
              >
                {data.status === "APPROVED" ? "Затверджено" : data.status === "DRAFT" ? "Чернетка" : "Архів"}
              </Badge>
            )}
            {manage && data?.status === "DRAFT" && (
              <Button
                variant='light'
                color='success'
                leftSection={<IconRosetteDiscountCheck size={16} />}
                loading={approve.isPending}
                onClick={() =>
                  approve.mutate(data.id, {
                    onSuccess: () => notifications.show({ color: "success", message: "Програму затверджено" }),
                    onError: e => notifications.show({ color: "danger", message: e.message }),
                  })
                }
              >
                Затвердити
              </Button>
            )}
            {manage && data && (
              <Button
                leftSection={<IconPlus size={16} />}
                onClick={() => openCreate(null)}
              >
                Новий захід
              </Button>
            )}
          </>
        }
      />
      <QueryError error={error ?? programs.error} />

      <Stack gap='lg'>
        <SimpleGrid
          cols={{ base: 2, md: 4 }}
          spacing='md'
        >
          <KpiTile
            label='Заходів'
            onClick={() => setTile("Усі заходи")}
            value={all.length}
            icon={IconListCheck}
            loading={isPending}
          />
          <KpiTile
            label='Виконано'
            onClick={() => setTile("Виконано")}
            value={done}
            icon={IconChecks}
            color='success'
            progress={all.length ? (done / all.length) * 100 : 0}
            loading={isPending}
          />
          <KpiTile
            label='Прострочено'
            onClick={() => setTile("Прострочено")}
            value={overdue}
            icon={IconAlarm}
            color='danger'
            loading={isPending}
          />
          <KpiTile
            label='З Risk Flags'
            onClick={() => setTile("З Risk Flags")}
            value={flagged}
            icon={IconShieldCheck}
            color='orange'
            loading={isPending}
          />
        </SimpleGrid>
        <MeasureListModal
          title={tile}
          items={tile ? (tiles[tile] ?? []) : []}
          onClose={() => setTile(null)}
        />

        <Group
          justify='space-between'
          gap='sm'
        >
          <SegmentedControl
            value={filter}
            onChange={v => setFilter(v as Filter)}
            data={[
              { value: "all", label: "Усі" },
              { value: "attention", label: "Потребують уваги" },
              { value: "review", label: "На перевірці" },
              { value: "done", label: "Завершені" },
            ]}
          />
          <TextInput
            placeholder='Пошук: номер, назва, підрозділ, ризик'
            leftSection={<IconSearch size={16} />}
            value={search.value}
            onChange={e => search.setValue(e.currentTarget.value)}
            aria-label='Пошук заходів'
            w={{ base: "100%", sm: 400 }}
          />
        </Group>

        {staff && data && (
          <CoverageGaps
            programId={data.id}
            canDraft={manage}
            onDraft={openCreate}
          />
        )}

        {isPending ? <Skeleton h={420} /> : <PassportView sections={sections} />}
      </Stack>

      {data && (
        <MeasureForm
          opened={creating}
          onClose={() => setCreating(false)}
          sections={data.sections}
          programId={data.id}
          draft={draft}
        />
      )}
    </>
  )
}
