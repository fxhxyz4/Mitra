import { useState } from "react"
import { Badge, Button, Group, Modal, Progress, Stack, Text, UnstyledButton } from "@mantine/core"
import type { ReportDraft, ReportDraftWithFile } from "@/shared/api"

import { formatPeriod } from "@/shared/lib"
import { AiNote, DocumentDrop } from "@/shared/ui"
import { useIntakeReport } from "../api/queries"
import { IntakeError } from "./IntakeError"

export type ChosenDraft = ReportDraftWithFile & { measureId: string }

type ReportIntakeProps = {
  onDraft: (draft: ChosenDraft) => void
  period?: string | null
  compact?: boolean
}

export function ReportIntake({ onDraft, period, compact }: ReportIntakeProps) {
  const intake = useIntakeReport()
  const [pending, setPending] = useState<ReportDraftWithFile | null>(null)

  const handle = (file: File) =>
    intake.mutate(
      { file, period },
      {
        onSuccess: (draft: ReportDraft) => {
          const withFile = { ...draft, file }
          if (draft.measureId) onDraft({ ...withFile, measureId: draft.measureId })
          else setPending(withFile)
        },
      }
    )

  return (
    <Stack gap='xs'>
      <DocumentDrop
        onFile={handle}
        loading={intake.isPending}
        compact={compact}
        title='Перетягніть звіт виконавця (зразок A)'
        description='Система знайде захід, заповнить стан і опис — ви перевірите і надішлете'
      />
      <IntakeError
        error={intake.error}
        sample='A'
      />

      <Modal
        opened={Boolean(pending)}
        onClose={() => setPending(null)}
        title='До якого заходу цей звіт?'
        size='lg'
      >
        {pending && (
          <Stack gap='sm'>
            <Text
              size='sm'
              c='dimmed'
            >
              У документі «{pending.fileName}» захід не визначено однозначно. Оберіть зі схожих — найімовірніший зверху.
            </Text>
            {pending.candidates.map((c, i) => (
              <UnstyledButton
                key={`${c.measureId}-${c.period}`}
                onClick={() => {
                  onDraft({ ...pending, measureId: c.measureId, period: c.period })
                  setPending(null)
                }}
                p='sm'
                style={{
                  border: "1px solid var(--mantine-color-default-border)",
                  borderRadius: "var(--mantine-radius-md)",
                }}
              >
                <Group
                  justify='space-between'
                  wrap='nowrap'
                  align='flex-start'
                >
                  <Stack
                    gap={2}
                    style={{ minWidth: 0 }}
                  >
                    <Text
                      size='sm'
                      fw={600}
                    >
                      {c.code} {c.title}
                    </Text>
                    <Text
                      size='xs'
                      c='dimmed'
                    >
                      {formatPeriod(c.period)} · {c.reason}
                    </Text>
                  </Stack>
                  <Stack
                    gap={4}
                    align='flex-end'
                    w={90}
                    style={{ flexShrink: 0 }}
                  >
                    {i === 0 && (
                      <Badge
                        size='xs'
                        variant='light'
                      >
                        найкращий збіг
                      </Badge>
                    )}
                    <Progress
                      value={Math.round(c.score * 100)}
                      aria-label='Збіг із заходом'
                      w='100%'
                      size='sm'
                    />
                    <Text size='xs'>{Math.round(c.score * 100)}%</Text>
                  </Stack>
                </Group>
              </UnstyledButton>
            ))}
            {!pending.candidates.length && <Text size='sm'>Схожих заходів, що очікують звіту, не знайдено.</Text>}
            <AiNote>{pending.disclaimer}</AiNote>
            <Group justify='flex-end'>
              <Button
                variant='default'
                onClick={() => setPending(null)}
              >
                Скасувати
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  )
}
