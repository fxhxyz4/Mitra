import { Accordion, Badge, Group, Text } from "@mantine/core"
import type { SectionPassport } from "@/shared/api"

import { sectionShort } from "@/shared/lib"
import { MeasureList } from "@/shared/ui"

export function PassportView({ sections }: { sections: SectionPassport[] }) {
  return (
    <Accordion
      multiple
      defaultValue={sections.map(s => s.id)}
      variant='separated'
      chevronPosition='left'
    >
      {sections.map(s => {
        const done = s.measures.filter(m => m.status === "DONE").length
        const overdue = s.measures.filter(
          m => m.isOverdue && m.status !== "DONE" && m.status !== "PARTIAL" && m.status !== "NOT_DONE"
        ).length
        return (
          <Accordion.Item
            key={s.id}
            value={s.id}
          >
            <Accordion.Control>
              <Group
                justify='space-between'
                wrap='nowrap'
                pr='sm'
              >
                <div>
                  <Text fw={600}>
                    Розділ {s.number}. {sectionShort[s.number]}
                  </Text>
                  <Text
                    size='xs'
                    c='dimmed'
                    lineClamp={1}
                  >
                    {s.title}
                  </Text>
                </div>
                <Group
                  gap={6}
                  wrap='nowrap'
                >
                  <Badge
                    variant='light'
                    color='gray'
                  >
                    {s.measures.length}
                  </Badge>
                  <Badge
                    variant='light'
                    color='success'
                  >
                    ✓ {done}
                  </Badge>
                  {overdue > 0 && (
                    <Badge
                      variant='light'
                      color='danger'
                    >
                      ⏰ {overdue}
                    </Badge>
                  )}
                </Group>
              </Group>
            </Accordion.Control>
            <Accordion.Panel>
              <MeasureList
                items={s.measures}
                empty='У розділі ще немає заходів'
              />
            </Accordion.Panel>
          </Accordion.Item>
        )
      })}
    </Accordion>
  )
}
