import { Alert, Button } from "@mantine/core"
import { IconAlertTriangle } from "@tabler/icons-react"

export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null
  return (
    <Alert
      color='danger'
      icon={<IconAlertTriangle size={18} />}
      title='Не вдалося завантажити дані'
      mb='lg'
    >
      {error instanceof Error ? error.message : String(error)}
      {onRetry && (
        <Button
          size='xs'
          variant='light'
          color='danger'
          ml='sm'
          onClick={onRetry}
        >
          Повторити
        </Button>
      )}
    </Alert>
  )
}
