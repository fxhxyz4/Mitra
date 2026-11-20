import { useState } from "react"
import { Alert, Button, Group, Stack, Text } from "@mantine/core"
import { IconSparkles } from "@tabler/icons-react"

import { useAiAccess } from "@/shared/api"
import { useRewrite } from "../api/queries"

type AiSuggestProps = { measureId: string; text: string; onApply: (text: string) => void }

export function AiSuggest({ measureId, text, onApply }: AiSuggestProps) {
  const ai = useAiAccess()
  const rewrite = useRewrite(measureId)
  const [suggestion, setSuggestion] = useState("")
  const [note, setNote] = useState("")

  if (!ai.model) return null

  const run = () => {
    setNote("")
    rewrite.mutate(text.trim(), {
      onSuccess: r => {
        setSuggestion(r.text?.trim() ?? "")
        setNote(r.text ? "" : r.note)
      },
    })
  }

  return (
    <Stack gap='xs'>
      <Button
        variant='light'
        color='violet'
        size='xs'
        w='fit-content'
        leftSection={<IconSparkles size={14} />}
        loading={rewrite.isPending}
        disabled={text.trim().length < 5}
        onClick={run}
      >
        Покращити опис з ШІ
      </Button>
      {rewrite.error && (
        <Text
          size='xs'
          c='danger'
        >
          {rewrite.error.message}
        </Text>
      )}
      {note && (
        <Text
          size='xs'
          c='dimmed'
        >
          {note}
        </Text>
      )}
      {suggestion && (
        <Alert
          variant='light'
          color='violet'
          title='Пропозиція локальної моделі — перевірте перед використанням'
        >
          <Text
            size='sm'
            style={{ whiteSpace: "pre-wrap" }}
          >
            {suggestion}
          </Text>
          <Group
            gap='xs'
            mt='sm'
          >
            <Button
              size='xs'
              color='violet'
              onClick={() => {
                onApply(suggestion)
                setSuggestion("")
              }}
            >
              Вставити
            </Button>
            <Button
              size='xs'
              variant='subtle'
              color='gray'
              onClick={() => setSuggestion("")}
            >
              Відхилити
            </Button>
          </Group>
        </Alert>
      )}
    </Stack>
  )
}
