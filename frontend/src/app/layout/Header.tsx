import { Burger, Divider, Group, UnstyledButton } from "@mantine/core"
import { Link } from "react-router"
import type { CSSProperties } from "react"

import { useSession } from "@/shared/api"
import { paths } from "@/shared/config"
import { Logo } from "@/shared/ui"
import { AiQueueBadge } from "./AiQueueBadge"
import { AppearanceMenu } from "./AppearanceMenu"
import { Reminders } from "./Reminders"
import { UserMenu } from "./UserMenu"

type HeaderProps = { opened: boolean; onToggle: () => void }

export function Header({ opened, onToggle }: HeaderProps) {
  const { user } = useSession()

  return (
    <Group
      h='100%'
      px='md'
      justify='space-between'
      wrap='nowrap'
    >
      <Group
        gap='sm'
        wrap='nowrap'
      >
        <Burger
          opened={opened}
          onClick={onToggle}
          hiddenFrom='sm'
          size='sm'
          aria-label='Меню'
        />
        <UnstyledButton
          component={Link}
          to={paths.home}
          aria-label='Mitra — на головну'
        >
          <Logo />
        </UnstyledButton>
      </Group>

      <Group
        gap='xs'
        wrap='nowrap'
      >
        {user && <AiQueueBadge />}
        <AppearanceMenu />
        {user && (
          <>
            <Divider
              orientation='vertical'
              size='sm'
              my={10}
              mx={2}
              visibleFrom='xs'
              style={
                { "--divider-color": "color-mix(in srgb, var(--mantine-color-text) 24%, transparent)" } as CSSProperties
              }
            />
            <Reminders />
            <UserMenu />
          </>
        )}
      </Group>
    </Group>
  )
}
