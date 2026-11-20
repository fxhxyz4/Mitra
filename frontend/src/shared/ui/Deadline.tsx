import { Text } from "@mantine/core"
import { IconAlarm, IconCalendarEvent } from "@tabler/icons-react"

import { formatDate, formatDaysLeft } from "@/shared/lib"

type DeadlineProps = { date: string; daysLeft: number; overdue?: boolean; closed?: boolean; size?: "xs" | "sm" }

export function Deadline({ date, daysLeft, overdue, closed, size = "sm" }: DeadlineProps) {
  const late = overdue && !closed
  const color = closed ? "dimmed" : late ? "danger" : daysLeft <= 7 ? "orange" : undefined
  const Icon = late ? IconAlarm : IconCalendarEvent
  return (
    <Text
      size={size}
      c={color}
      fw={late ? 600 : undefined}
      style={{ whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 6 }}
    >
      <Icon
        size={size === "xs" ? 14 : 16}
        stroke={1.6}
      />
      {formatDate(date)}
      {!closed && (
        <Text
          span
          inherit
          c={color ?? "dimmed"}
          fw={400}
        >
          · {formatDaysLeft(daysLeft)}
        </Text>
      )}
    </Text>
  )
}
