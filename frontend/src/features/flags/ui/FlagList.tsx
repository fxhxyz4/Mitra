import { useState } from "react"
import { Alert, Badge, Button, Card, Code, Group, Modal, Stack, Text, Textarea } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconCircleCheck } from "@tabler/icons-react"
import { Link } from "react-router"
import type { RiskFlag, Role } from "@/shared/api"

import { formatDateTime } from "@/shared/lib"
import { EmptyState, FlagBadge, measurePath } from "@/shared/ui"
import { useResolveFlag } from "../api"

const headOnly = (flag: RiskFlag) => flag.type === "FORMAL_CLOSURE" || flag.type === "WORSENING"

const canResolve = (flag: RiskFlag, role: Role | null) =>
  flag.status === "OPEN" && (role === "HEAD" || (role === "COORDINATOR" && !headOnly(flag)))

const factLabels: Record<string, string> = {
  deadline: "строк",
  daysOverdue: "днів прострочки",
  status: "статус",
  period: "період",
  indicator: "індикатор",
  baseline: "база",
  current: "поточне",
  target: "ціль",
  similarityToTitle: "схожість з назвою",
  threshold: "поріг",
  hasNumber: "є число",
  hasReference: "є посилання",
  orgUnit: "підрозділ",
  overdueCount: "прострочених",
  measures: "заходи",
  evidenceCount: "документів",
  form: "форма документа",
  rrs: "RRS",
  lagMonths: "лаг, міс.",
  monthsSince: "минуло, міс.",
  completedOn: "виконано",
  risk: "ризик",
}

const formatFact = (v: unknown) =>
  typeof v === "boolean" ? (v ? "так" : "ні") : Array.isArray(v) ? v.join(", ") : String(v)

function Facts({ facts }: { facts: Record<string, unknown> }) {
  const entries = Object.entries(facts).filter(([k]) => !k.endsWith("Id") && factLabels[k])
  if (!entries.length) return null
  return (
    <Group gap={6}>
      {entries.map(([k, v]) => (
        <Code
          key={k}
          style={{ whiteSpace: "normal", overflowWrap: "anywhere" }}
        >
          {factLabels[k]}: {formatFact(v)}
        </Code>
      ))}
    </Group>
  )
}

export function FlagList({ flags, role }: { flags: RiskFlag[]; role: Role | null }) {
  const [target, setTarget] = useState<RiskFlag | null>(null)
  const [comment, setComment] = useState("")
  const resolve = useResolveFlag()

  if (!flags.length)
    return (
      <EmptyState
        title='Прапорців немає'
        text='Правила R1, R4, R6, E1 і F1–F3 нічого не виявили'
      />
    )

  return (
    <>
      <Stack gap='sm'>
        {flags.map(f => (
          <Card
            key={f.id}
            withBorder
            shadow='none'
            padding='md'
          >
            <Group
              justify='space-between'
              align='flex-start'
              wrap='wrap'
              gap='sm'
            >
              <Stack
                gap={6}
                style={{ flex: 1, minWidth: "min(260px, 100%)" }}
              >
                <Group gap='xs'>
                  <FlagBadge type={f.type} />
                  {f.status === "RESOLVED" && (
                    <Badge
                      color='gray'
                      variant='light'
                    >
                      Знято
                    </Badge>
                  )}
                  <Text
                    size='xs'
                    c='dimmed'
                  >
                    {formatDateTime(f.createdAt)}
                  </Text>
                </Group>
                <Text
                  component={Link}
                  to={measurePath(f.measureId)}
                  fw={600}
                  size='sm'
                  style={{ color: "inherit" }}
                >
                  {f.measureCode} {f.measureTitle}
                </Text>
                <Text size='sm'>{f.explanation}</Text>
                <Facts facts={f.facts} />
                {f.resolutionComment && (
                  <Text
                    size='xs'
                    c='dimmed'
                  >
                    Коментар: {f.resolutionComment}
                  </Text>
                )}
              </Stack>
              {canResolve(f, role) && (
                <Button
                  size='xs'
                  variant='light'
                  leftSection={<IconCircleCheck size={14} />}
                  onClick={() => {
                    setComment("")
                    setTarget(f)
                  }}
                >
                  Зняти
                </Button>
              )}
              {f.status === "OPEN" && headOnly(f) && role === "COORDINATOR" && (
                <Text
                  size='xs'
                  c='dimmed'
                  maw={160}
                >
                  Знімає лише керівник
                </Text>
              )}
            </Group>
          </Card>
        ))}
      </Stack>

      <Modal
        opened={Boolean(target)}
        onClose={() => setTarget(null)}
        title='Зняти прапорець'
      >
        {target && (
          <Stack>
            <Alert
              variant='light'
              color='gray'
            >
              {target.explanation}
            </Alert>
            <Textarea
              label='Обґрунтування'
              description='Мінімум 3 символи, потрапить у журнал дій'
              autosize
              minRows={3}
              value={comment}
              onChange={e => setComment(e.currentTarget.value)}
            />
            <Group justify='flex-end'>
              <Button
                variant='default'
                onClick={() => setTarget(null)}
              >
                Скасувати
              </Button>
              <Button
                disabled={comment.trim().length < 3}
                loading={resolve.isPending}
                onClick={() =>
                  resolve.mutate(
                    { id: target.id, comment: comment.trim() },
                    {
                      onSuccess: () => {
                        setTarget(null)
                        notifications.show({ color: "success", message: "Прапорець знято" })
                      },
                      onError: e => notifications.show({ color: "danger", message: e.message }),
                    }
                  )
                }
              >
                Зняти
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </>
  )
}
