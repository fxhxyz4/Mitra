import { useState } from "react"
import { Badge, Button, Card, Code, Collapse, Group, List, Select, Stack, Text, Textarea } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconCheck, IconChecks, IconSparkles, IconX } from "@tabler/icons-react"
import { Link } from "react-router"
import type { Recommendation } from "@/shared/api"

import { session, useAiAccess } from "@/shared/api"
import { formatDate, isoDate } from "@/shared/lib"
import { AiNote, DateField, FlagBadge, LevelBadge, measurePath, RecBadge } from "@/shared/ui"
import {
  useCompleteRecommendation,
  useDecideRecommendation,
  useMeasureAssignees,
  useSuggestRecommendation,
} from "../api"

type Mode = null | "accept" | "reject" | "complete"

export function RecommendationCard({ rec, canDecide }: { rec: Recommendation; canDecide: boolean }) {
  const [mode, setMode] = useState<Mode>(null)
  const [responsibleId, setResponsibleId] = useState<string | null>(null)
  const [dueDate, setDueDate] = useState(() => isoDate(new Date(Date.now() + 14 * 86_400_000)))
  const [comment, setComment] = useState("")
  const [text, setText] = useState(rec.text)
  const decide = useDecideRecommendation()
  const complete = useCompleteRecommendation()
  const suggest = useSuggestRecommendation()
  const ai = useAiAccess()
  const finalText = text.trim()
  const edited = finalText !== rec.text.trim()
  const assignees = useMeasureAssignees(rec.measureId, mode === "accept")
  const me = session.get().user
  const canComplete = rec.status === "ACCEPTED" && (me?.role === "HEAD" || me?.id === rec.responsibleId)
  const options = [
    ...(assignees.data ?? []),
    ...(me ? [{ value: me.id, label: `${me.displayName} (я)` }] : []),
  ].filter((o, i, all) => all.findIndex(x => x.value === o.value) === i)

  const done = (message: string) => {
    setMode(null)
    notifications.show({ color: "success", message })
  }

  return (
    <Card
      withBorder
      shadow='none'
    >
      <Stack gap='sm'>
        <Group
          justify='space-between'
          align='flex-start'
          wrap='nowrap'
        >
          <Group gap={6}>
            {rec.basis.priority !== undefined && (
              <Badge
                variant='outline'
                color={rec.basis.priority <= 1 ? "danger" : "gray"}
              >
                Пріоритет {rec.basis.priority}
              </Badge>
            )}
            {rec.basis.flagType && <FlagBadge type={rec.basis.flagType} />}
            {rec.basis.riskLevel && (
              <LevelBadge
                level={rec.basis.riskLevel}
                prefix='Ризик'
              />
            )}
          </Group>
          <RecBadge
            status={rec.status}
            style={{ flexShrink: 0 }}
          />
        </Group>

        <Text fw={600}>{rec.text}</Text>
        {rec.measureId && rec.measureTitle && (
          <Text
            component={Link}
            to={measurePath(rec.measureId)}
            size='sm'
            c='dimmed'
          >
            Захід: {rec.measureTitle}
          </Text>
        )}

        <Card
          bg='var(--mantine-color-default-hover)'
          shadow='none'
          padding='sm'
        >
          <Text
            size='xs'
            fw={600}
            c='dimmed'
            tt='uppercase'
            mb={4}
          >
            Підстава · правило {rec.basis.rule ?? "—"}
          </Text>
          <Text size='sm'>{rec.basis.ruleDescription}</Text>
          {rec.basis.explanation && (
            <Text
              size='sm'
              c='dimmed'
              mt={4}
            >
              {rec.basis.explanation}
            </Text>
          )}
          {rec.basis.source && (
            <Code
              mt={6}
              fz={10}
            >
              джерело: {rec.basis.source === "rules" ? "явні правила" : rec.basis.source}
            </Code>
          )}
        </Card>

        {rec.status === "ACCEPTED" && <Text size='sm'>Строк виконання: {formatDate(rec.dueDate)}</Text>}
        {rec.status === "DONE" && typeof rec.basis.completionComment === "string" && (
          <Text size='sm'>Виконано: {rec.basis.completionComment}</Text>
        )}

        {canComplete && (
          <>
            <Button
              size='xs'
              color='teal'
              w='fit-content'
              leftSection={<IconChecks size={14} />}
              variant={mode === "complete" ? "filled" : "light"}
              onClick={() => setMode(mode === "complete" ? null : "complete")}
            >
              Позначити виконаною
            </Button>
            <Collapse expanded={mode === "complete"}>
              <Group
                align='flex-end'
                gap='sm'
              >
                <Textarea
                  label='Що зроблено'
                  autosize
                  minRows={1}
                  value={comment}
                  onChange={e => setComment(e.currentTarget.value)}
                  style={{ flex: 1, minWidth: 220 }}
                />
                <Button
                  color='teal'
                  disabled={comment.trim().length < 3}
                  loading={complete.isPending}
                  onClick={() =>
                    complete.mutate(
                      { id: rec.id, comment: comment.trim() },
                      {
                        onSuccess: () => done("Рекомендацію виконано"),
                        onError: e => notifications.show({ color: "danger", message: e.message }),
                      }
                    )
                  }
                >
                  Підтвердити
                </Button>
              </Group>
            </Collapse>
          </>
        )}

        {canDecide && rec.status === "PROPOSED" && (
          <>
            <Group gap='xs'>
              <Button
                size='xs'
                color='success'
                leftSection={<IconCheck size={14} />}
                variant={mode === "accept" ? "filled" : "light"}
                onClick={() => setMode(mode === "accept" ? null : "accept")}
              >
                Прийняти
              </Button>
              <Button
                size='xs'
                color='gray'
                leftSection={<IconX size={14} />}
                variant={mode === "reject" ? "filled" : "light"}
                onClick={() => setMode(mode === "reject" ? null : "reject")}
              >
                Відхилити
              </Button>
            </Group>
            <Collapse expanded={mode === "accept"}>
              <Stack gap='sm'>
                <Textarea
                  label='Формулювання рекомендації'
                  description={edited ? "Буде збережено відредагований текст" : "Можна уточнити перед прийняттям"}
                  autosize
                  minRows={2}
                  value={text}
                  onChange={e => setText(e.currentTarget.value)}
                  error={edited && finalText.length < 10 ? "Мінімум 10 символів" : undefined}
                />
                {ai.model && (
                  <Group gap='xs'>
                    <Button
                      size='compact-sm'
                      variant='light'
                      color='violet'
                      leftSection={<IconSparkles size={14} />}
                      loading={suggest.isPending}
                      onClick={() =>
                        suggest.mutate(rec.id, {
                          onSuccess: r => setText(r.text),
                          onError: e => notifications.show({ color: "danger", message: e.message }),
                        })
                      }
                    >
                      Конкретизувати з ШІ
                    </Button>
                    {edited && (
                      <Button
                        size='compact-sm'
                        variant='subtle'
                        onClick={() => setText(rec.text)}
                      >
                        Повернути текст правила
                      </Button>
                    )}
                  </Group>
                )}
                {suggest.data && (
                  <Stack gap={4}>
                    {suggest.data.steps.length > 0 && (
                      <List size='sm'>
                        {suggest.data.steps.map(step => (
                          <List.Item key={step}>{step}</List.Item>
                        ))}
                      </List>
                    )}
                    {suggest.data.rationale && (
                      <Text
                        size='xs'
                        c='dimmed'
                      >
                        {suggest.data.rationale}
                      </Text>
                    )}
                    <AiNote>{suggest.data.disclaimer}</AiNote>
                  </Stack>
                )}
                <Group
                  align='flex-end'
                  gap='sm'
                >
                  <Select
                    label='Відповідальний'
                    data={options}
                    value={responsibleId}
                    onChange={setResponsibleId}
                    placeholder={assignees.isLoading ? "Завантаження…" : "Оберіть"}
                    style={{ flex: 1, minWidth: 220 }}
                  />
                  <DateField
                    label='Строк'
                    value={dueDate}
                    onChange={v => setDueDate(v ?? "")}
                    minDate={isoDate(new Date())}
                  />
                  <Button
                    disabled={!responsibleId || !dueDate || (edited && finalText.length < 10)}
                    loading={decide.isPending}
                    onClick={() =>
                      responsibleId &&
                      decide.mutate(
                        {
                          id: rec.id,
                          decision: "accept",
                          responsibleId,
                          dueDate,
                          text: edited ? finalText : undefined,
                        },
                        {
                          onSuccess: () => done("Рекомендацію прийнято"),
                          onError: e => notifications.show({ color: "danger", message: e.message }),
                        }
                      )
                    }
                  >
                    Підтвердити
                  </Button>
                </Group>
              </Stack>
            </Collapse>
            <Collapse expanded={mode === "reject"}>
              <Group
                align='flex-end'
                gap='sm'
              >
                <Textarea
                  label='Причина відхилення'
                  autosize
                  minRows={1}
                  value={comment}
                  onChange={e => setComment(e.currentTarget.value)}
                  style={{ flex: 1, minWidth: 220 }}
                />
                <Button
                  color='gray'
                  disabled={comment.trim().length < 3}
                  loading={decide.isPending}
                  onClick={() =>
                    decide.mutate(
                      { id: rec.id, decision: "reject", comment: comment.trim() },
                      {
                        onSuccess: () => done("Рекомендацію відхилено"),
                        onError: e => notifications.show({ color: "danger", message: e.message }),
                      }
                    )
                  }
                >
                  Відхилити
                </Button>
              </Group>
            </Collapse>
          </>
        )}
      </Stack>
    </Card>
  )
}
