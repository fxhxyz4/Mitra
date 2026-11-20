import {
  Alert,
  Anchor,
  Badge,
  Grid,
  Group,
  List,
  Progress,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core"
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconClockExclamation,
  IconHourglass,
  IconInfoCircle,
  IconProgress,
  IconShieldCheck,
} from "@tabler/icons-react"
import { Link } from "react-router"
import type { Verdict } from "@/shared/api"

import { formatDate, formatDaysLeft, formatNumber } from "@/shared/lib"
import { KpiTile, measurePath, QueryError, Section } from "@/shared/ui"
import { useAnalyticsSummary } from "../api"

const verdictMeta: Record<Verdict["level"], { color: string; icon: typeof IconCircleCheck }> = {
  good: { color: "success", icon: IconCircleCheck },
  attention: { color: "warning", icon: IconInfoCircle },
  behind: { color: "danger", icon: IconAlertTriangle },
}

export function BasicView({ programId }: { programId?: string | null }) {
  const { data: s, isPending, error } = useAnalyticsSummary(programId)

  if (error) return <QueryError error={error} />
  const verdict = s ? verdictMeta[s.verdict.level] : null

  return (
    <Stack gap='lg'>
      {s && verdict && (
        <Alert
          variant='light'
          color={verdict.color}
          icon={<verdict.icon size={22} />}
          title={<Title order={4}>{s.verdict.title}</Title>}
        >
          <Text size='sm'>{s.verdict.text}</Text>
          <Text
            size='xs'
            c='dimmed'
            mt={4}
          >
            {s.programTitle}
            {s.scope ? ` · підрозділ: ${s.scope}` : ""} · станом на {formatDate(s.asOf)}
          </Text>
        </Alert>
      )}

      <Section
        title='Загальний прогрес'
        subtitle={s ? `Виконано ${s.done} з ${s.total} заходів` : undefined}
        loading={isPending}
      >
        {s && (
          <Stack gap='md'>
            <Progress.Root
              size={22}
              radius='md'
            >
              <Progress.Section
                value={s.donePercent}
                color='success'
                aria-label='Виконано'
              >
                <Progress.Label>{s.donePercent >= 8 ? `${Math.round(s.donePercent)} %` : ""}</Progress.Label>
              </Progress.Section>
              <Progress.Section
                value={(100 * s.onReview) / Math.max(s.total, 1)}
                color='violet'
                aria-label='На перевірці'
              />
              <Progress.Section
                value={(100 * s.overdue) / Math.max(s.total, 1)}
                color='danger'
                aria-label='Прострочено'
              />
            </Progress.Root>
            <Group gap='lg'>
              <Legend
                color='success'
                label='Виконано'
              />
              <Legend
                color='violet'
                label='На перевірці'
              />
              <Legend
                color='danger'
                label='Прострочено'
              />
            </Group>
          </Stack>
        )}
      </Section>

      <SimpleGrid
        cols={{ base: 2, md: 4 }}
        spacing='md'
      >
        <KpiTile
          label='Виконано'
          value={s?.done ?? "—"}
          hint={s ? `${formatNumber(s.onTimePercent)} % — вчасно` : undefined}
          icon={IconCircleCheck}
          color='success'
          loading={isPending}
        />
        <KpiTile
          label='В роботі'
          value={s?.inWork ?? "—"}
          hint={s?.onReview ? `ще ${s.onReview} на перевірці` : undefined}
          icon={IconProgress}
          color='brand'
          loading={isPending}
        />
        <KpiTile
          label='Прострочено'
          value={s?.overdue ?? "—"}
          hint={s ? `строк настав для ${s.due}` : undefined}
          icon={IconClockExclamation}
          color={s?.overdue ? "danger" : "gray"}
          loading={isPending}
        />
        <KpiTile
          label='Ризиків зменшено'
          value={s ? `${s.risksReduced} з ${s.risksTotal}` : "—"}
          hint='за індикаторами ризиків'
          icon={IconShieldCheck}
          color='teal'
          loading={isPending}
        />
      </SimpleGrid>

      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Section
            title='Що потребує уваги'
            loading={isPending}
          >
            <List
              spacing='sm'
              size='sm'
              icon={
                <ThemeIcon
                  size={20}
                  radius='xl'
                  variant='light'
                  color={s?.verdict.level === "good" ? "success" : "warning"}
                >
                  {s?.verdict.level === "good" ? <IconCircleCheck size={13} /> : <IconInfoCircle size={13} />}
                </ThemeIcon>
              }
            >
              {s?.attention.map(a => (
                <List.Item key={a}>{a}</List.Item>
              ))}
            </List>
          </Section>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Section
            title='Розділи програми'
            loading={isPending}
          >
            <Stack gap='md'>
              {s?.sections.map(sec => (
                <div key={sec.number}>
                  <Group
                    justify='space-between'
                    mb={4}
                    wrap='nowrap'
                  >
                    <Text
                      size='sm'
                      fw={500}
                    >
                      {sec.number}. {sec.title}
                    </Text>
                    <Text
                      size='sm'
                      c='dimmed'
                      style={{ whiteSpace: "nowrap" }}
                    >
                      {sec.done} з {sec.total}
                      {sec.overdue > 0 && (
                        <Text
                          span
                          c='danger'
                          size='sm'
                        >
                          {" "}
                          · прострочено {sec.overdue}
                        </Text>
                      )}
                    </Text>
                  </Group>
                  <Progress
                    value={sec.percent}
                    color={sec.overdue ? "warning" : "success"}
                    size='md'
                    radius='xl'
                    aria-label={`Розділ ${sec.number}: виконано ${sec.percent} %`}
                  />
                </div>
              ))}
            </Stack>
          </Section>
        </Grid.Col>
      </Grid>

      <Section
        title='Найближчі строки'
        subtitle={
          s
            ? s.upcomingTotal
              ? `Наступні 30 днів: ${s.upcomingTotal}`
              : "У наступні 30 днів строків немає"
            : undefined
        }
        loading={isPending}
      >
        {s?.upcoming.length ? (
          <Stack gap='xs'>
            {s.upcoming.map(d => (
              <Group
                key={d.measureId}
                justify='space-between'
                wrap='nowrap'
                gap='sm'
              >
                <Group
                  gap='xs'
                  wrap='nowrap'
                  style={{ minWidth: 0 }}
                >
                  <IconHourglass
                    size={16}
                    style={{ flexShrink: 0 }}
                  />
                  <Text
                    size='sm'
                    truncate
                  >
                    <Anchor
                      component={Link}
                      to={measurePath(d.measureId)}
                      size='sm'
                    >
                      {d.code} {d.title}
                    </Anchor>
                    {d.unit && (
                      <Text
                        span
                        c='dimmed'
                        size='sm'
                      >
                        {" "}
                        · {d.unit}
                      </Text>
                    )}
                  </Text>
                </Group>
                <Badge
                  variant='light'
                  color={d.daysLeft <= 3 ? "danger" : d.daysLeft <= 7 ? "warning" : "gray"}
                  style={{ flexShrink: 0 }}
                >
                  {formatDate(d.deadline)} · {formatDaysLeft(d.daysLeft)}
                </Badge>
              </Group>
            ))}
          </Stack>
        ) : (
          <Text
            size='sm'
            c='dimmed'
          >
            Термінових строків немає.
          </Text>
        )}
      </Section>
    </Stack>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <Group gap={6}>
      <div style={{ width: 10, height: 10, borderRadius: 3, background: `var(--mantine-color-${color}-filled)` }} />
      <Text
        size='xs'
        c='dimmed'
      >
        {label}
      </Text>
    </Group>
  )
}
