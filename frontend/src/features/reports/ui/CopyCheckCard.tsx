import { Alert, Card, Code, Stack, Text, Title } from "@mantine/core"
import { IconCircleCheckFilled, IconCircleXFilled } from "@tabler/icons-react"

import { canHashFiles, formatDateTime, formatPeriod } from "@/shared/lib"
import { DocumentDrop } from "@/shared/ui"
import { useCopyCheck } from "../api"

const COPY_ACCEPT = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "text/csv": [".csv"],
  "application/json": [".json"],
  "text/html": [".html", ".htm"],
}

export function CopyCheckCard({ reportId }: { reportId: string }) {
  const check = useCopyCheck()
  const result = check.data

  return (
    <Card p='xl'>
      <Stack gap='md'>
        <div>
          <Title order={2}>Перевірка завантаженого файлу</Title>
          <Text
            size='sm'
            c='dimmed'
          >
            Порівнюємо файл побайтово з копіями, які видала система. Хеш SHA-256 рахується у вашому браузері, сам файл
            нікуди не надсилається.
          </Text>
        </div>

        {canHashFiles() ? (
          <DocumentDrop
            compact
            accept={COPY_ACCEPT}
            loading={check.isPending}
            onFile={file => check.mutate({ file, reportId })}
            title='Перетягніть копію звіту'
            description='PDF, DOCX, XLSX, CSV, JSON або HTML, завантажені із системи'
          />
        ) : (
          <Alert color='warning'>
            Браузер дозволяє рахувати хеш файлу лише на сторінці із захищеним зʼєднанням (HTTPS).
          </Alert>
        )}

        {check.error && <Alert color='danger'>{check.error.message}</Alert>}

        {result && (
          <Alert
            color={result.match ? "success" : "danger"}
            icon={result.match ? <IconCircleCheckFilled /> : <IconCircleXFilled />}
            title={result.match ? "Копія збігається з оригіналом" : "Файл відрізняється від оригіналу"}
          >
            <Stack gap={4}>
              <Text size='sm'>{result.reason}</Text>
              {result.match && (
                <Text size='sm'>
                  {result.programTitle} · {formatPeriod(result.period)} · {result.format?.toUpperCase()} · видано{" "}
                  {formatDateTime(result.issuedAt)}
                </Text>
              )}
              {!result.match && (
                <Text size='sm'>
                  Будь-яка зміна, навіть пересохранення в іншій програмі, робить файл неоригінальним. Завантажте копію
                  із системи ще раз або зверніться до уповноваженої особи.
                </Text>
              )}
              <Code
                fz={11}
                style={{ wordBreak: "break-all" }}
              >
                SHA-256: {result.sha256}
              </Code>
            </Stack>
          </Alert>
        )}
      </Stack>
    </Card>
  )
}
