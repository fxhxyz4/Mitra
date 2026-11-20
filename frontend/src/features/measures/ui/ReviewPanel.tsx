import { useState } from "react"
import { Alert, Button, Card, Group, NumberInput, Stack, Text, Textarea } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconArrowBackUp, IconCheck } from "@tabler/icons-react"
import type { MeasureDetail } from "@/shared/api"

import { formatNumber, isoDate } from "@/shared/lib"
import { DateField } from "@/shared/ui"
import { useApproveMeasure, useReturnMeasure } from "../api/queries"
import { EvidenceAdvice } from "./EvidenceAdvice"

export function ReviewPanel({ measure }: { measure: MeasureDetail }) {
  const [comment, setComment] = useState("")
  const [value, setValue] = useState<number | string>("")
  const [measuredAt, setMeasuredAt] = useState(isoDate(new Date()))
  const approve = useApproveMeasure(measure.id)
  const ret = useReturnMeasure(measure.id)
  const p = measure.currentPeriod
  const isNotDone = Boolean(p?.nonExecutionReason && !p.resultDescription)

  return (
    <Card>
      <Stack gap='md'>
        <div>
          <Text
            fw={600}
            size='lg'
          >
            Рішення координатора
          </Text>
          <Text
            size='sm'
            c='dimmed'
          >
            Погодьте виконання або поверніть на доопрацювання з обовʼязковим коментарем.
          </Text>
        </div>

        <Alert
          variant='light'
          color={isNotDone ? "danger" : "violet"}
          title={isNotDone ? "Виконавець повідомив про невиконання" : "Результат від виконавця"}
        >
          <Text
            size='sm'
            style={{ whiteSpace: "pre-wrap" }}
          >
            {p?.resultDescription || p?.nonExecutionReason || "—"}
          </Text>
        </Alert>

        {p && (
          <EvidenceAdvice
            key={p.id}
            periodId={p.id}
            onUseAdvice={text => setComment(c => (c.trim() ? `${c.trim()}\n${text}` : text))}
          />
        )}

        <Textarea
          label='Коментар'
          description='Обовʼязковий при поверненні (мінімум 3 символи)'
          autosize
          minRows={2}
          value={comment}
          onChange={e => setComment(e.currentTarget.value)}
        />

        {measure.indicator && !isNotDone && (
          <Group
            grow
            align='flex-end'
          >
            <NumberInput
              label={`Уточнити факт індикатора виконання: ${measure.indicator.name}`}
              description={`Виконавець вказав ${measure.indicator.current === null ? "—" : formatNumber(measure.indicator.current)} ${measure.indicator.unit} · ціль ${formatNumber(measure.indicator.target)} · необовʼязково`}
              value={value}
              onChange={setValue}
              decimalSeparator=','
            />
            <DateField
              label='Дата вимірювання'
              value={measuredAt}
              onChange={v => setMeasuredAt(v ?? isoDate(new Date()))}
            />
          </Group>
        )}

        <Group
          justify='flex-end'
          gap='sm'
        >
          <Button
            variant='light'
            color='orange'
            leftSection={<IconArrowBackUp size={16} />}
            disabled={comment.trim().length < 3}
            loading={ret.isPending}
            onClick={() =>
              ret.mutate(
                { comment: comment.trim(), period: measure.period ?? undefined },
                {
                  onSuccess: () => {
                    setComment("")
                    notifications.show({ color: "orange", message: "Повернено виконавцю на доопрацювання" })
                  },
                  onError: e => notifications.show({ color: "danger", message: e.message }),
                }
              )
            }
          >
            Повернути
          </Button>
          <Button
            color='success'
            leftSection={<IconCheck size={16} />}
            loading={approve.isPending}
            onClick={() =>
              approve.mutate(
                {
                  comment: comment.trim(),
                  period: measure.period ?? undefined,
                  indicatorValue: value === "" ? null : { value: String(value), measuredAt },
                },
                {
                  onSuccess: res => {
                    setComment("")
                    setValue("")
                    notifications.show({
                      color: "success",
                      message: res.status === "NOT_DONE" ? "Зафіксовано «Не виконано»" : "Виконання погоджено",
                    })
                  },
                  onError: e => notifications.show({ color: "danger", message: e.message }),
                }
              )
            }
          >
            {isNotDone ? "Погодити невиконання" : "Погодити"}
          </Button>
        </Group>
      </Stack>
    </Card>
  )
}
