import { AppShell } from "@mantine/core"
import { useDisclosure } from "@mantine/hooks"
import { Outlet } from "react-router"

import { useMe } from "@/features/auth"
import { AiFab } from "./AiFab"
import classes from "./AppLayout.module.scss"
import { Header } from "./Header"
import { Navbar } from "./Navbar"
import { NavigationProgress } from "./NavigationProgress"
import { ScrollToTop } from "./ScrollToTop"

export function AppLayout() {
  const [opened, { toggle, close }] = useDisclosure()
  useMe()

  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{ width: { sm: 240, lg: 270 }, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding={{ base: "md", sm: "lg", xl: "xl" }}
    >
      <a
        href='#main'
        className={classes.skip}
      >
        Перейти до змісту
      </a>
      <NavigationProgress />

      <AppShell.Header className={classes.header}>
        <Header
          opened={opened}
          onToggle={toggle}
        />
      </AppShell.Header>

      <AppShell.Navbar
        p='md'
        className={classes.navbar}
      >
        <Navbar onNavigate={close} />
      </AppShell.Navbar>

      <AppShell.Main id='main'>
        <div className={classes.content}>
          <Outlet />
          <ScrollToTop />
        </div>
      </AppShell.Main>
      <AiFab />
    </AppShell>
  )
}
