import { Alert, Blockquote, Button, Card, Group, List, Stack, Text, ThemeIcon } from "@mantine/core"
import { IconCircleCheck, IconCircleX, IconFileSearch } from "@tabler/icons-react"

import { AiNote, SourceBadge } from "@/shared/ui"
import { useEvidenceCheck } from "../api/queries"

const ruleTitle: Record<string, string> = {
  V1: "Потрібні документи",
  V2: "Числа з опису результату",
  V3: "Дати в межах періоду",
}

type EvidenceAdviceProps = {
  periodId: string
  onUseAdvice?: (text: string) => void
}

export function EvidenceAdvice({ periodId, onUseAdvice }: EvidenceAdviceProps) {
  const check = useEvidenceCheck()
  const data = check.data
  const failed = data?.findings.filter(f => !f.ok).length ?? 0
  const advice = data?.advice.trim() ?? ""
  const repeatsRules = Boolean(data?.findings.some(f => f.text.trim() === advice))

  return (
    <Card withBorder>
      <Stack gap='sm'>
        <Group justify='space-between'>
          <Group gap='xs'>
            <IconFileSearch size={18} />
            <Text fw={600}>Перевірка підтвердних документів</Text>
          </Group>
          <Button
            size='compact-sm'
            variant='light'
            loading={check.isPending}
            onClick={() => check.mutate(periodId)}
          >
            {data ? "Перевірити ще раз" : "Перевірити"}
          </Button>
        </Group>
        {!data && !check.isPending && (
          <Text
            size='sm'
            c='dimmed'
          >
            Звірка документів з описом результату: типи документів, числа і дати. Рішення залишається за вами.
          </Text>
        )}
        {check.error && (
          <Alert
            color='danger'
            variant='light'
          >
            {check.error.message}
          </Alert>
        )}
        {data && (
          <>
            <Stack gap={6}>
              {data.findings.map(f => (
                <Group
                  key={f.ruleCode}
                  gap='xs'
                  wrap='nowrap'
                  align='flex-start'
                >
                  <ThemeIcon
                    size='sm'
                    variant='light'
                    color={f.ok ? "success" : "warning"}
                  >
                    {f.ok ? <IconCircleCheck size={14} /> : <IconCircleX size={14} />}
                  </ThemeIcon>
                  <div>
                    <Text
                      size='sm'
                      fw={500}
                    >
                      {f.ruleCode} · {ruleTitle[f.ruleCode] ?? "Правило"}
                    </Text>
                    <Text
                      size='sm'
                      c='dimmed'
                    >
                      {f.text}
                    </Text>
                  </div>
                </Group>
              ))}
            </Stack>
            {data.unreadable.length > 0 && (
              <Alert
                color='warning'
                variant='light'
                title='Не вдалося прочитати'
              >
                <List size='sm'>
                  {data.unreadable.map(name => (
                    <List.Item key={name}>{name}</List.Item>
                  ))}
                </List>
              </Alert>
            )}
            {advice && !repeatsRules && (
              <Stack gap={6}>
                <Group gap='xs'>
                  <Text
                    size='sm'
                    fw={600}
                  >
                    Порада
                  </Text>
                  <SourceBadge source={data.adviceSource} />
                </Group>
                <Text
                  size='sm'
                  style={{ whiteSpace: "pre-wrap" }}
                >
                  {advice}
                </Text>
              </Stack>
            )}
            {onUseAdvice && advice && failed > 0 && (
              <Group>
                <Button
                  size='compact-sm'
                  variant='subtle'
                  onClick={() => onUseAdvice(advice)}
                >
                  Вставити в коментар
                </Button>
              </Group>
            )}
            {data.quotes.map(q => (
              <Blockquote
                key={`${q.evidenceId}-${q.quote}`}
                p='xs'
                cite={q.fileName}
              >
                <Text size='sm'>{q.quote}</Text>
              </Blockquote>
            ))}
            {data.modelUsed && <AiNote>{data.disclaimer}</AiNote>}
          </>
        )}
      </Stack>
    </Card>
  )
}
