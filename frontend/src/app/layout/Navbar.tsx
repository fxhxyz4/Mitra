import { NavLink, ScrollArea, Stack, Text } from "@mantine/core"
import { Link, useLocation } from "react-router"

import { navigationFor } from "@/app/router/navigation"
import { preload } from "@/app/router/pages"
import { useSession } from "@/shared/api"

export function Navbar({ onNavigate }: { onNavigate: () => void }) {
  const { pathname } = useLocation()
  const { user } = useSession()
  const groups = navigationFor(user?.role)

  return (
    <Stack
      h='100%'
      justify='space-between'
      gap='md'
    >
      <ScrollArea
        type='never'
        style={{ flex: 1 }}
      >
        <Stack gap='md'>
          {groups.map(({ group, items }) => (
            <Stack
              key={group}
              gap={2}
            >
              {groups.length > 1 && (
                <Text
                  size='xs'
                  fw={700}
                  c='dimmed'
                  tt='uppercase'
                  px='sm'
                  lts={0.4}
                  mb={2}
                >
                  {group}
                </Text>
              )}
              {items.map(({ to, label, icon: Icon, load }) => (
                <NavLink
                  key={to}
                  component={Link}
                  to={to}
                  label={label}
                  leftSection={
                    <Icon
                      size={20}
                      stroke={1.6}
                    />
                  }
                  active={pathname === to || pathname.startsWith(`${to}/`)}
                  onClick={onNavigate}
                  onMouseEnter={() => preload(load)}
                  onFocus={() => preload(load)}
                  styles={{ root: { borderRadius: "var(--mantine-radius-md)" } }}
                />
              ))}
            </Stack>
          ))}
        </Stack>
      </ScrollArea>

      <Text
        size='xs'
        c='dimmed'
        px='sm'
      >
        v{__APP_VERSION__} · BITEC Hackathon 2026
      </Text>
    </Stack>
  )
}
