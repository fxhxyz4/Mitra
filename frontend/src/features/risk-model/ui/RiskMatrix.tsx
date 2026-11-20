import { Badge, Group, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core"
import type { RiskAssessment, RiskLevel, RiskVerdict, UncoveredRisk } from "@/shared/api"
import type { CSSProperties } from "react"

import { signalColor } from "@/shared/lib"
import classes from "./RiskMatrix.module.scss"

/** Колір коду ризику, читабельний в обох темах (див. `.badge` у стилях). */
const chip = (color: string) => ({ "--chip-color": `var(--mantine-color-${color}-text)` }) as CSSProperties

const LIKELIHOOD = [
  4,
  3,
  2,
  1,
]
const CONSEQUENCES = [
  1,
  2,
  3,
  4,
]

/** Межі рівнів за Методологією НАЗК № 830/21: 1–2 низький, 3–4 середній, 6–9 високий, 12–16 критичний. */
const levelOf = (score: number): RiskLevel =>
  score >= 12 ? "CRITICAL" : score >= 6 ? "HIGH" : score >= 3 ? "MEDIUM" : "LOW"

const verdictLegend: { verdict: RiskVerdict; label: string; color: string }[] = [
  { verdict: "WORKING", label: "Заходи працюють", color: "green" },
  { verdict: "FORMAL", label: "Закрито «на папері»", color: "red" },
  { verdict: "WORSE_DESPITE", label: "Погіршення попри виконання", color: "red" },
  { verdict: "UNATTENDED", label: "Ризик росте без реакції", color: "red" },
  { verdict: "STAGNANT", label: "Не виконано, змін немає", color: "yellow" },
  { verdict: "EXTERNAL", label: "Покращення без заходів", color: "gray" },
  { verdict: "NO_MEASURES", label: "Немає заходів", color: "orange" },
]

type RiskMatrixProps = {
  risks: RiskAssessment[]
  uncovered?: UncoveredRisk[]
  onSelect?: (riskId: string) => void
}

/** Матриця НАЗК 4×4 (ймовірність × наслідки): у клітинці — ризики з цим балом, колір — висновок за даними. */
export function RiskMatrix({ risks, uncovered = [], onSelect }: RiskMatrixProps) {
  const at = (l: number, c: number) => risks.filter(r => r.probability0 === l && r.impact0 === c)
  const gapsAt = (l: number, c: number) => uncovered.filter(r => r.probability0 === l && r.impact0 === c)
  return (
    <Stack gap='sm'>
      <div
        className={classes.grid}
        role='grid'
        aria-label='Матриця ризиків НАЗК: ймовірність × наслідки'
      >
        {LIKELIHOOD.map(l => (
          <div
            key={l}
            role='row'
            style={{ display: "contents" }}
          >
            <div
              className={classes.axis}
              role='rowheader'
              title={`Ймовірність ${l}`}
            >
              {l}
            </div>
            {CONSEQUENCES.map(c => (
              <div
                key={c}
                role='gridcell'
                className={classes.cell}
                data-level={levelOf(l * c)}
              >
                <span className={classes.score}>{l * c}</span>
                <div className={classes.chips}>
                  {at(l, c).map(r => (
                    <Tooltip
                      key={r.riskId}
                      label={`${r.description} — ${r.verdictLabel}${r.preliminary ? " (попередньо)" : ""}`}
                      multiline
                      w={260}
                      withArrow
                    >
                      <UnstyledButton
                        className={classes.chip}
                        onClick={() => onSelect?.(r.riskId)}
                        aria-label={`${r.code}: ${r.verdictLabel}`}
                      >
                        <Badge
                          size='sm'
                          variant='light'
                          className={classes.badge}
                          data-preliminary={r.preliminary || undefined}
                          style={chip(signalColor[r.verdictColor] ?? "gray")}
                        >
                          {r.code}
                        </Badge>
                      </UnstyledButton>
                    </Tooltip>
                  ))}
                  {gapsAt(l, c).map(r => (
                    <Tooltip
                      key={r.riskId}
                      label={`${r.description} — у програмі немає жодного заходу`}
                      multiline
                      w={260}
                      withArrow
                    >
                      <Badge
                        size='sm'
                        variant='light'
                        className={classes.badge}
                        data-preliminary
                        style={chip("orange")}
                      >
                        {r.code}
                      </Badge>
                    </Tooltip>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ))}
        <div />
        {CONSEQUENCES.map(c => (
          <div
            key={c}
            className={classes.axis}
            title={`Наслідки ${c}`}
          >
            {c}
          </div>
        ))}
      </div>
      <Text
        size='xs'
        c='dimmed'
        ta='center'
      >
        Рядки — ймовірність, стовпці — наслідки (бали ставить робоча група). Колір ризику — висновок за даними;
        пунктирна рамка — попередній висновок (лаг ефекту ще не минув).
      </Text>
      <Group
        gap='xs'
        justify='center'
      >
        {verdictLegend.map(v => (
          <Badge
            key={v.verdict}
            size='xs'
            variant='light'
            className={classes.badge}
            data-preliminary={v.verdict === "NO_MEASURES" || undefined}
            style={chip(signalColor[v.color] ?? "gray")}
          >
            {v.label}
          </Badge>
        ))}
      </Group>
    </Stack>
  )
}
