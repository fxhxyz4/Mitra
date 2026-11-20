import { useState } from "react"
import { Alert, Button, Card, Drawer, Group, ScrollArea, SimpleGrid, Stack, Switch, Table, Text } from "@mantine/core"
import {
  IconAlertTriangle,
  IconChartBar,
  IconClockHour4,
  IconFileAlert,
  IconHistory,
  IconScale,
} from "@tabler/icons-react"
import { useSearchParams } from "react-router"

import { STAFF } from "@/features/auth"
import {
  RiskDelta,
  RiskDetails,
  RiskMatrix,
  SignalBadge,
  useRiskAssessment,
  useRiskModel,
  VerdictBadge,
} from "@/features/risk-model"
import { useSession } from "@/shared/api"
import { formatDate, isoDate, signalColor } from "@/shared/lib"
import {
  DateField,
  EmptyState,
  HintLabel,
  KpiTile,
  LevelBadge,
  PageHeader,
  QueryError,
  Section,
  Seo,
} from "@/shared/ui"
import classes from "./RiskModelPage.module.scss"

const num = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? "—" : v.toLocaleString("uk-UA", { maximumFractionDigits: d })
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${num(v * 100, 1)} %`)

const fcgText: Record<string, string> = {
  green: "зелений: розрив < 10 в.п.",
  yellow: "жовтий: розрив 10–25 в.п.",
  red: "червоний: розрив > 25 в.п.",
}

const shiftDays = (iso: string, days: number) => {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + days)
  return isoDate(d)
}

const trendStyle = (previous: number | null | undefined, current: number | null) => {
  if (previous === undefined || previous === null || current === null || previous === current) return {}
  const color = current < previous ? "var(--mantine-color-danger-filled)" : "var(--mantine-color-success-filled)"
  return {
    background: `color-mix(in srgb, ${color} 8%, transparent)`,
    boxShadow: `inset 4px 0 0 ${color}`,
  }
}

export function RiskModelPage() {
  const { user } = useSession()
  const [asOf, setAsOf] = useState<string | null>(null)
  const [compare, setCompare] = useState(false)
  const today = useRiskModel()
  const serverToday = today.data?.asOf ?? null
  const viewing = asOf && asOf !== serverToday ? asOf : null
  const shown = useRiskModel(undefined, viewing, Boolean(viewing))
  const { data, isPending, error } = viewing ? shown : today
  const baseDate = viewing ?? serverToday
  const compareDate = compare && baseDate ? shiftDays(baseDate, -7) : null
  const previous = useRiskModel(undefined, compareDate, Boolean(compareDate))
  const prev = compareDate ? previous.data : undefined
  const prevRisk = (id: string) => prev?.risks.find(r => r.riskId === id)
  const [params, setParams] = useSearchParams()
  const selected = params.get("risk")
  const setSelected = (id: string | null) =>
    setParams(
      prev => {
        const next = new URLSearchParams(prev)
        if (id) next.set("risk", id)
        else next.delete("risk")
        return next
      },
      { replace: true }
    )
  const detail = useRiskAssessment(selected, viewing)
  const current = detail.data ?? data?.risks.find(r => r.riskId === selected)
  const changed = prev
    ? (data?.risks ?? []).filter(r => {
        const old = prevRisk(r.riskId)
        return old !== undefined && (old.rrs !== r.rrs || old.verdict !== r.verdict)
      })
    : []
  const paper = data ? data.verdictCounts.FORMAL + data.verdictCounts.WORSE_DESPITE : 0

  return (
    <>
      <Seo title='Модель ризику' />
      <PageHeader
        title='Модель ризику'
        description='Чи працюють заходи: виконання × зміна індикатора ризику → висновок; розрив формального виконання (FCG)'
      />
      <QueryError error={error ?? previous.error} />
      <Stack gap='lg'>
        <Card>
          <Group
            justify='space-between'
            align='flex-end'
            gap='md'
          >
            <Group
              align='flex-end'
              gap='sm'
              maw='100%'
              miw={0}
            >
              <DateField
                label='Розрахунок на дату'
                leftSection={<IconClockHour4 size={16} />}
                value={baseDate}
                maxDate={serverToday ?? undefined}
                onChange={setAsOf}
                w={{ base: "100%", xs: 210 }}
              />
              <Button.Group className={classes.range}>
                <Button
                  variant={viewing ? "default" : "light"}
                  onClick={() => setAsOf(null)}
                >
                  Сьогодні
                </Button>
                <Button
                  variant='default'
                  disabled={!serverToday}
                  onClick={() => serverToday && setAsOf(shiftDays(baseDate ?? serverToday, -7))}
                >
                  −7 днів
                </Button>
                <Button
                  variant='default'
                  disabled={!serverToday}
                  onClick={() => serverToday && setAsOf(shiftDays(baseDate ?? serverToday, -30))}
                >
                  −30 днів
                </Button>
              </Button.Group>
            </Group>
            <Switch
              label='Порівняти з тижнем раніше'
              checked={compare}
              onChange={e => setCompare(e.currentTarget.checked)}
            />
          </Group>
          {viewing && (
            <Alert
              mt='md'
              variant='light'
              color='violet'
              icon={<IconHistory size={18} />}
            >
              Показано стан ризиків на {formatDate(viewing)} — так, як система оцінила б їх того дня за наявними даними.
            </Alert>
          )}
          {prev && compareDate && (
            <Text
              size='sm'
              mt='md'
              c='dimmed'
            >
              Порівняння з {formatDate(compareDate)}:{" "}
              {changed.length
                ? `змінився стан у ${changed.length} з ${data?.risks.length ?? 0} ризиків`
                : "стан ризиків не змінився"}
              . Червоним — зниження ризику стало меншим, зеленим — більшим.
            </Text>
          )}
        </Card>
        {data?.scopeName && (
          <Alert
            color='blue'
            variant='light'
          >
            Показники пораховано лише за ризиками й заходами вашої зони відповідальності: {data.scopeName}.
          </Alert>
        )}
        <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
          <KpiTile
            label='FCG — розрив формального виконання'
            info={{
              formula: "FCG = EXEC − PRI",
              hint: "Наскільки «закриті на папері» заходи випереджають реальне зниження ризиків. До 10 в.п. — норма, 10–25 — увага, понад 25 — формальне виконання.",
            }}
            value={data ? `${num(data.fcg, 1)} в.п.` : "—"}
            hint={
              data ? (
                <Group gap={6}>
                  {fcgText[data.fcgColor]}
                  <RiskDelta
                    current={data.fcg}
                    previous={prev?.fcg}
                    suffix=' в.п.'
                  />
                </Group>
              ) : undefined
            }
            icon={IconAlertTriangle}
            color={data ? signalColor[data.fcgColor] : "gray"}
            loading={isPending}
          />
          <KpiTile
            label='EXEC — закрито заходів (зважено на I)'
            info={{
              formula: "EXEC = Σ I · частка виконаних / Σ I",
              hint: "Частка виконаних заходів, де важливіші ризики (більший I) мають більшу вагу. Це те, що показав би звичайний звіт.",
            }}
            value={pct(data?.exec)}
            hint={
              <Group gap={6}>
                те, що показала б метрика «закрито заходів»
                <RiskDelta
                  current={data ? data.exec * 100 : null}
                  previous={prev ? prev.exec * 100 : null}
                  higherIsWorse={false}
                  suffix=' в.п.'
                />
              </Group>
            }
            icon={IconChartBar}
            progress={data ? data.exec * 100 : undefined}
            loading={isPending}
          />
          <KpiTile
            label='PRI — реальне зниження ризиків'
            info={{
              formula: "PRI = Σ I · RRS / Σ I",
              hint: "Наскільки ризики знизились за даними індикаторів (KRI), а не за звітами виконавців.",
            }}
            value={pct(data?.pri)}
            hint={
              <Group gap={6}>
                Σ I·RRS / Σ I
                <RiskDelta
                  current={data ? data.pri * 100 : null}
                  previous={prev ? prev.pri * 100 : null}
                  higherIsWorse={false}
                  suffix=' в.п.'
                />
              </Group>
            }
            icon={IconScale}
            color='success'
            progress={data ? Math.max(0, data.pri * 100) : undefined}
            loading={isPending}
          />
          <KpiTile
            label='Закрито «на папері»'
            info={{
              formula: "заходи виконано, а індикатор < 10 % шляху",
              hint: "Ризики, у яких є виконані заходи, а індикатор ризику майже не змінився або погіршився. Найслабша ланка — критичний ризик, що знижується найгірше.",
            }}
            value={data ? `${paper} з ${data.risksWithDone}` : "—"}
            hint={
              data
                ? `зниження підтверджено у ${data.risksWorking} з ${data.risksWithDone} ризиків з виконаними заходами` +
                  (data.weakestLink ? ` · найслабша ланка: ${data.weakestLink.code}` : "")
                : undefined
            }
            icon={IconFileAlert}
            color={paper ? "danger" : "success"}
            loading={isPending}
          />
        </SimpleGrid>

        <Section
          title='Матриця ризиків НАЗК'
          subtitle={
            data
              ? `Притаманний ризик (ймовірність × наслідки) і висновок за даними · ${data.risks.length} ризиків` +
                (data.uncovered.length ? ` · без заходів: ${data.uncovered.map(r => r.code).join(", ")}` : "")
              : undefined
          }
          loading={isPending}
        >
          {data && (
            <RiskMatrix
              risks={data.risks}
              uncovered={data.uncovered}
              onSelect={setSelected}
            />
          )}
        </Section>

        <Section
          title='Ризики програми'
          subtitle={
            data
              ? `Розрахунок на ${formatDate(data.asOf)} · правила ${data.rulesetVersion}` +
                (data.subIndex !== null
                  ? ` · субіндекс розділів 1 і 3 (без ризику): ${pct(data.subIndex)} за ${data.subIndexCount} індикаторами`
                  : "")
              : undefined
          }
          loading={isPending}
          padding={0}
        >
          {data && !data.risks.length ? (
            <EmptyState
              title='Немає ризиків'
              text='Заходи програми не повʼязані з корупційними ризиками'
            />
          ) : (
            <ScrollArea type='auto'>
              <Table
                miw={980}
                highlightOnHover
                verticalSpacing='sm'
              >
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Ризик</Table.Th>
                    <Table.Th>
                      <HintLabel hint='Притаманний ризик до заходів: ймовірність L₀ × наслідки C₀ (шкала 1–16).'>
                        I = L₀·C₀
                      </HintLabel>
                    </Table.Th>
                    <Table.Th>
                      <HintLabel hint='Скільки заходів щодо ризику виконано (або подано як виконані) з усіх затверджених.'>
                        Виконання
                      </HintLabel>
                    </Table.Th>
                    <Table.Th>
                      <HintLabel
                        hint='Прогрес індикатора ризику від бази до цілі і скільки мало б бути на цю дату за рівномірного руху до дедлайну цілі. Менше 10 % шляху — «без змін».'
                        formula='p = (C − B) / (T − B)'
                      >
                        Індикатор: факт / графік
                      </HintLabel>
                    </Table.Th>
                    <Table.Th>
                      <HintLabel hint='Висновок за матрицею «виконання × зміна індикатора». «Попередньо» — лаг ефекту виконаних заходів ще не минув.'>
                        Висновок
                      </HintLabel>
                    </Table.Th>
                    <Table.Th>
                      <HintLabel hint='Спрацьовані правила: формальне закриття, непідтверджена ефективність, інциденти тощо.'>
                        Сигнали
                      </HintLabel>
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data?.risks.map(r => (
                    <Table.Tr
                      key={r.riskId}
                      onClick={() => setSelected(r.riskId)}
                      style={{ cursor: "pointer", ...trendStyle(prevRisk(r.riskId)?.rrs, r.rrs) }}
                    >
                      <Table.Td maw={320}>
                        <Text fw={600}>{r.code}</Text>
                        <Text
                          size='xs'
                          c='dimmed'
                          lineClamp={2}
                        >
                          {r.description}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Group gap={6}>
                          {r.inherent}
                          <LevelBadge
                            level={r.inherentLevel}
                            size='xs'
                          />
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Text fw={600}>
                          {r.doneCount} з {r.measures.length}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text
                          fw={600}
                          c={
                            r.rrs === null
                              ? "dimmed"
                              : r.effect === "WORSENING" || r.effect === "NO_CHANGE"
                                ? "danger"
                                : r.effect === "ON_TRACK"
                                  ? "success"
                                  : undefined
                          }
                        >
                          {pct(r.rrs)} / {pct(r.expected)}
                        </Text>
                        <Text
                          size='xs'
                          c='dimmed'
                        >
                          {r.effectLabel}
                        </Text>
                        <RiskDelta
                          current={r.rrs}
                          previous={prevRisk(r.riskId)?.rrs}
                          higherIsWorse={false}
                          digits={2}
                        />
                      </Table.Td>
                      <Table.Td>
                        <VerdictBadge risk={r} />
                      </Table.Td>
                      <Table.Td>
                        <Group gap={4}>
                          {r.signals.map(s => (
                            <SignalBadge
                              key={`${s.ruleCode}-${s.indicatorId ?? ""}`}
                              signal={s}
                            />
                          ))}
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          )}
        </Section>
      </Stack>

      <Drawer
        opened={selected !== null}
        onClose={() => setSelected(null)}
        position='right'
        size='xl'
        title={
          current ? `${current.code} — оцінка ризику${viewing ? ` на ${formatDate(viewing)}` : ""}` : "Оцінка ризику"
        }
      >
        {current && (
          <RiskDetails
            risk={current}
            canEdit={user?.role === "COORDINATOR"}
            canExplain={Boolean(user && STAFF.includes(user.role))}
          />
        )}
      </Drawer>
    </>
  )
}
