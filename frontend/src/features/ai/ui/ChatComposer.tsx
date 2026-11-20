import { useState } from "react"
import { ActionIcon, Chip, Group, Stack, Textarea } from "@mantine/core"
import { IconSend } from "@tabler/icons-react"

export const MIN_QUESTION = 3

export function ChatComposer({
  examples,
  busy,
  onSend,
}: {
  examples: string[]
  busy: boolean
  onSend: (question: string) => void
}) {
  const [question, setQuestion] = useState("")
  const ready = !busy && question.trim().length >= MIN_QUESTION
  const send = (text: string) => {
    const q = text.trim()
    if (busy || q.length < MIN_QUESTION) return
    onSend(q)
    setQuestion("")
  }

  return (
    <Stack gap='xs'>
      {examples.length > 0 && (
        <Group gap={6}>
          {examples.map(q => (
            <Chip
              key={q}
              size='xs'
              variant='light'
              checked={false}
              disabled={busy}
              onClick={() => send(q)}
            >
              {q}
            </Chip>
          ))}
        </Group>
      )}
      <form
        onSubmit={e => {
          e.preventDefault()
          send(question)
        }}
      >
        <Group
          gap='xs'
          align='flex-end'
          wrap='nowrap'
        >
          <Textarea
            style={{ flex: 1 }}
            placeholder='Напр.: Які заходи розділу 2 прострочені?'
            autosize
            minRows={1}
            maxRows={5}
            maxLength={500}
            value={question}
            onChange={e => setQuestion(e.currentTarget.value)}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                send(question)
              }
            }}
            aria-label='Питання по даних'
          />
          <ActionIcon
            type='submit'
            size='lg'
            loading={busy}
            disabled={!ready}
            aria-label='Надіслати'
          >
            <IconSend size={16} />
          </ActionIcon>
        </Group>
      </form>
    </Stack>
  )
}
