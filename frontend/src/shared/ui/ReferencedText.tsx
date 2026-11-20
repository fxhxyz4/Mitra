import { Anchor, Badge, Group, List, Stack, Text } from "@mantine/core"
import { Link } from "react-router"
import type { EntityType, SourceRef } from "@/shared/api"

import { session } from "@/shared/api"
import { paths } from "@/shared/config"
import { measurePath } from "./measurePath"
import { canOpen } from "./pageAccess"

const typeLabel: Record<EntityType, string> = {
  risk: "ризик",
  indicator: "індикатор",
  measure: "захід",
  period: "період",
  flag: "Risk Flag",
  signal: "сигнал",
  evidence: "документ",
  recommendation: "рекомендація",
}

const hrefFor = (ref: SourceRef) => {
  const role = session.role()
  const opens = (path: string) => canOpen(path, role)
  const measure = (id?: string | null) =>
    id && (opens(paths.measure) || opens(paths.myMeasure)) ? measurePath(id) : null
  switch (ref.type) {
    case "measure":
      return measure(ref.id)
    case "flag":
      return measure(ref.target) ?? (opens(paths.flags) ? paths.flags : null)
    case "risk":
      return opens(paths.riskModel) ? `${paths.riskModel}?risk=${ref.id}` : measure(ref.target)
    case "signal":
      if (!opens(paths.riskModel)) return null
      return ref.target ? `${paths.riskModel}?risk=${ref.target}` : paths.riskModel
    case "recommendation":
      return opens(paths.recommendations) ? paths.recommendations : measure(ref.target)
    default:
      return null
  }
}

function Marker({ n, source }: { n: string; source?: SourceRef }) {
  const href = source ? hrefFor(source) : null
  const label = `[${n}]`
  if (!source || !href)
    return (
      <Text
        span
        c='dimmed'
        fz='xs'
        fw={600}
        title={source?.label}
      >
        {label}
      </Text>
    )
  return (
    <Anchor
      component={Link}
      to={href}
      fz='xs'
      fw={700}
      title={source.label}
    >
      {label}
    </Anchor>
  )
}

function Inline({ text, byN }: { text: string; byN: Map<string, SourceRef> }) {
  const parts = text.split(/(\[\d+(?:\s*[,;]\s*\d+)*\])/g)
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(\d+(?:\s*[,;]\s*\d+)*)\]$/.exec(part)
        if (!m) return part
        return m[1]!.split(/\s*[,;]\s*/).map((n, j) => (
          <Marker
            key={`${i}-${j}`}
            n={n}
            source={byN.get(n)}
          />
        ))
      })}
    </>
  )
}

const BULLET = /^\s*[•\-*]\s+/

export function ReferencedText({
  text,
  references,
  showSources = true,
}: {
  text: string
  references: SourceRef[]
  showSources?: boolean
}) {
  const byN = new Map(references.map(r => [String(r.n), r]))
  const blocks = text
    .split(/\n\s*\n/)
    .map(b => b.split("\n").filter(l => l.trim()))
    .filter(b => b.length)
  return (
    <Stack gap='sm'>
      {blocks.map((lines, bi) => {
        const bullets = lines.filter(l => BULLET.test(l))
        const heading = bullets.length && !BULLET.test(lines[0]!) ? lines[0] : null
        if (!bullets.length)
          return (
            <Text
              key={bi}
              size='sm'
              style={{ whiteSpace: "pre-wrap" }}
            >
              <Inline
                text={lines.join("\n")}
                byN={byN}
              />
            </Text>
          )
        return (
          <Stack
            key={bi}
            gap={4}
          >
            {heading && (
              <Text
                size='xs'
                fw={700}
                tt='uppercase'
                c='dimmed'
              >
                {heading}
              </Text>
            )}
            <List
              size='sm'
              spacing={4}
            >
              {bullets.map((line, li) => (
                <List.Item key={li}>
                  <Inline
                    text={line.replace(BULLET, "")}
                    byN={byN}
                  />
                </List.Item>
              ))}
            </List>
          </Stack>
        )
      })}
      {showSources && references.length > 0 && (
        <Stack gap={8}>
          {references.map(r => {
            const href = hrefFor(r)
            return (
              <Group
                key={r.n}
                gap={6}
                wrap='nowrap'
                align='flex-start'
              >
                <Text
                  size='xs'
                  fw={700}
                  w={26}
                  style={{ flexShrink: 0 }}
                >
                  [{r.n}]
                </Text>
                <Badge
                  size='xs'
                  variant='outline'
                  color='gray'
                  style={{ flexShrink: 0 }}
                >
                  {typeLabel[r.type]}
                </Badge>
                {href ? (
                  <Anchor
                    component={Link}
                    to={href}
                    size='xs'
                    display='inline-block'
                    py={4}
                    my={-4}
                  >
                    {r.label}
                  </Anchor>
                ) : (
                  <Text size='xs'>{r.label}</Text>
                )}
              </Group>
            )
          })}
        </Stack>
      )}
    </Stack>
  )
}
