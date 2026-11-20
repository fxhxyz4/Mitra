import { Alert, Badge, Card, Divider, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core"
import { IconFileCertificate } from "@tabler/icons-react"
import type { MeasureDetail } from "@/shared/api"
import type { ReactNode } from "react"

import { formatDate, formatPeriod, sectionShort } from "@/shared/lib"
import { Deadline, FlagBadge, IndicatorBlock, LevelBadge, StatusBadge } from "@/shared/ui"
import { DeadlineChanges } from "./DeadlineChanges"

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Stack gap={2}>
      <Text
        size='xs'
        c='dimmed'
        tt='uppercase'
        fw={600}
        lts={0.3}
      >
        {label}
      </Text>
      <div>{children}</div>
    </Stack>
  )
}

export function MeasureSummary({ measure, canPostpone = false }: { measure: MeasureDetail; canPostpone?: boolean }) {
  const moved = measure.deadlineChanges.length > 0 && measure.internalDeadline !== measure.plannedDeadline
  const closed = measure.status === "DONE" || measure.status === "PARTIAL" || measure.status === "NOT_DONE"
  const openFlags = measure.flags.filter(f => f.status === "OPEN")

  return (
    <Card>
      <Stack gap='md'>
        <Group
          gap='xs'
          wrap='wrap'
        >
          <Badge
            variant='outline'
            color='gray'
          >
            Захід {measure.code}
          </Badge>
          <StatusBadge status={measure.status} />
          {measure.isPermanent && (
            <Badge
              variant='light'
              color='gray'
            >
              Постійний
            </Badge>
          )}
          <Text
            size='sm'
            c='dimmed'
          >
            {formatPeriod(measure.period)}
          </Text>
        </Group>
        <Title order={2}>{measure.title}</Title>
        <Text
          size='sm'
          c='dimmed'
        >
          Розділ {measure.sectionNumber}. {sectionShort[measure.sectionNumber] ?? measure.sectionTitle}
        </Text>

        {openFlags.length > 0 && (
          <Alert
            color='danger'
            variant='light'
            title={`Risk Flags: ${openFlags.length}`}
          >
            <Stack gap={6}>
              {openFlags.map(f => (
                <Group
                  key={f.id}
                  gap='xs'
                  align='flex-start'
                  wrap='nowrap'
                >
                  <FlagBadge
                    type={f.type}
                    style={{ flexShrink: 0 }}
                  />
                  <Text size='sm'>{f.explanation}</Text>
                </Group>
              ))}
            </Stack>
          </Alert>
        )}

        <Divider />

        <SimpleGrid
          cols={{ base: 1, sm: 2, lg: 3 }}
          spacing='lg'
        >
          <Field label='Строк'>
            <Deadline
              date={measure.deadline}
              daysLeft={measure.daysLeft}
              overdue={measure.isOverdue}
              closed={closed}
            />
            {moved && measure.internalDeadline && (
              <Text
                size='xs'
                c='orange'
              >
                Внутрішній строк: {formatDate(measure.internalDeadline)} (перенесено {measure.deadlineChanges.length})
              </Text>
            )}
          </Field>
          <Field label='Виконавці'>
            <Stack gap={2}>
              {measure.assignments.map(a => (
                <Text
                  size='sm'
                  key={`${a.orgUnitId}-${a.userId}`}
                  fw={a.isResponsible ? 600 : undefined}
                >
                  {a.orgUnitName}
                  {a.userName ? ` · ${a.userName}` : ""}
                  {a.isResponsible ? " (відповідальний)" : ""}
                </Text>
              ))}
              {!measure.assignments.length && (
                <Text
                  size='sm'
                  c='dimmed'
                >
                  Не призначено
                </Text>
              )}
            </Stack>
          </Field>
          <Field label='Корупційний ризик'>
            {measure.risk ? (
              <Stack gap={4}>
                <Group gap={6}>
                  <Text
                    size='sm'
                    fw={600}
                  >
                    {measure.risk.code}
                  </Text>
                  <LevelBadge
                    level={measure.risk.level}
                    size='xs'
                  />
                </Group>
                <Text size='sm'>{measure.risk.description}</Text>
              </Stack>
            ) : (
              <Text
                size='sm'
                c='dimmed'
              >
                Не повʼязано
              </Text>
            )}
          </Field>
        </SimpleGrid>

        {(measure.indicator || measure.indicatorText) && (
          <Field label='Індикатор виконання заходу'>
            {measure.indicator ? (
              <IndicatorBlock indicator={measure.indicator} />
            ) : (
              <Text size='sm'>
                {measure.indicatorText}{" "}
                <Text
                  span
                  size='xs'
                  c='dimmed'
                >
                  (якісний, без числової цілі)
                </Text>
              </Text>
            )}
          </Field>
        )}

        <DeadlineChanges
          measure={measure}
          canPostpone={canPostpone}
        />

        {measure.requiredEvidence && (
          <Group
            gap='xs'
            wrap='nowrap'
            align='flex-start'
          >
            <IconFileCertificate
              size={18}
              stroke={1.6}
              style={{ flexShrink: 0, marginTop: 2 }}
            />
            <Text size='sm'>
              <Text
                span
                fw={600}
              >
                Потрібні документи:{" "}
              </Text>
              {measure.requiredEvidence}
            </Text>
          </Group>
        )}
      </Stack>
    </Card>
  )
}
