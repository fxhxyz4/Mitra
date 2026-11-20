import { Card, Center, Group, Stack, Text, Title } from "@mantine/core"
import { IconCalendarStats, IconFileCertificate, IconFlag } from "@tabler/icons-react"
import { Navigate, useLocation } from "react-router"

import { homeFor, LoginForm } from "@/features/auth"
import { useSession } from "@/shared/api"
import { Logo, Seo } from "@/shared/ui"
import classes from "./LoginPage.module.scss"

const points = [
  { icon: IconCalendarStats, text: "Строки, нагадування і внесення результату за один крок" },
  { icon: IconFlag, text: "Risk Flags за явними правилами з поясненням" },
  { icon: IconFileCertificate, text: "Звіт за півріччя у структурі полів Порталу НАЗК" },
]

export function LoginPage() {
  const { user } = useSession()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from

  if (user)
    return (
      <Navigate
        to={from && from !== "/" ? from : homeFor(user.role)}
        replace
      />
    )

  return (
    <div className={classes.root}>
      <Seo title='Вхід' />
      <div className={classes.inner}>
        <Stack gap='lg'>
          <Logo />
          <Title className={classes.title}>Моніторинг виконання антикорупційної програми</Title>
          <Text
            className={classes.lead}
            c='dimmed'
            size='lg'
          >
            Заходи, строки, підтвердні матеріали, Risk Flags, модель ризику і підписаний звіт для Порталу НАЗК — в
            одному місці.
          </Text>
          <Stack
            className={classes.points}
            gap='sm'
          >
            {points.map(({ icon: PointIcon, text }) => (
              <Group
                key={text}
                gap='sm'
                wrap='nowrap'
              >
                <PointIcon
                  size={22}
                  stroke={1.6}
                  color='var(--mantine-primary-color-filled)'
                />
                <Text>{text}</Text>
              </Group>
            ))}
          </Stack>
        </Stack>
        <Center>
          <Card
            className={classes.card}
            p={{ base: "lg", xs: "xl" }}
          >
            <Title
              order={2}
              mb='lg'
            >
              Вхід
            </Title>
            <LoginForm />
          </Card>
        </Center>
      </div>
    </div>
  )
}
