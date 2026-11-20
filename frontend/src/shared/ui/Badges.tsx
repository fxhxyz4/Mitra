import { Badge, Tooltip } from "@mantine/core"
import type { FlagType, MeasureStatus, RecStatus, RiskLevel, Role } from "@/shared/api"
import type { BadgeProps } from "@mantine/core"

import { flagMeta, levelMeta, recMeta, roleMeta, statusMeta } from "@/shared/lib"

type Base = Omit<BadgeProps, "color" | "children">

export function StatusBadge({ status, ...props }: Base & { status: MeasureStatus | null }) {
  if (!status) return null
  const meta = statusMeta[status]
  return (
    <Badge
      variant='light'
      color={meta.color}
      {...props}
    >
      {meta.label}
    </Badge>
  )
}

export function FlagBadge({ type, explanation, ...props }: Base & { type: FlagType; explanation?: string }) {
  const meta = flagMeta[type]
  const badge = (
    <Badge
      variant='dot'
      color={meta.color}
      {...props}
    >
      {meta.rule} · {meta.label}
    </Badge>
  )
  return explanation ? (
    <Tooltip
      label={explanation}
      multiline
      maw={320}
      withArrow
    >
      {badge}
    </Tooltip>
  ) : (
    badge
  )
}

export function LevelBadge({ level, prefix, ...props }: Base & { level: RiskLevel; prefix?: string }) {
  const meta = levelMeta[level]
  return (
    <Badge
      variant='light'
      color={meta.color}
      {...props}
    >
      {prefix ? `${prefix}: ` : ""}
      {meta.label}
    </Badge>
  )
}

export function RoleBadge({ role, ...props }: Base & { role: Role }) {
  const meta = roleMeta[role]
  return (
    <Badge
      variant='light'
      color={meta.color}
      {...props}
    >
      {meta.label}
    </Badge>
  )
}

export function RecBadge({ status, ...props }: Base & { status: RecStatus }) {
  const meta = recMeta[status]
  return (
    <Badge
      variant='light'
      color={meta.color}
      {...props}
    >
      {meta.label}
    </Badge>
  )
}
