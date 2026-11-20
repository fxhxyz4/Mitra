import { useState } from "react"
import {
  Alert,
  Button,
  Divider,
  Group,
  PasswordInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  UnstyledButton,
} from "@mantine/core"
import {
  IconChartLine,
  IconChecklist,
  IconKey,
  IconLayoutDashboard,
  IconListCheck,
  IconLogin2,
  IconSettings,
  IconUserSearch,
} from "@tabler/icons-react"
import type { Role, UserWithToken } from "@/shared/api"
import type { Icon } from "@tabler/icons-react"

import { roleMeta } from "@/shared/lib"
import { RoleBadge } from "@/shared/ui"
import { useDemoAccounts, useLogin } from "../api/queries"
import classes from "./LoginForm.module.scss"

const QUICK_ROLES: Role[] = [
  "COORDINATOR",
  "HEAD",
  "ANALYST",
  "ADMIN",
]

const roleIcons: Record<Role, Icon> = {
  EXECUTOR: IconChecklist,
  COORDINATOR: IconListCheck,
  HEAD: IconLayoutDashboard,
  ANALYST: IconChartLine,
  ADMIN: IconSettings,
}

function demoGroups(accounts: UserWithToken[]) {
  const quick = QUICK_ROLES.flatMap(role => accounts.find(a => a.role === role) ?? [])
  const rest = accounts.filter(a => !quick.includes(a))
  const groups = [
    { group: "Керівництво", items: rest.filter(a => a.role !== "EXECUTOR") },
    { group: "Виконавці підрозділів", items: rest.filter(a => a.role === "EXECUTOR") },
  ]
    .filter(g => g.items.length)
    .map(g => ({
      group: g.group,
      items: g.items.map(a => ({ value: a.token, label: a.displayName.replace(/^Виконавець — /, "") })),
    }))
  return { quick, groups, byToken: new Map(accounts.map(a => [a.token, a])) }
}

export function LoginForm({ showDemo = true }: { showDemo?: boolean }) {
  const [token, setToken] = useState("")
  const login = useLogin()
  const demo = useDemoAccounts(showDemo)
  const { quick, groups, byToken } = demoGroups(demo.data ?? [])
  const enter = (demoToken: string) => {
    setToken("")
    login.mutate(demoToken)
  }

  return (
    <Stack gap='lg'>
      <form
        onSubmit={e => {
          e.preventDefault()
          if (token.trim()) login.mutate(token)
        }}
      >
        <Stack gap='md'>
          <PasswordInput
            label='Персональний токен'
            description='Видається адміністратором системи'
            placeholder='Вставте токен'
            leftSection={<IconKey size={16} />}
            value={token}
            onChange={e => setToken(e.currentTarget.value)}
            autoComplete='current-password'
            size='md'
          />
          {login.error && (
            <Alert
              color='danger'
              variant='light'
            >
              {login.error.message}
            </Alert>
          )}
          <Button
            type='submit'
            size='md'
            leftSection={<IconLogin2 size={18} />}
            loading={login.isPending && Boolean(token)}
            disabled={!token.trim()}
          >
            Увійти
          </Button>
        </Stack>
      </form>

      {showDemo && quick.length > 0 && (
        <>
          <Divider label='Демо-доступ' />
          <SimpleGrid
            cols={{ base: 1, xs: 2 }}
            spacing='xs'
          >
            {quick.map(a => {
              const RoleIcon = roleIcons[a.role]
              return (
                <UnstyledButton
                  key={a.token}
                  className={classes.demo}
                  onClick={() => enter(a.token)}
                  disabled={login.isPending}
                >
                  <ThemeIcon
                    variant='light'
                    color={roleMeta[a.role].color}
                    radius='md'
                    size={34}
                  >
                    <RoleIcon
                      size={18}
                      stroke={1.7}
                    />
                  </ThemeIcon>
                  <Text
                    className={classes.demoName}
                    size='sm'
                    fw={600}
                    lh={1.25}
                  >
                    {a.displayName}
                  </Text>
                </UnstyledButton>
              )
            })}
          </SimpleGrid>
          <Select
            placeholder='Інша роль або виконавець підрозділу…'
            leftSection={<IconUserSearch size={16} />}
            data={groups}
            value={null}
            onChange={v => v && enter(v)}
            searchable
            nothingFoundMessage='Нічого не знайдено'
            maxDropdownHeight={320}
            disabled={login.isPending}
            renderOption={({ option }) => {
              const account = byToken.get(option.value)
              return (
                <Group
                  gap='sm'
                  wrap='nowrap'
                >
                  {account && (
                    <RoleBadge
                      role={account.role}
                      size='xs'
                      variant='dot'
                      style={{ flexShrink: 0 }}
                    />
                  )}
                  <Text size='sm'>{option.label}</Text>
                </Group>
              )
            }}
            aria-label='Обрати демо-роль'
          />
        </>
      )}
    </Stack>
  )
}
