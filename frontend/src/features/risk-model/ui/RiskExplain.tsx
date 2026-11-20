import { Alert, Button, Card, Group, Stack, Text } from "@mantine/core"
import { IconBulb } from "@tabler/icons-react"

import { useAiAccess } from "@/shared/api"
import { AiNote, ReferencedText, SourceBadge } from "@/shared/ui"
import { useExplainRisk } from "../api"

export function RiskExplain({ riskId }: { riskId: string }) {
  const explain = useExplainRisk()
  const ai = useAiAccess()
  const data = explain.data

  return (
    <Card withBorder>
      <Stack gap='sm'>
        <Group justify='space-between'>
          <Group gap='xs'>
            <IconBulb size={18} />
            <Text fw={600}>Чому ризик у такому стані</Text>
            {data && <SourceBadge source={data.textSource} />}
          </Group>
          <Button
            size='compact-sm'
            variant='light'
            loading={explain.isPending}
            onClick={() => explain.mutate(riskId)}
          >
            {data ? "Оновити" : "Пояснити"}
          </Button>
        </Group>
        {!data && !explain.isPending && (
          <Text
            size='sm'
            c='dimmed'
          >
            {ai.model
              ? "Пояснення з посиланнями на індикатори, заходи, сигнали і Risk Flags."
              : "Пояснення за правилами моделі з посиланнями на записи."}
          </Text>
        )}
        {explain.error && (
          <Alert
            color='danger'
            variant='light'
          >
            {explain.error.message}
          </Alert>
        )}
        {data && (
          <>
            <ReferencedText
              text={data.text}
              references={data.references}
            />
            {data.modelUsed && data.ruleText && data.ruleText !== data.text && (
              <Text
                size='xs'
                c='dimmed'
              >
                За правилами: {data.ruleText}
              </Text>
            )}
            {data.modelUsed && <AiNote>{data.disclaimer}</AiNote>}
          </>
        )}
      </Stack>
    </Card>
  )
}
