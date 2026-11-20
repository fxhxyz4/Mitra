import { Group, Stack, Text } from "@mantine/core"
import { Link } from "react-router"
import type { MeasureListItem, NonExecutionRisk } from "@/shared/api"
import type { ReactNode } from "react"

import { FlagBadge, LevelBadge, StatusBadge } from "./Badges"
import { Deadline } from "./Deadline"
import { EmptyState } from "./EmptyState"
import classes from "./MeasureList.module.scss"
import { measurePath } from "./measurePath"

type Item = MeasureListItem & { nonExecutionRisk?: NonExecutionRisk }

type MeasureListProps = {
  items: Item[]
  empty?: string
  emptyText?: ReactNode
  extra?: (item: Item) => ReactNode
  showUnit?: boolean
}

const closed = (item: Item) => item.status === "DONE" || item.status === "PARTIAL" || item.status === "NOT_DONE"

export function MeasureList({ items, empty = "Заходів немає", emptyText, extra, showUnit = true }: MeasureListProps) {
  if (!items.length)
    return (
      <EmptyState
        title={empty}
        text={emptyText}
      />
    )

  return (
    <div className={classes.list}>
      {items.map(item => {
        const accent =
          item.isOverdue && !closed(item)
            ? classes.danger
            : item.nonExecutionRisk?.level === "HIGH"
              ? classes.danger
              : item.status === "RETURNED"
                ? classes.warn
                : ""
        return (
          <Link
            key={item.id}
            to={measurePath(item.id)}
            className={`${classes.row} ${accent}`}
          >
            <span className={classes.code}>{item.code}</span>
            <Stack
              gap={4}
              className={classes.title}
            >
              <Text
                fw={500}
                lineClamp={2}
              >
                {item.title}
              </Text>
              <Group gap={6}>
                {showUnit && item.responsibleUnit && (
                  <Text
                    size='xs'
                    c='dimmed'
                  >
                    {item.responsibleUnit}
                  </Text>
                )}
                {item.risk && (
                  <Text
                    size='xs'
                    c='dimmed'
                  >
                    · {item.risk.code}
                  </Text>
                )}
                {item.isPermanent && (
                  <Text
                    size='xs'
                    c='dimmed'
                  >
                    · постійний
                  </Text>
                )}
              </Group>
              {(item.openFlags.length > 0 || item.nonExecutionRisk?.level === "HIGH") && (
                <Group gap={6}>
                  {item.nonExecutionRisk?.level === "HIGH" && (
                    <LevelBadge
                      level='HIGH'
                      prefix='Ризик невиконання'
                      size='sm'
                    />
                  )}
                  {item.openFlags.map(f => (
                    <FlagBadge
                      key={f.id}
                      type={f.type}
                      explanation={f.explanation}
                      size='sm'
                    />
                  ))}
                </Group>
              )}
              {extra?.(item)}
            </Stack>
            <div className={classes.status}>
              <StatusBadge status={item.status} />
            </div>
            <div className={classes.deadline}>
              <Deadline
                date={item.deadline}
                daysLeft={item.daysLeft}
                overdue={item.isOverdue}
                closed={closed(item)}
              />
            </div>
          </Link>
        )
      })}
    </div>
  )
}
