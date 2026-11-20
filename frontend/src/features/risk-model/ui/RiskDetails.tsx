import { useState } from "react"
import {
  Alert,
  Badge,
  Button,
  Group,
  NumberInput,
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Tooltip,
} from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconArrowDown, IconArrowUp, IconBulb, IconPlus, IconScale } from "@tabler/icons-react"
import type { RiskAssessment } from "@/shared/api"

import { formatDate, signalColor } from "@/shared/lib"
import { DateField, LevelBadge, StatusBadge } from "@/shared/ui"
import { useAddIncident, useReassessRisk } from "../api"
import { RiskExplain } from "./RiskExplain"
import { SignalBadge } from "./SignalBadge"
import { VerdictBadge } from "./VerdictBadge"

const num = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? "—" : v.toLocaleString("uk-UA", { maximumFractionDigits: d })
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${num(v * 100, 0)} %`)

const stateColor: Record<string, string | undefined> = {
  ON_TRACK: "success",
  LAGGING: "warning",
  NO_CHANGE: "danger",
  WORSENING: "danger",
  NO_DATA: "dimmed",
}

function Metric({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <Stack gap={2}>
      <Text
        size='xs'
        c='dimmed'
      >
        {label}
      </Text>
      <Text
        fw={600}
        component='div'
      >
        {value}
      </Text>
      {hint && (
        <Text
          size='xs'
          c='dimmed'
        >
          {hint}
        </Text>
      )}
    </Stack>
  )
}

function IncidentForm({ riskId }: { riskId: string }) {
  const add = useAddIncident(riskId)
  const [form, setForm] = useState({ occurredOn: "", source: "", description: "" })
  return (
    <form
      onSubmit={e => {
        e.preventDefault()
        add.mutate(form, {
          onSuccess: () => {
            setForm({ occurredOn: "", source: "", description: "" })
            notifications.show({
              color: "success",
              message: "Інцидент зареєстровано: зʼявилась підстава переоцінити ризик",
            })
          },
          onError: err => notifications.show({ color: "danger", message: err.message }),
        })
      }}
    >
      <Stack gap='xs'>
        <Group
          grow
          align='flex-start'
        >
          <DateField
            label='Дата'
            required
            value={form.occurredOn}
            onChange={v => setForm(f => ({ ...f, occurredOn: v ?? "" }))}
          />
          <TextInput
            label='Джерело'
            placeholder='ЄДРСР, Реєстр корупціонерів, службове розслідування'
            required
            value={form.source}
            onChange={e => {
              const source = e.currentTarget.value
              setForm(f => ({ ...f, source }))
            }}
          />
        </Group>
        <Textarea
          label='Опис'
          autosize
          minRows={2}
          value={form.description}
          onChange={e => {
            const description = e.currentTarget.value
            setForm(f => ({ ...f, description }))
          }}
        />
        <Group justify='flex-end'>
          <Button
            type='submit'
            size='xs'
            leftSection={<IconPlus size={14} />}
            loading={add.isPending}
          >
            Зареєструвати підтверджений інцидент
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

function ReassessForm({ risk }: { risk: RiskAssessment }) {
  const reassess = useReassessRisk(risk.riskId)
  const suggested = risk.hints.at(-1)?.suggested
  const [form, setForm] = useState({
    probability: suggested ?? risk.probability0,
    impact: risk.impact0,
    justification: "",
  })
  const score = form.probability * form.impact
  return (
    <form
      onSubmit={e => {
        e.preventDefault()
        reassess.mutate(form, {
          onSuccess: r => {
            setForm(f => ({ ...f, justification: "" }))
            notifications.show({ color: "success", message: `Ризик переоцінено: ${r.score} — запис у журналі дій` })
          },
          onError: err => notifications.show({ color: "danger", message: err.message }),
        })
      }}
    >
      <Stack gap='xs'>
        <Group
          grow
          align='flex-start'
        >
          <NumberInput
            label='Ймовірність L'
            min={1}
            max={4}
            clampBehavior='strict'
            allowDecimal={false}
            value={form.probability}
            onChange={v => setForm(f => ({ ...f, probability: Number(v) || 1 }))}
          />
          <NumberInput
            label='Наслідки C'
            min={1}
            max={4}
            clampBehavior='strict'
            allowDecimal={false}
            value={form.impact}
            onChange={v => setForm(f => ({ ...f, impact: Number(v) || 1 }))}
          />
        </Group>
        <Textarea
          label='Обґрунтування робочої групи'
          placeholder='Напр.: протокол засідання робочої групи № 5 від 10.07.2026, вирок за ЄДРСР'
          required
          minLength={10}
          autosize
          minRows={2}
          value={form.justification}
          onChange={e => {
            const justification = e.currentTarget.value
            setForm(f => ({ ...f, justification }))
          }}
        />
        <Group justify='space-between'>
          <Text
            size='sm'
            c='dimmed'
          >
            Новий бал: {form.probability}·{form.impact} = {score}
          </Text>
          <Button
            type='submit'
            size='xs'
            leftSection={<IconScale size={14} />}
            loading={reassess.isPending}
            disabled={form.justification.trim().length < 10}
          >
            Зберегти переоцінку
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

type RiskDetailsProps = {
  risk: RiskAssessment
  canEdit: boolean
  canExplain?: boolean
}

export function RiskDetails({ risk, canEdit, canExplain }: RiskDetailsProps) {
  return (
    <Stack gap='lg'>
      <Text size='sm'>{risk.description}</Text>
      {canExplain && (
        <RiskExplain
          key={risk.riskId}
          riskId={risk.riskId}
        />
      )}

      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        <Metric
          label='Притаманний I = L₀·C₀'
          value={
            <Group gap={6}>
              {risk.probability0}·{risk.impact0} = {risk.inherent}
              <LevelBadge
                level={risk.inherentLevel}
                size='xs'
              />
            </Group>
          }
          hint='бали ставить робоча група'
        />
        <Metric
          label='Виконання заходів'
          value={`${risk.doneCount} з ${risk.measures.length}`}
          hint={risk.measures.some(m => m.pending) ? "частина подана, ще не погоджена" : undefined}
        />
        <Metric
          label='Індикатор: факт / графік'
          value={
            <Text
              span
              fw={600}
              c={stateColor[risk.effect]}
            >
              {pct(risk.rrs)} / {pct(risk.expected)}
            </Text>
          }
          hint={risk.effectLabel}
        />
        <Metric
          label='Висновок'
          value={<VerdictBadge risk={risk} />}
          hint={risk.preliminary && risk.effectDue ? `ефект можливий до ${formatDate(risk.effectDue)}` : undefined}
        />
      </SimpleGrid>

      {risk.signals.length > 0 && (
        <Group gap='xs'>
          {risk.signals.map(s => (
            <SignalBadge
              key={`${s.ruleCode}-${s.indicatorId ?? ""}`}
              signal={s}
            />
          ))}
        </Group>
      )}

      <Stack gap='xs'>
        <Text fw={600}>Індикатори ризику (KRI)</Text>
        <ScrollArea type='auto'>
          <Table
            miw={760}
            fz='sm'
            verticalSpacing={6}
          >
            <Table.Thead>
              <Table.Tr>
                <Table.Th>KRI</Table.Th>
                <Table.Th>B → T</Table.Th>
                <Table.Th>C</Table.Th>
                <Table.Th>Прогрес p</Table.Th>
                <Table.Th>За графіком</Table.Th>
                <Table.Th>Стан</Table.Th>
                <Table.Th>δ</Table.Th>
                <Table.Th>Лаг</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {risk.kris.map(k => (
                <Table.Tr key={k.indicatorId}>
                  <Table.Td maw={260}>
                    <Group
                      gap={4}
                      wrap='nowrap'
                    >
                      {k.direction === "LOWER" ? <IconArrowDown size={14} /> : <IconArrowUp size={14} />}
                      <Text
                        size='sm'
                        lineClamp={2}
                      >
                        {k.name}
                      </Text>
                    </Group>
                    <Text
                      size='xs'
                      c='dimmed'
                    >
                      {k.source || "джерело не вказано"}
                      {!k.independent && " · самозвіт (позитивний p × 0,5)"}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {num(k.baseline)} → {num(k.target)} {k.unit}
                    {k.targetDate && (
                      <Text
                        size='xs'
                        c='dimmed'
                      >
                        до {formatDate(k.targetDate)}
                      </Text>
                    )}
                    {k.baselineChanged && (
                      <Badge
                        ml={4}
                        size='xs'
                        color='orange'
                        variant='light'
                      >
                        B1
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {num(k.current)}
                    {k.measuredAt && (
                      <Text
                        size='xs'
                        c='dimmed'
                      >
                        {formatDate(k.measuredAt)}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Tooltip
                      label={
                        k.insufficient.length
                          ? k.insufficient.join("; ")
                          : k.noise
                            ? "|C − B| < δ: зміна в межах шуму, p = 0"
                            : `сирий прогрес ${num(k.raw)}`
                      }
                      multiline
                      w={260}
                    >
                      <Text
                        size='sm'
                        fw={600}
                        c={stateColor[k.state]}
                      >
                        {pct(k.p)}
                        {k.noise && " (шум)"}
                      </Text>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td>{pct(k.expected)}</Table.Td>
                  <Table.Td>{k.stateLabel}</Table.Td>
                  <Table.Td>{num(k.delta, 1)}</Table.Td>
                  <Table.Td>{k.lagMonths} міс.</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      </Stack>

      <Stack gap='xs'>
        <Text fw={600}>Заходи щодо ризику</Text>
        {risk.measures.length ? (
          <Table
            fz='sm'
            verticalSpacing={6}
          >
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Захід</Table.Th>
                <Table.Th w={190}>Статус</Table.Th>
                <Table.Th>Виконано</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {risk.measures.map(m => (
                <Table.Tr key={m.measureId}>
                  <Table.Td>
                    <Text
                      size='sm'
                      lineClamp={1}
                    >
                      {m.code} {m.title}
                    </Text>
                  </Table.Td>
                  <Table.Td>{m.status && <StatusBadge status={m.status} />}</Table.Td>
                  <Table.Td>
                    {m.done
                      ? `${m.pending ? "подано" : "так"}${m.completedOn ? `, ${formatDate(m.completedOn)}` : ""}`
                      : "ні"}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <Text
            size='sm'
            c='dimmed'
          >
            Затверджених заходів щодо ризику немає.
          </Text>
        )}
      </Stack>

      <Stack gap='xs'>
        <Text fw={600}>Підстави для переоцінки ймовірності</Text>
        {risk.hints.length ? (
          risk.hints.map(h => (
            <Alert
              key={h.rule}
              variant='light'
              color={signalColor[h.rule === "L-1" ? "green" : h.rule === "P1" ? "red" : "orange"]}
              icon={<IconBulb size={18} />}
              title={`${h.rule} · пропонується L = ${h.suggested}`}
            >
              <Text size='sm'>{h.text}</Text>
              {h.source && (
                <Text
                  size='xs'
                  c='dimmed'
                >
                  Джерело: {h.source}
                </Text>
              )}
            </Alert>
          ))
        ) : (
          <Text
            size='sm'
            c='dimmed'
          >
            Підстав немає: бал у реєстрі узгоджується з даними індикатора та інцидентами.
          </Text>
        )}
        <Text
          size='xs'
          c='dimmed'
        >
          Система бал НАЗК не змінює: переоцінку ухвалює робоча група з обґрунтуванням, зміна йде в журнал дій.
        </Text>
        {canEdit && (
          <ReassessForm
            key={risk.riskId}
            risk={risk}
          />
        )}
      </Stack>

      <Stack gap='xs'>
        <Text fw={600}>Підтверджені інциденти</Text>
        {risk.incidents.length ? (
          risk.incidents.map(i => (
            <Text
              key={i.id}
              size='sm'
            >
              <b>{formatDate(i.occurredOn)}</b> · {i.source}
              {i.description ? ` — ${i.description}` : ""}
            </Text>
          ))
        ) : (
          <Text
            size='sm'
            c='dimmed'
          >
            Інцидентів немає.
          </Text>
        )}
        {canEdit && <IncidentForm riskId={risk.riskId} />}
      </Stack>

      <Text
        size='xs'
        c='dimmed'
      >
        Розрахунок на {formatDate(risk.asOf)} · правила {risk.rulesetVersion}. Статуси й прапорці ставлять лише
        версіоновані правила; ШІ лише пропонує.
      </Text>
    </Stack>
  )
}
