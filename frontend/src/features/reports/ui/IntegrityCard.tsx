import { Anchor, Code, CopyButton, Group, Skeleton, Stack, Text, Tooltip } from "@mantine/core"
import { IconAlertCircle, IconBan, IconCheck, IconCopy, IconShieldCheck } from "@tabler/icons-react"

import { formatDate } from "@/shared/lib"
import { useReportIntegrity } from "../api"
import { DocumentThumb } from "./DocumentThumb"

/** current — актуальна редакція; superseded — є новіша за той самий період; revoked — відкликано. */
export type EditionState = "current" | "superseded" | "revoked"

const EDITION = {
  current: { Icon: IconShieldCheck, color: "success", note: "" },
  superseded: { Icon: IconAlertCircle, color: "warning", note: " · застаріла редакція" },
  revoked: { Icon: IconBan, color: "danger", note: " · відкликано" },
} as const

export function IntegrityCard({
  reportId,
  title,
  caption,
  state = "current",
}: {
  reportId: string
  title: string
  caption: string
  state?: EditionState
}) {
  const edition = EDITION[state]
  const { data, isPending, error } = useReportIntegrity(reportId)
  if (error)
    return (
      <Text
        size='sm'
        c='danger'
      >
        {error.message}
      </Text>
    )
  if (isPending || !data) return <Skeleton h={212} />
  const qr = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(data.qrSvg)}`
  const verify = new URL(data.verifyUrl)
  const verifyHere = `${window.location.origin}${verify.pathname}${verify.search}`

  return (
    <Group
      align='flex-start'
      gap='lg'
      wrap='wrap'
    >
      <DocumentThumb
        qr={qr}
        title={title}
        caption={caption}
      />
      <Stack
        gap={6}
        style={{ flex: 1, minWidth: "min(200px, 100%)" }}
      >
        <Group gap={6}>
          <edition.Icon
            size={18}
            color={`var(--mantine-color-${edition.color}-filled)`}
          />
          <Text
            fw={600}
            c={state === "current" ? undefined : `${edition.color}.7`}
          >
            Підписано {formatDate(data.signedOn)}
            {edition.note}
          </Text>
        </Group>
        <Text
          size='sm'
          c='dimmed'
        >
          QR-код є у друкованій формі та DOCX. Будь-хто може відсканувати його і переконатися, що звіт справжній і не
          змінювався.
        </Text>
        <Anchor
          href={verifyHere}
          target='_blank'
          size='sm'
          fw={600}
          className='app-strong-link'
          style={{ wordBreak: "break-all" }}
        >
          Відкрити сторінку перевірки
        </Anchor>
        <Group
          gap={4}
          wrap='nowrap'
        >
          <Code
            fz={11}
            style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
          >
            SHA-256 {data.sha256}
          </Code>
          <CopyButton value={data.verifyUrl}>
            {({ copied, copy }) => (
              <Tooltip label={copied ? "Скопійовано" : "Скопіювати посилання"}>
                <Anchor
                  component='button'
                  onClick={copy}
                  aria-label='Скопіювати посилання перевірки'
                  lh={0}
                >
                  {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                </Anchor>
              </Tooltip>
            )}
          </CopyButton>
        </Group>
      </Stack>
    </Group>
  )
}
