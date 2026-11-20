import { Avatar, Group, Menu, Switch, Text, UnstyledButton, VisuallyHidden } from "@mantine/core"
import { IconLogout, IconSparkles, IconSwitchHorizontal } from "@tabler/icons-react"
import { useNavigate } from "react-router"

import { useLogout } from "@/features/auth"
import { useAiPreference, useAiStatus, useSession } from "@/shared/api"
import { paths } from "@/shared/config"
import { roleMeta } from "@/shared/lib"
import { dropdownWidth, headerDropdown } from "./dropdown"

const initials = (name: string) =>
  name
    .split(/[\s—-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(w => w[0]?.toUpperCase())
    .join("")

export function UserMenu() {
  const { user } = useSession()
  const logout = useLogout()
  const navigate = useNavigate()
  const [aiEnabled, setAiEnabled] = useAiPreference()
  const aiStatus = useAiStatus()
  const adminOff = aiStatus.data?.enabled === false
  if (!user) return null
  const meta = roleMeta[user.role]

  const exit = () => {
    logout()
    navigate(paths.login, { replace: true })
  }

  return (
    <Menu
      {...headerDropdown}
      width={dropdownWidth(260)}
    >
      <Menu.Target>
        <UnstyledButton>
          <Group
            gap='xs'
            wrap='nowrap'
          >
            <Avatar
              aria-hidden
              color={meta.color}
              radius='xl'
              size={34}
            >
              {initials(user.displayName)}
            </Avatar>
            <div style={{ lineHeight: 1.1 }}>
              <Text
                size='sm'
                fw={600}
                visibleFrom='md'
                maw={180}
                truncate
              >
                {user.displayName}
              </Text>
              <Text
                size='xs'
                c='dimmed'
                visibleFrom='md'
              >
                {meta.label}
              </Text>
              <VisuallyHidden>Меню користувача</VisuallyHidden>
            </div>
          </Group>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>
          {user.displayName} · {meta.label}
        </Menu.Label>
        <Menu.Item
          leftSection={<IconSparkles size={16} />}
          rightSection={
            <Switch
              size='sm'
              checked={aiEnabled && !adminOff}
              readOnly
              tabIndex={-1}
              aria-hidden
              styles={{ root: { pointerEvents: "none" } }}
            />
          }
          closeMenuOnClick={false}
          disabled={adminOff}
          onClick={() => setAiEnabled(v => !v)}
          aria-checked={aiEnabled}
        >
          <div>Використовувати ШІ</div>
          {adminOff && (
            <Text
              size='xs'
              c='dimmed'
            >
              Вимкнено адміністратором
            </Text>
          )}
        </Menu.Item>
        <Menu.Divider />
        <Menu.Item
          leftSection={<IconSwitchHorizontal size={16} />}
          onClick={exit}
        >
          Змінити роль
        </Menu.Item>
        <Menu.Item
          color='danger'
          leftSection={<IconLogout size={16} />}
          onClick={exit}
        >
          Вийти
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}
