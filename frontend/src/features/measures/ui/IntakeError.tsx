import { Alert, List, Text } from "@mantine/core"

import { HttpError } from "@/shared/api"

type IntakeErrorProps = {
  error: Error | null
  sample: "A" | "B"
}

const titleFor = (error: Error, sample: "A" | "B") => {
  if (!(error instanceof HttpError)) return "Не вдалося прочитати"
  if (error.status === 422) return `Документ не відповідає зразку ${sample}`
  if (error.status === 415) return "Непідтримуваний формат файлу"
  if (error.status === 413) return "Файл завеликий"
  return "Не вдалося прочитати"
}

export function IntakeError({ error, sample }: IntakeErrorProps) {
  if (!error) return null
  const hints = error instanceof HttpError ? error.hints : []
  return (
    <Alert
      color={error instanceof HttpError && error.status === 409 ? "warning" : "danger"}
      variant='light'
      title={titleFor(error, sample)}
    >
      <Text size='sm'>{error.message}</Text>
      {hints.length > 0 && (
        <List
          size='sm'
          mt={4}
        >
          {hints.map(h => (
            <List.Item key={h}>{h}</List.Item>
          ))}
        </List>
      )}
    </Alert>
  )
}
