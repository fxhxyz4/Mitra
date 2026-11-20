import { Badge, Group, Skeleton, Stack, Text } from "@mantine/core"

import { formatDate } from "@/shared/lib"
import { AiNote, ReferencedText, Section, SourceBadge } from "@/shared/ui"
import { useWeeklyDigest } from "../api/queries"

const pct = (x: number) => `${Math.round(x * 100)}%`

export function WeeklyDigestCard() {
  const { data, isPending, error } = useWeeklyDigest()
  const h = data?.highlights

  return (
    <Section
      title='Що змінилось за тиждень'
      actions={data && <SourceBadge source={data.textSource} />}
    >
      {isPending && <Skeleton h={380} />}
      {error && (
        <Text
          size='sm'
          c='danger'
        >
          {error.message}
        </Text>
      )}
      {data && h && (
        <Stack gap='sm'>
          <Text
            size='xs'
            c='dimmed'
          >
            {formatDate(data.since)} — {formatDate(data.asOf)}
          </Text>
          <Group gap='xs'>
            <Badge
              variant='light'
              color={h.pri >= h.priBefore ? "success" : "danger"}
            >
              Зниження ризиків {pct(h.priBefore)} → {pct(h.pri)}
            </Badge>
            <Badge
              variant='light'
              color='success'
            >
              Виконано: {h.done}
            </Badge>
            {h.newOverdue > 0 && (
              <Badge
                variant='light'
                color='danger'
              >
                Нові прострочення: {h.newOverdue}
              </Badge>
            )}
            {h.risksUp > 0 && (
              <Badge
                variant='light'
                color='danger'
              >
                Ризиків зросло: {h.risksUp}
              </Badge>
            )}
            {h.risksDown > 0 && (
              <Badge
                variant='light'
                color='success'
              >
                Ризиків знизилось: {h.risksDown}
              </Badge>
            )}
          </Group>
          <ReferencedText
            text={data.text}
            references={data.references}
          />
          {data.modelUsed && <AiNote>{data.disclaimer}</AiNote>}
        </Stack>
      )}
    </Section>
  )
}
