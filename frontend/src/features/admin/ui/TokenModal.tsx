import { Alert, Button, CopyButton, Group, Modal, Stack, Text, TextInput } from "@mantine/core"
import { IconCheck, IconCopy } from "@tabler/icons-react"
import type { UserWithToken } from "@/shared/api"

export function TokenModal({ user, onClose }: { user: UserWithToken | null; onClose: () => void }) {
  return (
    <Modal
      opened={Boolean(user)}
      onClose={onClose}
      title='Персональний токен'
    >
      {user && (
        <Stack>
          <Text size='sm'>
            Токен для <b>{user.displayName}</b>. Він показується лише один раз — у базі зберігається тільки sha256.
          </Text>
          {user.tokenExpiresAt && (
            <Text size='sm'>
              Діє до <b>{new Date(user.tokenExpiresAt).toLocaleDateString("uk-UA")}</b>, далі потрібен новий токен.
            </Text>
          )}
          <TextInput
            value={user.token}
            readOnly
            ff='monospace'
            rightSectionWidth={44}
            rightSection={
              <CopyButton value={user.token}>
                {({ copied, copy }) => (
                  <Button
                    variant='subtle'
                    size='compact-sm'
                    onClick={copy}
                    aria-label='Скопіювати'
                  >
                    {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                  </Button>
                )}
              </CopyButton>
            }
          />
          <Alert
            variant='light'
            color='warning'
          >
            Передайте токен користувачу захищеним каналом.
          </Alert>
          <Group justify='flex-end'>
            <Button onClick={onClose}>Готово</Button>
          </Group>
        </Stack>
      )}
    </Modal>
  )
}
