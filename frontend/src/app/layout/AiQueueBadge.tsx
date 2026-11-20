import { Badge, Loader, Tooltip } from "@mantine/core"

import { useAiQueue } from "@/shared/api"

export function AiQueueBadge() {
  const jobs = useAiQueue()
  if (!jobs.length) return null
  const ahead = Math.min(...jobs.map(j => j.ahead))
  const waiting = jobs.every(j => j.status === "queued") && ahead > 0
  const label = waiting ? `ШІ: у черзі ${ahead}` : "ШІ готує відповідь"
  return (
    <Tooltip
      label='Можна працювати далі: результат зʼявиться, коли модель відповість'
      withArrow
    >
      <Badge
        variant='light'
        color='blue'
        leftSection={<Loader size={10} />}
        visibleFrom='xs'
        aria-live='polite'
      >
        {jobs.length > 1 ? `${label} · задач ${jobs.length}` : label}
      </Badge>
    </Tooltip>
  )
}
