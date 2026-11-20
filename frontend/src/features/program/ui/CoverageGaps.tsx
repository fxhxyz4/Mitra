import { Anchor, Badge, Button, Card, Group, Skeleton, Stack, Text, ThemeIcon, Title } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconCircleCheck, IconSparkles } from "@tabler/icons-react"
import { Link } from "react-router"
import type { CoverageGap, MeasureDraft } from "@/shared/api"

import { useAiAccess } from "@/shared/api"
import { paths } from "@/shared/config"
import { levelMeta } from "@/shared/lib"
import { measurePath } from "@/shared/ui"
import { useCoverage, useRiskMeasureDraft } from "../api"

const ruleMeta: Record<CoverageGap["ruleCode"], { label: string; color: string }> = {
  C1: { label: "Ризик без заходів", color: "danger" },
  C2: { label: "Захід без ризику", color: "warning" },
  C3: { label: "Без індикатора", color: "gray" },
}

type CoverageGapsProps = {
  programId: string
  canDraft: boolean
  onDraft: (draft: MeasureDraft) => void
}

export function CoverageGaps({ programId, canDraft, onDraft }: CoverageGapsProps) {
  const { data, isPending } = useCoverage(programId)
  const ai = useAiAccess()
  const draft = useRiskMeasureDraft()

  if (isPending) return <Skeleton h={120} />
  if (!data) return null

  return (
    <Card withBorder>
      <Stack gap='sm'>
        <Group justify='space-between'>
          <Title
            order={2}
            size='h4'
          >
            Прогалини покриття ризиків
          </Title>
          <Badge
            variant='light'
            color={data.length ? "warning" : "success"}
          >
            {data.length ? `${data.length} знайдено` : "Немає"}
          </Badge>
        </Group>
        {data.length === 0 && (
          <Group gap='xs'>
            <ThemeIcon
              color='success'
              variant='light'
              size='sm'
            >
              <IconCircleCheck size={14} />
            </ThemeIcon>
            <Text
              size='sm'
              c='dimmed'
            >
              Кожен ризик має захід, а кожен захід розділу 2 — ризик та індикатор.
            </Text>
          </Group>
        )}
        {data.map(g => {
          const key = `${g.ruleCode}-${g.riskId ?? ""}-${g.measureId ?? ""}`
          const loading = draft.isPending && draft.variables?.riskId === g.riskId
          return (
            <Group
              key={key}
              justify='space-between'
              wrap='nowrap'
              align='flex-start'
            >
              <Stack
                gap={4}
                style={{ minWidth: 0 }}
              >
                <Group gap={6}>
                  <Badge
                    size='sm'
                    variant='light'
                    color={ruleMeta[g.ruleCode].color}
                  >
                    {g.ruleCode} · {ruleMeta[g.ruleCode].label}
                  </Badge>
                  {g.level && (
                    <Badge
                      size='sm'
                      variant='outline'
                      color={levelMeta[g.level].color}
                    >
                      {levelMeta[g.level].label}
                    </Badge>
                  )}
                  {g.riskId && g.riskCode && (
                    <Anchor
                      component={Link}
                      to={`${paths.riskModel}?risk=${g.riskId}`}
                      size='sm'
                    >
                      {g.riskCode}
                    </Anchor>
                  )}
                  {g.measureId && g.measureCode && (
                    <Anchor
                      component={Link}
                      to={measurePath(g.measureId)}
                      size='sm'
                    >
                      Захід {g.measureCode}
                    </Anchor>
                  )}
                </Group>
                <Text size='sm'>{g.explanation}</Text>
              </Stack>
              {g.ruleCode === "C1" && g.riskId && canDraft && ai.model && (
                <Button
                  size='compact-sm'
                  variant='light'
                  color='violet'
                  leftSection={<IconSparkles size={14} />}
                  loading={loading}
                  disabled={draft.isPending && !loading}
                  onClick={() =>
                    draft.mutate(
                      { riskId: g.riskId as string, programId },
                      {
                        onSuccess: onDraft,
                        onError: e => notifications.show({ color: "danger", message: e.message }),
                      }
                    )
                  }
                >
                  Чернетка заходу
                </Button>
              )}
            </Group>
          )
        })}
      </Stack>
    </Card>
  )
}
