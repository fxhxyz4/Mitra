import { Group, Text } from "@mantine/core"
import { Link } from "react-router"
import type { UnitCell } from "@/shared/api"

import { paths, withId } from "@/shared/config"
import { EmptyState, LevelBadge } from "@/shared/ui"
import classes from "./RiskHeatMap.module.scss"

export function RiskHeatMap({ units }: { units: UnitCell[] }) {
  if (!units.length) return <EmptyState title='Підрозділів немає' />
  return (
    <div className={classes.grid}>
      {units.map(u => (
        <Link
          key={u.orgUnitId}
          to={withId(paths.unit, u.orgUnitId)}
          className={classes.cell}
          data-level={u.level}
        >
          <Group
            justify='space-between'
            wrap='nowrap'
            align='flex-start'
            gap='xs'
          >
            <Text
              fw={600}
              size='sm'
              lineClamp={2}
            >
              {u.name}
            </Text>
            <LevelBadge
              level={u.level}
              size='xs'
              variant='filled'
              c='var(--app-on-filled, var(--mantine-color-white))'
              style={{ flexShrink: 0 }}
            />
          </Group>
          <Text size='xs'>
            Заходів {u.total} · прострочено {u.overdue} · прапорців {u.openFlags}
          </Text>
          {u.reasons.map(r => (
            <Text
              key={r}
              size='xs'
              c='dimmed'
            >
              {r}
            </Text>
          ))}
        </Link>
      ))}
    </div>
  )
}
