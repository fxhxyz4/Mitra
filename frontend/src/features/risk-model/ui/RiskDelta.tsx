import { Badge, Tooltip } from "@mantine/core"
import { IconArrowDownRight, IconArrowUpRight } from "@tabler/icons-react"

type RiskDeltaProps = {
  current: number | null | undefined
  previous: number | null | undefined
  higherIsWorse?: boolean
  digits?: number
  suffix?: string
  label?: string
}

const EPS = 1e-6

export function RiskDelta({ current, previous, higherIsWorse = true, digits = 1, suffix = "", label }: RiskDeltaProps) {
  if (current === null || current === undefined || previous === null || previous === undefined) return null
  const diff = current - previous
  if (Math.abs(diff) < EPS) return null
  const worse = higherIsWorse ? diff > 0 : diff < 0
  const Icon = diff > 0 ? IconArrowUpRight : IconArrowDownRight
  const text = `${diff > 0 ? "+" : "−"}${Math.abs(diff).toLocaleString("uk-UA", { maximumFractionDigits: digits })}${suffix}`
  return (
    <Tooltip
      label={`${label ?? "Порівняно з датою порівняння"}: було ${previous.toLocaleString("uk-UA", { maximumFractionDigits: digits })}${suffix}`}
    >
      <Badge
        size='xs'
        variant='light'
        color={worse ? "danger" : "success"}
        leftSection={<Icon size={11} />}
      >
        {text}
      </Badge>
    </Tooltip>
  )
}
