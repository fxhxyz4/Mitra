import { useEffect, useRef } from "react"
import { Group, Loader, Paper, ScrollArea, Stack, Text } from "@mantine/core"
import type { AiChatMessage } from "@/shared/api"

import { AiNote, ReferencedText, SourceBadge } from "@/shared/ui"

function Question({ text }: { text: string }) {
  return (
    <Group justify='flex-end'>
      <Paper
        px='sm'
        py={6}
        radius='md'
        bg='var(--mantine-primary-color-light)'
        maw='85%'
      >
        <Text
          size='sm'
          style={{ whiteSpace: "pre-wrap" }}
        >
          {text}
        </Text>
      </Paper>
    </Group>
  )
}

function Answer({ message, disclaimer }: { message: AiChatMessage; disclaimer: string }) {
  return (
    <Paper
      withBorder
      p='sm'
      radius='md'
    >
      <Stack gap='xs'>
        <SourceBadge
          source={message.answerSource}
          style={{ alignSelf: "flex-start" }}
        />
        <ReferencedText
          text={message.content}
          references={message.references}
          showSources={message.answerSource !== "rule"}
        />
        {message.modelUsed && <AiNote>{disclaimer}</AiNote>}
      </Stack>
    </Paper>
  )
}

export function ChatThread({
  messages,
  pending,
  disclaimer,
}: {
  messages: AiChatMessage[]
  pending: string | null
  disclaimer: string
}) {
  const end = useRef<HTMLDivElement>(null)
  // Фігурні дужки обовʼязкові: у свіжому Chrome scrollIntoView повертає Promise,
  // і React сприйняв би його як функцію очищення ефекту («destroy is not a function»).
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" })
  }, [messages.length, pending])

  return (
    <ScrollArea
      style={{ flex: 1 }}
      offsetScrollbars
    >
      <Stack
        gap='sm'
        pb='xs'
      >
        {messages.map(m =>
          m.role === "user" ? (
            <Question
              key={m.id}
              text={m.content}
            />
          ) : (
            <Answer
              key={m.id}
              message={m}
              disclaimer={disclaimer}
            />
          )
        )}
        {pending && (
          <>
            <Question text={pending} />
            <Group gap='xs'>
              <Loader size='xs' />
              <Text
                size='sm'
                c='dimmed'
              >
                Готую відповідь…
              </Text>
            </Group>
          </>
        )}
        <div ref={end} />
      </Stack>
    </ScrollArea>
  )
}
