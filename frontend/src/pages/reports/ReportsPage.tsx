import { useState } from "react"
import {
  Alert,
  Button,
  Grid,
  Group,
  Modal,
  NavLink,
  Progress,
  ScrollArea,
  Select,
  Stack,
  Text,
  Textarea,
} from "@mantine/core"
import { notifications } from "@mantine/notifications"
import {
  IconBan,
  IconDownload,
  IconFilePlus,
  IconFileTypeDocx,
  IconFileTypePdf,
  IconFileTypeXls,
  IconPrinter,
} from "@tabler/icons-react"
import { useSearchParams } from "react-router"
import type { Report, ReportType } from "@/shared/api"

import { canManage } from "@/features/auth"
import { useCoordinatorDashboard } from "@/features/dashboards"
import {
  IntegrityCard,
  NazkReportView,
  useGenerateReport,
  useNazkReport,
  useReports,
  useRevokeReport,
} from "@/features/reports"
import { download, openInTab, usePrograms, useSession } from "@/shared/api"
import { currentPeriod, formatDateTime, formatPeriod, reportMeta } from "@/shared/lib"
import { EmptyState, MeasureList, PageHeader, QueryError, Section, Seo } from "@/shared/ui"

const previousPeriod = (period: string) => {
  const [year, half] = period.split("-")
  return half === "H2" ? `${year}-H1` : `${Number(year) - 1}-H2`
}

const periodOptions = (latest: string) => {
  const out = [latest]
  while (out.length < 4) out.push(previousPeriod(out[out.length - 1]!))
  return out.map(p => ({ value: p, label: formatPeriod(p) }))
}

export function ReportsPage() {
  const { user } = useSession()
  const canGenerate = canManage(user?.role)
  const programs = usePrograms()
  const program = programs.data?.find(p => p.status === "APPROVED") ?? programs.data?.[0]
  const reports = useReports()
  const dashboard = useCoordinatorDashboard()
  const generate = useGenerateReport()
  const serverPeriod = dashboard.data?.reportReadiness.period ?? currentPeriod()
  const [chosenPeriod, setPeriod] = useState<string | null>(null)
  const period = chosenPeriod ?? serverPeriod
  const [type, setType] = useState<ReportType>("NAZK")
  const [params, setParams] = useSearchParams()
  const selected = params.get("report")
  const setSelected = (id: string) => setParams({ report: id }, { replace: true })
  const list = [...(reports.data ?? [])].sort((a, b) => b.generatedAt.localeCompare(a.generatedAt))
  const current = list.find(r => r.id === selected) ?? list[0]
  const superseded = (r: Report) =>
    list.some(
      n =>
        n.programId === r.programId &&
        n.period === r.period &&
        n.type === r.type &&
        !n.revokedAt &&
        n.generatedAt > r.generatedAt
    )
  const revoke = useRevokeReport()
  const [revoking, setRevoking] = useState(false)
  const [reason, setReason] = useState("")
  const nazk = useNazkReport(current?.id ?? null)
  const readiness = dashboard.data?.reportReadiness
  const restricted = program?.hasRestrictedInfo

  const fail = (e: Error) => notifications.show({ color: "danger", message: e.message })

  return (
    <>
      <Seo title='Звіт НАЗК' />
      <PageHeader
        title='Звіт за півріччя'
        description='Дані формуються із системи у структурі полів Порталу доброчесності НАЗК'
      />
      <QueryError error={reports.error} />

      <Grid gap='lg'>
        <Grid.Col span={{ base: 12, lg: 4, xl: 3 }}>
          <Stack gap='lg'>
            {canGenerate && (
              <Section title='Сформувати звіт'>
                <Stack gap='sm'>
                  <Select
                    label='Півріччя'
                    data={periodOptions(serverPeriod)}
                    value={period}
                    onChange={v => v && setPeriod(v)}
                    allowDeselect={false}
                  />
                  <Select
                    label='Тип'
                    data={(
                      [
                        "NAZK",
                        "PRINT",
                        "INTERNAL",
                      ] as ReportType[]
                    ).map(t => ({ value: t, label: reportMeta[t] }))}
                    value={type}
                    onChange={v => v && setType(v as ReportType)}
                    allowDeselect={false}
                  />
                  {restricted && (
                    <Alert
                      color='warning'
                      variant='light'
                    >
                      Програма містить інформацію з обмеженим доступом — подається у паперовій формі.
                    </Alert>
                  )}
                  <Button
                    leftSection={<IconFilePlus size={16} />}
                    disabled={!program}
                    loading={generate.isPending}
                    onClick={() =>
                      program &&
                      generate.mutate(
                        { programId: program.id, period, type },
                        {
                          onSuccess: r => {
                            setSelected(r.id)
                            notifications.show({ color: "success", message: "Звіт сформовано" })
                          },
                          onError: fail,
                        }
                      )
                    }
                  >
                    Сформувати
                  </Button>
                </Stack>
              </Section>
            )}

            {readiness && (
              <Section
                title='Готовність'
                subtitle={formatPeriod(readiness.period)}
              >
                <Text
                  fz={30}
                  fw={700}
                >
                  {readiness.percent}%
                </Text>
                <Progress
                  value={readiness.percent}
                  aria-label='Готовність звіту'
                  color={readiness.percent === 100 ? "success" : "brand"}
                  my='xs'
                />
                <Text
                  size='sm'
                  c='dimmed'
                >
                  {readiness.ready} з {readiness.total} заходів мають остаточний стан
                </Text>
              </Section>
            )}

            <Section
              title='Сформовані звіти'
              loading={reports.isPending}
              padding='md'
            >
              <Stack gap={2}>
                {list.map(r => (
                  <NavLink
                    key={r.id}
                    active={r.id === current?.id}
                    label={`${formatPeriod(r.period)} · ${reportMeta[r.type]}`}
                    description={
                      formatDateTime(r.generatedAt) +
                      (r.revokedAt ? " · відкликано" : superseded(r) ? " · є новіша редакція" : "")
                    }
                    onClick={() => setSelected(r.id)}
                    styles={{ root: { borderRadius: "var(--mantine-radius-md)" } }}
                  />
                ))}
                {!list.length && (
                  <Text
                    size='sm'
                    c='dimmed'
                  >
                    Ще не сформовано
                  </Text>
                )}
              </Stack>
            </Section>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 8, xl: 9 }}>
          <Stack gap='lg'>
            {current && (
              <Section
                title='Перевірка справжності'
                subtitle='SHA-256 знімка звіту і підпис HMAC; QR веде на публічну сторінку перевірки'
                actions={
                  canGenerate &&
                  !current.revokedAt && (
                    <Button
                      size='xs'
                      variant='default'
                      color='danger'
                      leftSection={<IconBan size={14} />}
                      onClick={() => setRevoking(true)}
                    >
                      Відкликати
                    </Button>
                  )
                }
              >
                <Stack gap='md'>
                  {current.revokedAt ? (
                    <Alert
                      color='danger'
                      variant='light'
                      title={`Звіт відкликано ${formatDateTime(current.revokedAt)}`}
                    >
                      Причина: {current.revokeReason}
                      <br />
                      Перевірка за QR показує, що звіт відкликано.
                    </Alert>
                  ) : (
                    superseded(current) && (
                      <Alert
                        color='warning'
                        variant='light'
                      >
                        Є новіша редакція за цей період. Перевірка за QR цього звіту попереджає про неї.
                      </Alert>
                    )
                  )}
                  <IntegrityCard
                    state={current.revokedAt ? "revoked" : superseded(current) ? "superseded" : "current"}
                    reportId={current.id}
                    title={program?.title ?? "Звіт про виконання антикорупційної програми"}
                    caption={`${reportMeta[current.type]} · ${formatPeriod(current.period)}`}
                  />
                </Stack>
              </Section>
            )}
            <Section
              title='Попередній перегляд'
              subtitle={current ? `${formatPeriod(current.period)} · ${reportMeta[current.type]}` : undefined}
              actions={
                current && (
                  <Group gap='xs'>
                    <Button
                      size='xs'
                      variant='default'
                      leftSection={<IconDownload size={14} />}
                      onClick={() =>
                        download(`/reports/${current.id}/nazk?format=csv`, `nazk-${current.period}.csv`).catch(fail)
                      }
                    >
                      CSV
                    </Button>
                    <Button
                      size='xs'
                      variant='default'
                      leftSection={<IconDownload size={14} />}
                      onClick={() =>
                        download(`/reports/${current.id}/nazk?format=json`, `nazk-${current.period}.json`).catch(fail)
                      }
                    >
                      JSON
                    </Button>
                    <Button
                      size='xs'
                      variant='default'
                      leftSection={<IconFileTypeDocx size={14} />}
                      onClick={() =>
                        download(
                          `/reports/${current.id}/export?format=docx`,
                          `${current.type === "INTERNAL" ? "memo" : "nazk"}-${current.period}.docx`
                        ).catch(fail)
                      }
                    >
                      DOCX
                    </Button>
                    <Button
                      size='xs'
                      variant='default'
                      leftSection={<IconFileTypePdf size={14} />}
                      onClick={() =>
                        download(
                          `/reports/${current.id}/export?format=pdf`,
                          `${current.type === "INTERNAL" ? "memo" : "nazk"}-${current.period}.pdf`
                        ).catch(fail)
                      }
                    >
                      PDF
                    </Button>
                    <Button
                      size='xs'
                      variant='default'
                      leftSection={<IconFileTypeXls size={14} />}
                      onClick={() =>
                        download(`/reports/${current.id}/export?format=xlsx`, `nazk-${current.period}.xlsx`).catch(fail)
                      }
                    >
                      XLSX
                    </Button>
                    <Button
                      size='xs'
                      variant='default'
                      leftSection={<IconPrinter size={14} />}
                      onClick={() => openInTab(`/reports/${current.id}/print`, { print: true }).catch(fail)}
                    >
                      Друк
                    </Button>
                  </Group>
                )
              }
            >
              {current ? (
                <ScrollArea.Autosize
                  mah='70vh'
                  type='auto'
                >
                  <NazkReportView
                    report={nazk.data}
                    loading={nazk.isPending}
                  />
                </ScrollArea.Autosize>
              ) : (
                <EmptyState
                  title='Звіт ще не сформовано'
                  text='Оберіть півріччя і натисніть «Сформувати»'
                />
              )}
            </Section>
            {readiness && readiness.missing.length > 0 && (
              <Section
                title='Не готові до звіту'
                subtitle='Строк настав, але немає остаточного стану'
                padding={0}
              >
                <MeasureList items={readiness.missing} />
              </Section>
            )}
          </Stack>
        </Grid.Col>
      </Grid>

      <Modal
        opened={revoking && Boolean(current)}
        onClose={() => setRevoking(false)}
        title='Відкликати звіт'
      >
        <Stack gap='sm'>
          <Text size='sm'>
            Звіт лишиться в системі з підписом, але перевірка за QR показуватиме «Звіт відкликано» з цією причиною.
            Скасувати відкликання не можна.
          </Text>
          <Textarea
            label='Причина'
            placeholder='Наприклад: помилка в розділі 2, сформовано нову редакцію'
            required
            autosize
            minRows={2}
            value={reason}
            onChange={e => setReason(e.currentTarget.value)}
          />
          <Group justify='flex-end'>
            <Button
              color='danger'
              disabled={reason.trim().length < 5}
              loading={revoke.isPending}
              onClick={() =>
                current &&
                revoke.mutate(
                  { id: current.id, reason: reason.trim() },
                  {
                    onSuccess: () => {
                      setRevoking(false)
                      setReason("")
                      notifications.show({ color: "success", message: "Звіт відкликано" })
                    },
                    onError: fail,
                  }
                )
              }
            >
              Відкликати
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
