import { useState } from "react"
import { ActionIcon, Badge, Button, Card, Group, Stack, Text, Tooltip } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconDownload, IconFileText, IconLock, IconUpload } from "@tabler/icons-react"
import type { EvidenceFile, MeasureDetail } from "@/shared/api"

import { download } from "@/shared/api"
import { formatDate, formatDateTime, formatPeriod, formatSize } from "@/shared/lib"
import { EmptyState } from "@/shared/ui"
import { useUploadEvidence } from "../api/queries"
import { isComplete } from "../lib/evidenceFiles"
import { FilePicker } from "./FilePicker"

export function EvidenceList({ measure }: { measure: MeasureDetail }) {
  const [files, setFiles] = useState<EvidenceFile[]>([])
  const upload = useUploadEvidence(measure.id)
  const canUpload = measure.allowedActions.includes("uploadEvidence")

  return (
    <Card>
      <Group
        justify='space-between'
        mb='md'
      >
        <div>
          <Text fw={600}>Підтвердні матеріали</Text>
          <Group gap={4}>
            <IconLock
              size={14}
              stroke={1.6}
            />
            <Text
              size='xs'
              c='dimmed'
            >
              Незмінні: sha256, версії, без видалення
            </Text>
          </Group>
        </div>
        <Badge
          variant='light'
          color='gray'
        >
          {measure.evidence.length}
        </Badge>
      </Group>

      <Stack gap='xs'>
        {measure.evidence.map(e => (
          <Group
            key={e.id}
            wrap='nowrap'
            gap='sm'
            align='flex-start'
          >
            <IconFileText
              size={20}
              stroke={1.5}
              style={{ flexShrink: 0, marginTop: 2 }}
            />
            <Stack
              gap={0}
              style={{ flex: 1, minWidth: 0 }}
            >
              <Text
                size='sm'
                fw={500}
                truncate
              >
                {e.fileName}
                {e.version > 1 && (
                  <Text
                    span
                    c='dimmed'
                    size='xs'
                  >
                    {" "}
                    v{e.version}
                  </Text>
                )}
              </Text>
              {(e.docType || e.documentDate) && (
                <Text size='xs'>
                  {e.docType || "документ"}
                  {e.documentDate ? ` від ${formatDate(e.documentDate)}` : ""}
                </Text>
              )}
              <Text
                size='xs'
                c='dimmed'
              >
                {formatSize(e.size)} · завантажено {formatDateTime(e.uploadedAt)} · {formatPeriod(e.period)}
              </Text>
              <Tooltip
                label={e.sha256}
                maw={420}
                multiline
              >
                <Text
                  size='xs'
                  ff='monospace'
                  c='dimmed'
                  w='fit-content'
                >
                  sha256 {e.sha256.slice(0, 12)}…
                </Text>
              </Tooltip>
            </Stack>
            <ActionIcon
              variant='subtle'
              aria-label={`Завантажити ${e.fileName}`}
              onClick={() =>
                download(`/measures/${measure.id}/evidence/${e.id}/download`, e.fileName).catch((err: Error) =>
                  notifications.show({ color: "danger", message: err.message })
                )
              }
            >
              <IconDownload size={18} />
            </ActionIcon>
          </Group>
        ))}
        {!measure.evidence.length && (
          <EmptyState
            title='Документів ще немає'
            icon={IconFileText}
          />
        )}
      </Stack>

      {canUpload && measure.status === "DONE" && (
        <Stack
          gap='xs'
          mt='md'
        >
          <Text
            size='xs'
            c='dimmed'
          >
            Захід виконано — можна лише додавати документи.
          </Text>
          <FilePicker
            files={files}
            onChange={setFiles}
          />
          {files.length > 0 && (
            <Button
              leftSection={<IconUpload size={16} />}
              loading={upload.isPending}
              disabled={!isComplete(files)}
              w='fit-content'
              onClick={() =>
                upload.mutate(
                  { files, period: measure.period ?? undefined },
                  {
                    onSuccess: () => {
                      setFiles([])
                      notifications.show({ color: "success", message: "Документи додано" })
                    },
                    onError: e => notifications.show({ color: "danger", message: e.message }),
                  }
                )
              }
            >
              Завантажити
            </Button>
          )}
        </Stack>
      )}
    </Card>
  )
}
