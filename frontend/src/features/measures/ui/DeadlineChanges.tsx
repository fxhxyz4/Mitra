import { useState } from "react"
import { Alert, Button, Group, Modal, Stack, Text, Textarea, Timeline } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconCalendarRepeat } from "@tabler/icons-react"
import type { MeasureDetail } from "@/shared/api"

import { formatDate } from "@/shared/lib"
import { DateField } from "@/shared/ui"
import { usePostponeMeasure } from "../api/queries"

type DeadlineChangesProps = { measure: MeasureDetail; canPostpone: boolean }

export function DeadlineChanges({ measure, canPostpone }: DeadlineChangesProps) {
  const [opened, setOpened] = useState(false)
  const [form, setForm] = useState<{ newDeadline: string | null; reason: string }>({ newDeadline: null, reason: "" })
  const postpone = usePostponeMeasure(measure.id)
  const changes = measure.deadlineChanges
  if (measure.isPermanent || (!changes.length && !canPostpone)) return null

  const valid = Boolean(form.newDeadline) && form.reason.trim().length >= 10
  return (
    <Stack gap='xs'>
      <Group justify='space-between'>
        <Text
          size='xs'
          c='dimmed'
          tt='uppercase'
          fw={600}
          lts={0.3}
        >
          Перенесення строку
        </Text>
        {canPostpone && (
          <Button
            size='xs'
            variant='default'
            leftSection={<IconCalendarRepeat size={14} />}
            onClick={() => setOpened(true)}
          >
            Перенести строк
          </Button>
        )}
      </Group>
      {changes.length ? (
        <Timeline
          bulletSize={14}
          lineWidth={2}
        >
          {changes.map(c => (
            <Timeline.Item
              key={c.id}
              title={`${formatDate(c.oldDeadline)} → ${formatDate(c.newDeadline)}`}
            >
              <Text size='sm'>{c.reason}</Text>
              <Text
                size='xs'
                c='dimmed'
              >
                Рішення {formatDate(c.decidedOn)}
                {c.decidedByName ? ` · ${c.decidedByName}` : ""}
              </Text>
            </Timeline.Item>
          ))}
        </Timeline>
      ) : (
        <Text
          size='sm'
          c='dimmed'
        >
          Строк не переносили.
        </Text>
      )}
      {changes.length >= 2 && (
        <Alert
          variant='light'
          color='orange'
        >
          Строк переносили {changes.length} рази — прапорець R6a «Строк переносили двічі і більше».
        </Alert>
      )}

      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title='Перенести строк заходу'
      >
        <Stack gap='sm'>
          <Text
            size='sm'
            c='dimmed'
          >
            Це внутрішнє рішення координатора: строк у затвердженій програмі ({formatDate(measure.plannedDeadline)}) не
            змінюється, прострочення і звіт НАЗК рахуються за ним, а нагадування — за новим строком. Чинний внутрішній
            строк: {formatDate(measure.internalDeadline ?? measure.plannedDeadline)}.
          </Text>
          <DateField
            label='Новий строк'
            required
            value={form.newDeadline}
            onChange={newDeadline => setForm(f => ({ ...f, newDeadline }))}
          />
          <Textarea
            label='Причина перенесення'
            placeholder='Напр.: постачальник переніс строк поставки обладнання, лист № 41 від 20.03.2026'
            required
            autosize
            minRows={2}
            value={form.reason}
            onChange={e => {
              const reason = e.currentTarget.value
              setForm(f => ({ ...f, reason }))
            }}
          />
          <Group justify='flex-end'>
            <Button
              disabled={!valid}
              loading={postpone.isPending}
              onClick={() =>
                form.newDeadline &&
                postpone.mutate(
                  { newDeadline: form.newDeadline, reason: form.reason.trim() },
                  {
                    onSuccess: () => {
                      setOpened(false)
                      setForm({ newDeadline: null, reason: "" })
                      notifications.show({ color: "success", message: "Строк перенесено, рішення записано в журнал" })
                    },
                    onError: e => notifications.show({ color: "danger", message: e.message }),
                  }
                )
              }
            >
              Перенести
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
