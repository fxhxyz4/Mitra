import { Group, Loader, Stack, Text, ThemeIcon } from "@mantine/core"
import { Dropzone } from "@mantine/dropzone"
import { IconFileUpload, IconFileX } from "@tabler/icons-react"
import type { ReactNode } from "react"

const DOCUMENT_ACCEPT = {
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/pdf": [".pdf"],
  "text/plain": [".txt"],
}

const MAX_MB = 10

type DocumentDropProps = {
  onFile: (file: File) => void
  accept?: Record<string, string[]>
  title: ReactNode
  description?: ReactNode
  loading?: boolean
  disabled?: boolean
  compact?: boolean
}

export function DocumentDrop({
  onFile,
  accept = DOCUMENT_ACCEPT,
  title,
  description,
  loading,
  disabled,
  compact,
}: DocumentDropProps) {
  return (
    <Dropzone
      onDrop={files => files[0] && onFile(files[0])}
      accept={accept}
      maxSize={MAX_MB * 1024 * 1024}
      maxFiles={1}
      multiple={false}
      loading={loading}
      disabled={disabled}
      radius='md'
      p={compact ? "sm" : "lg"}
      aria-label={typeof title === "string" ? title : "Перетягніть документ"}
    >
      <Group
        justify='center'
        gap='md'
        wrap='nowrap'
        mih={compact ? 48 : 96}
        style={{ pointerEvents: "none" }}
      >
        <Dropzone.Accept>
          <ThemeIcon
            size={compact ? 36 : 48}
            radius='xl'
            variant='light'
          >
            <IconFileUpload size={compact ? 20 : 26} />
          </ThemeIcon>
        </Dropzone.Accept>
        <Dropzone.Reject>
          <ThemeIcon
            size={compact ? 36 : 48}
            radius='xl'
            variant='light'
            color='danger'
          >
            <IconFileX size={compact ? 20 : 26} />
          </ThemeIcon>
        </Dropzone.Reject>
        <Dropzone.Idle>
          <ThemeIcon
            size={compact ? 36 : 48}
            radius='xl'
            variant='light'
            color='violet'
          >
            {loading ? <Loader size='sm' /> : <IconFileUpload size={compact ? 20 : 26} />}
          </ThemeIcon>
        </Dropzone.Idle>
        <Stack gap={2}>
          <Text
            fw={600}
            size={compact ? "sm" : "md"}
          >
            {title}
          </Text>
          <Text
            size='xs'
            c='dimmed'
          >
            {description ?? `DOCX, XLSX, PDF або TXT до ${MAX_MB} МБ — перетягніть сюди або натисніть, щоб обрати`}
          </Text>
        </Stack>
      </Group>
    </Dropzone>
  )
}
