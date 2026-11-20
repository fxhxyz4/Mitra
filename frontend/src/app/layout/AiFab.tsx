import { Drawer } from "@mantine/core"
import { useDisclosure } from "@mantine/hooks"

import "@fontsource-variable/unbounded/index.css"

import { ChatPanel } from "@/features/ai"
import { useAiAccess, useSession } from "@/shared/api"
import classes from "./AiFab.module.scss"

function Sparkle() {
  return (
    <svg
      width='19'
      height='19'
      viewBox='0 0 24 24'
      aria-hidden
    >
      <path
        d='M12 2.5c.5 4.6 2.9 7 7.5 7.5-4.6.5-7 2.9-7.5 7.5-.5-4.6-2.9-7-7.5-7.5 4.6-.5 7-2.9 7.5-7.5z'
        fill='currentColor'
      />
      <path
        d='M19 15.5c.2 1.8 1.1 2.7 2.9 2.9-1.8.2-2.7 1.1-2.9 2.9-.2-1.8-1.1-2.7-2.9-2.9 1.8-.2 2.7-1.1 2.9-2.9z'
        fill='currentColor'
        opacity='0.75'
      />
    </svg>
  )
}

export function AiFab() {
  const { user } = useSession()
  const ai = useAiAccess()
  const [opened, { open, close }] = useDisclosure()
  if (!user || user.role === "ADMIN" || !ai.show) return null

  return (
    <>
      <button
        type='button'
        className={classes.fab}
        data-hidden={opened || undefined}
        onClick={open}
        aria-label='Mitra AI — запитати по даних'
        title='Запитати асистента по даних програми'
      >
        <span className={classes.icon}>
          <Sparkle />
        </span>
        <span className={classes.label}>
          Mitra <span className={classes.ai}>AI</span>
        </span>
      </button>
      <Drawer
        opened={opened}
        onClose={close}
        position='right'
        size='lg'
        title='Mitra AI'
        styles={{
          content: { display: "flex", flexDirection: "column" },
          body: { flex: 1, minHeight: 0, paddingBottom: "var(--mantine-spacing-md)" },
        }}
      >
        <ChatPanel user={user} />
      </Drawer>
    </>
  )
}
