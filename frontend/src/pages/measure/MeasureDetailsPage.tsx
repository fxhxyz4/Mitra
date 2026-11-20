import { useState } from "react"
import { Alert, Anchor, Button, Grid, Group, Select, Skeleton, Stack, Tabs } from "@mantine/core"
import { IconArrowLeft, IconHourglass, IconPencil } from "@tabler/icons-react"
import { Link, useLocation, useParams } from "react-router"
import type { ChosenDraft } from "@/features/measures"

import { AiSuggest } from "@/features/ai"
import { FlagList } from "@/features/flags"
import {
  ActivityTimeline,
  EvidenceList,
  MeasureForm,
  MeasureSummary,
  ReviewPanel,
  SubmitForm,
  useMeasure,
} from "@/features/measures"
import { usePassport } from "@/features/program"
import { useSession } from "@/shared/api"
import { paths } from "@/shared/config"
import { formatPeriod } from "@/shared/lib"
import { QueryError, Section, Seo } from "@/shared/ui"

export function MeasureDetailsPage() {
  const { id = "" } = useParams()
  const { user } = useSession()
  const location = useLocation()
  const navDraft = (location.state as { draft?: ChosenDraft } | null)?.draft
  const draft = navDraft && navDraft.measureId === id ? navDraft : null
  const [period, setPeriod] = useState<string | undefined>(draft?.period ?? undefined)
  const [editing, setEditing] = useState(false)
  const { data: m, isPending, error, refetch } = useMeasure(id, period)
  const isExecutor = user?.role === "EXECUTOR"
  const canEdit = m?.allowedActions.includes("edit") ?? false
  const passport = usePassport(canEdit ? m?.programId : undefined)
  const canSubmit = m?.allowedActions.includes("submit") ?? false
  const canReview = m?.allowedActions.includes("approve") ?? false

  return (
    <>
      <Seo title={m ? `Захід ${m.code}` : "Захід"} />
      <Group
        justify='space-between'
        mb='md'
      >
        <Anchor
          component={Link}
          to={isExecutor ? paths.my : canReview ? paths.review : paths.program}
          size='sm'
        >
          <Group gap={4}>
            <IconArrowLeft size={14} />
            {isExecutor ? "Мої заходи" : canReview ? "Черга на перевірку" : "Паспорт програми"}
          </Group>
        </Anchor>
        <Group gap='xs'>
          {m && m.periods.length > 1 && (
            <Select
              size='xs'
              w={190}
              data={m.periods.map(p => ({ value: p.period, label: formatPeriod(p.period) }))}
              value={period ?? m.period}
              onChange={v => setPeriod(v ?? undefined)}
              allowDeselect={false}
              aria-label='Період'
            />
          )}
          {canEdit && (
            <Button
              size='xs'
              variant='default'
              leftSection={<IconPencil size={14} />}
              onClick={() => setEditing(true)}
              disabled={!passport.data}
            >
              Редагувати
            </Button>
          )}
        </Group>
      </Group>

      <QueryError
        error={error}
        onRetry={() => void refetch()}
      />
      {isPending && <Skeleton h={360} />}

      {m && (
        <Grid gap='lg'>
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <Stack gap='lg'>
              <MeasureSummary
                measure={m}
                canPostpone={user?.role === "COORDINATOR"}
              />
              {canSubmit && (
                <SubmitForm
                  key={`${m.id}-${m.status}-${m.period}-${draft?.fileSha256 ?? ""}`}
                  measure={m}
                  initialDraft={draft}
                  aiSlot={({ text, setText }) => (
                    <AiSuggest
                      measureId={m.id}
                      text={text}
                      onApply={setText}
                    />
                  )}
                />
              )}
              {isExecutor && m.status === "ON_REVIEW" && (
                <Alert
                  color='violet'
                  variant='light'
                  icon={<IconHourglass size={18} />}
                  title='На перевірці у координатора'
                >
                  Редагування недоступне до рішення координатора.
                </Alert>
              )}
              {canReview && (
                <ReviewPanel
                  key={`${m.id}-${m.status}`}
                  measure={m}
                />
              )}
              {!isExecutor ? (
                <Section title='Події'>
                  <Tabs defaultValue='activity'>
                    <Tabs.List mb='md'>
                      <Tabs.Tab value='activity'>Історія і зауваження</Tabs.Tab>
                      <Tabs.Tab value='flags'>Risk Flags ({m.flags.length})</Tabs.Tab>
                    </Tabs.List>
                    <Tabs.Panel value='activity'>
                      <ActivityTimeline
                        measure={m}
                        plain
                      />
                    </Tabs.Panel>
                    <Tabs.Panel value='flags'>
                      <FlagList
                        flags={m.flags}
                        role={user?.role ?? null}
                      />
                    </Tabs.Panel>
                  </Tabs>
                </Section>
              ) : null}
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <Stack gap='lg'>
              <EvidenceList measure={m} />
              {isExecutor && <ActivityTimeline measure={m} />}
            </Stack>
          </Grid.Col>
        </Grid>
      )}

      {m && passport.data && (
        <MeasureForm
          opened={editing}
          onClose={() => setEditing(false)}
          sections={passport.data.sections}
          measure={m}
          locked={passport.data.status !== "DRAFT"}
        />
      )}
    </>
  )
}
