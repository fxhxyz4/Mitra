import { Badge, Tooltip } from "@mantine/core"
import type { RiskAssessment } from "@/shared/api"

import { formatDate, signalColor } from "@/shared/lib"

type VerdictBadgeProps = {
  risk: Pick<RiskAssessment, "verdictLabel" | "verdictColor" | "effectLabel" | "preliminary" | "effectDue">
  size?: "xs" | "sm" | "md"
}

/** Висновок «виконання × ефект»; «попередньо» — лаг ефекту виконаних заходів ще не минув. */
export function VerdictBadge({ risk, size = "sm" }: VerdictBadgeProps) {
  const color = signalColor[risk.verdictColor] ?? "gray"
  const note = risk.preliminary
    ? `Висновок попередній: ефект заходів можливий до ${risk.effectDue ? formatDate(risk.effectDue) : "кінця лагу"}.`
    : null
  return (
    <Tooltip
      label={[`Індикатор ризику: ${risk.effectLabel}.`, note].filter(Boolean).join(" ")}
      multiline
      w={280}
      withArrow
    >
      <Badge
        size={size}
        variant='light'
        color={color}
        // Довгі назви («Закрито «на папері» · попередньо») переносяться, а не обрізаються
        h='auto'
        py={2}
        styles={{ label: { whiteSpace: "normal", overflow: "visible", textOverflow: "clip" } }}
        // Пунктир — попередній висновок; колір лишається кольором вердикту в обох темах
        style={{
          cursor: "help",
          maxWidth: "100%",
          border: `1px ${risk.preliminary ? "dashed" : "solid"} var(--mantine-color-${color}-text)`,
        }}
      >
        {risk.verdictLabel}
        {risk.preliminary ? " · попередньо" : ""}
      </Badge>
    </Tooltip>
  )
}
