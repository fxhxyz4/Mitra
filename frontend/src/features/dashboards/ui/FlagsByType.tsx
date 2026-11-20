import { Group, Progress, Stack, Text } from "@mantine/core"
import { Link } from "react-router"
import type { FlagType } from "@/shared/api"

import { paths } from "@/shared/config"
import { flagMeta, flagOrder } from "@/shared/lib"

export function FlagsByType({ counts }: { counts: Record<FlagType, number> }) {
  const max = Math.max(1, ...Object.values(counts))
  return (
    <Stack gap='sm'>
      {flagOrder.map(t => (
        <Link
          key={t}
          to={`${paths.flags}?type=${t}`}
          style={{ color: "inherit", textDecoration: "none" }}
        >
          <Group
            justify='space-between'
            mb={4}
            wrap='nowrap'
          >
            <Text size='sm'>
              <Text
                span
                c='dimmed'
                ff='monospace'
                size='xs'
              >
                {flagMeta[t].rule}
              </Text>{" "}
              {flagMeta[t].label}
            </Text>
            <Text
              size='sm'
              fw={600}
            >
              {counts[t] ?? 0}
            </Text>
          </Group>
          <Progress
            value={((counts[t] ?? 0) / max) * 100}
            color={flagMeta[t].color}
            aria-label={flagMeta[t].label}
            size='sm'
            radius='xl'
          />
        </Link>
      ))}
    </Stack>
  )
}
