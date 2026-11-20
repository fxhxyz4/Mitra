import { Group, SegmentedControl, Select } from "@mantine/core"
import { IconEye, IconZoomCheck } from "@tabler/icons-react"
import { useSearchParams } from "react-router"

import { AuditView, BasicView, PeersView } from "@/features/analytics"
import { usePrograms, useSession } from "@/shared/api"
import { formatDate } from "@/shared/lib"
import { PageHeader, Seo } from "@/shared/ui"

type Mode = "basic" | "extended"

export function AnalyticsPage() {
  const { user } = useSession()
  const role = user?.role
  const [params, setParams] = useSearchParams()
  const mode: Mode = params.get("mode") === "basic" ? "basic" : "extended"
  const programs = usePrograms()
  const programId = params.get("program")

  const update = (patch: Record<string, string | null>) =>
    setParams(
      p => {
        for (const [k, v] of Object.entries(patch)) {
          if (v) p.set(k, v)
          else p.delete(k)
        }
        return p
      },
      { replace: true }
    )

  const programOptions = (programs.data ?? []).map(p => ({
    value: p.id,
    label: `${p.title} (${formatDate(p.periodStart).slice(-4)}–${formatDate(p.periodEnd).slice(-4)})`,
  }))
  const programSelect = programOptions.length > 1 && (
    <Select
      aria-label='Програма'
      placeholder='Поточна програма'
      data={programOptions}
      value={programId}
      onChange={v => update({ program: v, period: null, unit: null, user: null })}
      clearable
      w={300}
    />
  )

  if (role === "EXECUTOR")
    return (
      <>
        <Seo title='Аналітика' />
        <PageHeader
          title='Аналітика'
          description='Як працюють колеги, з якими ви виконуєте спільні заходи'
          actions={programSelect}
        />
        <PeersView programId={programId} />
      </>
    )

  return (
    <>
      <Seo title={mode === "extended" ? "Аналітика · розширений режим" : "Аналітика"} />
      <PageHeader
        title='Аналітика'
        description={
          mode === "extended"
            ? "Виконання в розрізі підрозділів і виконавців, повернення на доопрацювання, хронологія рішень"
            : "Як іде виконання антикорупційної програми — коротко і зрозуміло"
        }
        actions={
          <Group gap='sm'>
            {programSelect}
            <SegmentedControl
              value={mode}
              onChange={v => update({ mode: v === "basic" ? "basic" : null, tab: null })}
              data={[
                {
                  value: "basic",
                  label: (
                    <Group
                      gap={6}
                      wrap='nowrap'
                    >
                      <IconEye size={16} />
                      Основний
                    </Group>
                  ),
                },
                {
                  value: "extended",
                  label: (
                    <Group
                      gap={6}
                      wrap='nowrap'
                    >
                      <IconZoomCheck size={16} />
                      Розширений
                    </Group>
                  ),
                },
              ]}
              aria-label='Режим аналітики'
            />
          </Group>
        }
      />
      {mode === "extended" ? (
        <AuditView
          programId={programId}
          withTrends={role === "ANALYST"}
        />
      ) : (
        <BasicView programId={programId} />
      )}
    </>
  )
}
