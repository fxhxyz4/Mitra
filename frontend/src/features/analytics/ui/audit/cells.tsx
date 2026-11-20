import { Anchor, Text } from "@mantine/core"
import { Link } from "react-router"

import { measurePath } from "@/shared/ui"

export function Num({ value, bad, muted }: { value: number; bad?: boolean; muted?: boolean }) {
  return (
    <Text
      size='sm'
      fw={bad && value > 0 ? 600 : undefined}
      c={bad && value > 0 ? "danger" : muted || value === 0 ? "dimmed" : undefined}
    >
      {value}
    </Text>
  )
}

export function MeasureLink({ id, code, title }: { id: string; code: string; title: string }) {
  return (
    <Anchor
      component={Link}
      to={measurePath(id)}
      size='sm'
      onClick={e => e.stopPropagation()}
    >
      <Text
        span
        fw={600}
        size='sm'
      >
        {code}
      </Text>{" "}
      {title}
    </Anchor>
  )
}
