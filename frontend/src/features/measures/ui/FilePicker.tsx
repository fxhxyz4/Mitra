import { ActionIcon, Autocomplete, Button, FileButton, Group, Paper, Stack, Text } from "@mantine/core"
import { IconFile, IconPaperclip, IconX } from "@tabler/icons-react"
import type { EvidenceFile } from "@/shared/api"

import { formatSize, isoDate } from "@/shared/lib"
import { DateField } from "@/shared/ui"
import { DOC_TYPES, toEvidenceFile } from "../lib/evidenceFiles"

const EVIDENCE_ACCEPT = ".pdf,.doc,.docx,.xls,.xlsx,.odt,.ods,.rtf,.txt,.csv,.jpg,.jpeg,.png,.p7s,.asice"

type FilePickerProps = {
  files: EvidenceFile[]
  onChange: (files: EvidenceFile[]) => void
  label?: string
  disabled?: boolean
}

export function FilePicker({ files, onChange, label = "Додати файли", disabled }: FilePickerProps) {
  const update = (i: number, change: Partial<EvidenceFile>) =>
    onChange(files.map((f, j) => (j === i ? { ...f, ...change } : f)))
  const today = new Date()
  return (
    <Stack gap='xs'>
      <FileButton
        multiple
        accept={EVIDENCE_ACCEPT}
        onChange={picked => onChange([...files, ...picked.map(toEvidenceFile)])}
        disabled={disabled}
      >
        {props => (
          <Button
            {...props}
            variant='default'
            leftSection={<IconPaperclip size={16} />}
            w='fit-content'
            disabled={disabled}
          >
            {label}
          </Button>
        )}
      </FileButton>
      {files.map((f, i) => (
        <Paper
          key={`${f.file.name}-${i}`}
          withBorder
          p='xs'
          radius='md'
        >
          <Stack gap={6}>
            <Group
              gap='xs'
              wrap='nowrap'
            >
              <IconFile
                size={16}
                stroke={1.6}
              />
              <Text
                size='sm'
                truncate
                style={{ flex: 1 }}
              >
                {f.file.name}
              </Text>
              <Text
                size='xs'
                c='dimmed'
              >
                {formatSize(f.file.size)}
              </Text>
              <ActionIcon
                variant='subtle'
                color='gray'
                size='sm'
                aria-label='Прибрати файл'
                onClick={() => onChange(files.filter((_, j) => j !== i))}
              >
                <IconX size={14} />
              </ActionIcon>
            </Group>
            <Group
              grow
              align='flex-start'
              gap='xs'
            >
              <Autocomplete
                size='xs'
                label='Тип документа'
                placeholder='наказ, протокол, акт…'
                data={DOC_TYPES}
                value={f.docType}
                onChange={docType => update(i, { docType })}
                error={!f.docType.trim() ? "Вкажіть тип" : undefined}
                required
                disabled={disabled}
              />
              <DateField
                size='xs'
                label='Дата документа'
                placeholder='дд.мм.рррр'
                value={f.documentDate}
                maxDate={isoDate(today)}
                onChange={documentDate => update(i, { documentDate })}
                error={!f.documentDate ? "Вкажіть дату" : undefined}
                required
                disabled={disabled}
              />
            </Group>
          </Stack>
        </Paper>
      ))}
    </Stack>
  )
}
