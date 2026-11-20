import { useState } from "react"
import { ActionIcon, Indicator, Popover, ScrollArea, Stack, Text, UnstyledButton } from "@mantine/core"
import { IconBell } from "@tabler/icons-react"
import { Link } from "react-router"

import { useReminders } from "@/features/auth"
import { formatDateTime } from "@/shared/lib"
import { measurePath } from "@/shared/ui"
import { dropdownWidth, headerDropdown } from "./dropdown"

export function Reminders() {
  const { data = [] } = useReminders()
  const [opened, setOpened] = useState(false)
  const recent = data.slice(0, 12)

  return (
    <Indicator
      disabled={!data.length}
      label={data.length > 9 ? "9+" : data.length}
      size={16}
      color='danger'
      offset={4}
    >
      <Popover
        opened={opened}
        onChange={setOpened}
        {...headerDropdown}
        width={dropdownWidth(340)}
      >
        <Popover.Target>
          <ActionIcon
            variant='default'
            size='lg'
            aria-label={data.length ? `Нагадування: ${data.length}` : "Нагадування"}
            onClick={() => setOpened(o => !o)}
          >
            <IconBell size={18} />
          </ActionIcon>
        </Popover.Target>
        <Popover.Dropdown p={0}>
          <Text
            fw={600}
            p='sm'
            pb={4}
          >
            Нагадування
          </Text>
          <ScrollArea.Autosize mah={360}>
            <Stack
              gap={0}
              pb='xs'
            >
              {recent.map(r => (
                <UnstyledButton
                  key={r.id}
                  component={Link}
                  to={measurePath(r.measureId)}
                  onClick={() => setOpened(false)}
                  px='sm'
                  py={8}
                  style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}
                >
                  <Text
                    size='sm'
                    lineClamp={2}
                  >
                    {r.text}
                  </Text>
                  <Text
                    size='xs'
                    c='dimmed'
                  >
                    {formatDateTime(r.sendAt)}
                  </Text>
                </UnstyledButton>
              ))}
              {!recent.length && (
                <Text
                  size='sm'
                  c='dimmed'
                  px='sm'
                  pb='xs'
                >
                  Нових нагадувань немає
                </Text>
              )}
            </Stack>
          </ScrollArea.Autosize>
        </Popover.Dropdown>
      </Popover>
    </Indicator>
  )
}
