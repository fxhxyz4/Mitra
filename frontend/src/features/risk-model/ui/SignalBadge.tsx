import { Badge, Tooltip } from "@mantine/core"
import type { RiskSignal } from "@/shared/api"

import { signalColor } from "@/shared/lib"

export function SignalBadge({ signal }: { signal: RiskSignal }) {
  return (
    <Tooltip
      label={signal.explanation}
      multiline
      w={320}
      withArrow
    >
      <Badge
        variant='light'
        color={signalColor[signal.color] ?? "gray"}
        style={{ cursor: "help" }}
      >
        {signal.ruleCode} · {signal.label}
      </Badge>
    </Tooltip>
  )
}
