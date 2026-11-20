import { useEffect, useState } from "react"
import { ActionIcon, Alert, Button, Group, Menu, Modal, Select, Stack, Text, TextInput, Tooltip } from "@mantine/core"
import { useLocalStorage } from "@mantine/hooks"
import { IconCheck, IconDots, IconPencil, IconPlus, IconTrash, IconX } from "@tabler/icons-react"
import type { User } from "@/shared/api"

import { HttpError } from "@/shared/api"
import { useChat, useChats, useDeleteChat, useRenameChat, useSendMessage } from "../api/queries"
import { ChatComposer } from "./ChatComposer"
import { chatExamples } from "./chatExamples"
import { ChatThread } from "./ChatThread"

const TITLE_MAX = 120

function TitleEditor({
  initial,
  onSave,
  onCancel,
}: {
  initial: string
  onSave: (title: string) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState(initial)
  const valid = title.trim().length > 0
  return (
    <form
      style={{ flex: 1 }}
      onSubmit={e => {
        e.preventDefault()
        if (valid) onSave(title.trim())
      }}
    >
      <Group
        gap={4}
        wrap='nowrap'
      >
        <TextInput
          style={{ flex: 1 }}
          size='xs'
          value={title}
          maxLength={TITLE_MAX}
          onChange={e => setTitle(e.currentTarget.value)}
          onKeyDown={e => e.key === "Escape" && onCancel()}
          aria-label='Назва розмови'
          autoFocus
        />
        <ActionIcon
          type='submit'
          variant='subtle'
          disabled={!valid}
          aria-label='Зберегти назву'
        >
          <IconCheck size={16} />
        </ActionIcon>
        <ActionIcon
          variant='subtle'
          color='gray'
          onClick={onCancel}
          aria-label='Скасувати'
        >
          <IconX size={16} />
        </ActionIcon>
      </Group>
    </form>
  )
}

function DeleteChatModal({
  title,
  opened,
  busy,
  error,
  onConfirm,
  onClose,
}: {
  title: string
  opened: boolean
  busy: boolean
  error: string | null
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title='Видалити розмову?'
      centered
    >
      <Stack gap='md'>
        <Text size='sm'>
          Розмова «{title}» зникне зі списку, відновити її в інтерфейсі не вийде. Питання і відповіді лишаються в
          журналі дій.
        </Text>
        {error && (
          <Alert
            color='danger'
            variant='light'
          >
            {error}
          </Alert>
        )}
        <Group justify='flex-end'>
          <Button
            variant='default'
            onClick={onClose}
            disabled={busy}
          >
            Скасувати
          </Button>
          <Button
            color='danger'
            onClick={onConfirm}
            loading={busy}
          >
            Видалити
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export function ChatPanel({ user }: { user: User }) {
  const [lastId, setLastId] = useLocalStorage<string>({
    key: `mitra.ai-chat.${user.id}`,
    defaultValue: "",
    getInitialValueInEffect: false,
  })
  const [picked, setPicked] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const chats = useChats()
  const current = picked ?? (lastId || chats.data?.[0]?.id || "")
  const chat = useChat(current || null)
  const send = useSendMessage()
  const rename = useRenameChat()
  const remove = useDeleteChat()

  const gone = chat.error instanceof HttpError && chat.error.status === 404
  const activeId = gone ? "" : current
  useEffect(() => {
    if (gone) setLastId("")
  }, [gone, setLastId])

  const openChat = (id: string) => {
    setPicked(id)
    setLastId(id)
  }

  const messages = activeId ? (chat.data?.messages ?? []) : []
  const pending = send.isPending ? send.variables.question : null
  const error = send.error ?? rename.error ?? (gone ? null : chat.error)

  const startNew = () => {
    send.reset()
    setEditing(false)
    setPicked("")
  }

  return (
    <Stack
      gap='sm'
      h='100%'
    >
      <Group
        gap='xs'
        wrap='nowrap'
      >
        {editing && chat.data ? (
          <TitleEditor
            initial={chat.data.title}
            onCancel={() => setEditing(false)}
            onSave={title => rename.mutate({ id: chat.data.id, title }, { onSuccess: () => setEditing(false) })}
          />
        ) : (
          <Select
            style={{ flex: 1 }}
            size='xs'
            placeholder={chats.data?.length ? "Нова розмова" : "Розмов ще немає"}
            data={(chats.data ?? []).map(c => ({ value: c.id, label: c.title }))}
            value={activeId || null}
            onChange={id => {
              send.reset()
              openChat(id ?? "")
            }}
            disabled={send.isPending}
            searchable
            nothingFoundMessage='Не знайдено'
            aria-label='Розмова'
          />
        )}
        <Tooltip label='Нова розмова'>
          <ActionIcon
            variant='default'
            onClick={startNew}
            disabled={send.isPending || !activeId}
            aria-label='Нова розмова'
          >
            <IconPlus size={16} />
          </ActionIcon>
        </Tooltip>
        {activeId && chat.data && !editing && (
          <Menu position='bottom-end'>
            <Menu.Target>
              <ActionIcon
                variant='default'
                disabled={send.isPending}
                aria-label='Дії з розмовою'
              >
                <IconDots size={16} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconPencil size={14} />}
                onClick={() => setEditing(true)}
              >
                Перейменувати
              </Menu.Item>
              <Menu.Item
                color='danger'
                leftSection={<IconTrash size={14} />}
                onClick={() => {
                  remove.reset()
                  setConfirming(true)
                }}
              >
                Видалити
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        )}
      </Group>

      {messages.length === 0 && !pending ? (
        <Text
          size='sm'
          c='dimmed'
          style={{ flex: 1 }}
        >
          Запитайте про дані програми — відповідь у межах прав вашої ролі, з посиланнями на заходи, ризики і прапорці.
          Можна уточнювати: попередні питання розмови враховуються.
        </Text>
      ) : (
        <ChatThread
          messages={messages}
          pending={pending}
          disclaimer={chat.data?.disclaimer ?? ""}
        />
      )}

      {error && (
        <Alert
          color='danger'
          variant='light'
        >
          {error.message}
        </Alert>
      )}

      {chat.data && (
        <DeleteChatModal
          title={chat.data.title}
          opened={confirming}
          busy={remove.isPending}
          error={remove.error?.message ?? null}
          onClose={() => setConfirming(false)}
          onConfirm={() =>
            remove.mutate(chat.data.id, {
              onSuccess: () => {
                setConfirming(false)
                startNew()
                setLastId("")
              },
            })
          }
        />
      )}

      <ChatComposer
        examples={messages.length === 0 && !pending ? chatExamples[user.role] : []}
        busy={send.isPending}
        onSend={question =>
          send.mutate({ chatId: activeId || null, question }, { onSuccess: saved => openChat(saved.id) })
        }
      />
    </Stack>
  )
}
