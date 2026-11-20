import { Alert, Anchor, Badge, Button, Card, Code, Group, Loader, Stack, Text, Title } from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconAlertCircle, IconAlertTriangle, IconBan, IconDownload, IconExternalLink } from "@tabler/icons-react"
import { Link, useSearchParams } from "react-router"
import type { ReactNode } from "react"

import { CopyCheckCard, useReportVerification } from "@/features/reports"
import { download, useSession } from "@/shared/api"
import { paths } from "@/shared/config"
import { formatDateTime, formatPeriod, reportMeta } from "@/shared/lib"
import { canOpen, Logo, Seo } from "@/shared/ui"
import classes from "./VerifyPage.module.scss"

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className={classes.row}>
      <Text
        size='sm'
        c='dimmed'
      >
        {label}
      </Text>
      <Text
        component='div'
        size='sm'
        fw={500}
      >
        {value}
      </Text>
    </div>
  )
}

export function VerifyPage() {
  const [params] = useSearchParams()
  const id = params.get("id") ?? ""
  const h = params.get("h") ?? ""
  const sig = params.get("sig") ?? ""
  const complete = Boolean(id && h && sig)
  const { data, isPending, error } = useReportVerification(id, h, sig)
  const { user } = useSession()
  const signedIn = Boolean(user)
  // the original lives on the reports page (coordinator, analyst): other roles would be sent home / get 403
  const opensReports = canOpen(paths.reports, user?.role)
  const valid = complete && data?.valid === true
  const revoked = complete && Boolean(data?.revokedAt)
  const known = valid || revoked
  const outdated = valid && Boolean(data?.supersededAt)

  return (
    <div className={classes.root}>
      <Seo
        title='Перевірка звіту'
        noindex
      />
      <Link
        to={signedIn ? paths.home : paths.login}
        className={classes.brand}
        aria-label='Mitra — на головну'
      >
        <Logo />
      </Link>
      <Stack
        className={classes.inner}
        gap='lg'
      >
        <Card p='xl'>
          {complete && isPending ? (
            <Group
              justify='center'
              py='xl'
            >
              <Loader />
              <Text>Перевіряємо підпис…</Text>
            </Group>
          ) : (
            <Stack gap='lg'>
              <div>
                <Group
                  gap='xs'
                  wrap='nowrap'
                >
                  {outdated && (
                    <IconAlertCircle
                      size={32}
                      color='var(--mantine-color-warning-filled)'
                      aria-hidden
                    />
                  )}
                  {revoked && (
                    <IconBan
                      size={32}
                      color='var(--mantine-color-danger-filled)'
                      aria-hidden
                    />
                  )}
                  <Title
                    order={1}
                    c={outdated ? "warning.7" : revoked ? "danger.7" : undefined}
                  >
                    {outdated
                      ? "Застаріла редакція"
                      : valid
                        ? "Файл підписано"
                        : revoked
                          ? "Звіт відкликано"
                          : "Недійсний"}
                  </Title>
                </Group>
                <Text c='dimmed'>
                  {!complete
                    ? "Посилання неповне: відскануйте QR-код зі звіту ще раз"
                    : error
                      ? "Не вдалося звʼязатися з сервером перевірки"
                      : valid
                        ? "Перевірте файл на відповідність нижче"
                        : data?.reason}
                </Text>
              </div>

              {valid && data?.supersededAt && (
                <Alert
                  color='warning'
                  variant='light'
                  icon={<IconAlertTriangle size={18} />}
                  title='Існує новіша редакція цього звіту'
                >
                  Підпис дійсний, але {formatDateTime(data.supersededAt)} сформовано новішу редакцію за той самий
                  період. Звіряйтеся з нею: попросіть актуальний звіт у відповідальної особи.
                </Alert>
              )}

              {known && data && (
                <>
                  <div className={classes.rows}>
                    <Row
                      label='Програма'
                      value={data.programTitle}
                    />
                    <Row
                      label='Орган'
                      value={data.orgUnit}
                    />
                    <Row
                      label='Звітний період'
                      value={formatPeriod(data.period)}
                    />
                    <Row
                      label='Тип'
                      value={data.type ? <Badge variant='light'>{reportMeta[data.type]}</Badge> : "—"}
                    />
                    <Row
                      label='Сформовано'
                      value={`${formatDateTime(data.generatedAt)}${data.generatedBy ? ` · ${data.generatedBy}` : ""}`}
                    />
                    <Row
                      label='SHA-256'
                      value={
                        <Code
                          fz={11}
                          style={{ wordBreak: "break-all" }}
                        >
                          {data.sha256}
                        </Code>
                      }
                    />
                  </div>
                  {valid && (
                    <Text
                      size='sm'
                      c='dimmed'
                    >
                      Підпис HMAC-SHA256 збігається. Порівняйте дані з паперовою копією або перевірте файл нижче.
                    </Text>
                  )}
                  {signedIn && !opensReports ? (
                    <Text
                      size='sm'
                      c='dimmed'
                    >
                      Оригінал звіту в системі доступний координатору й аналітику.
                    </Text>
                  ) : (
                    <Group className={classes.actions}>
                      <Button
                        component={Link}
                        to={signedIn ? `${paths.reports}?report=${data.reportId}` : paths.login}
                        state={signedIn ? undefined : { from: `${paths.reports}?report=${data.reportId}` }}
                        rightSection={<IconExternalLink size={16} />}
                      >
                        {signedIn ? "Відкрити оригінал звіту" : "Увійти, щоб відкрити оригінал"}
                      </Button>
                      {signedIn && (
                        <Button
                          variant='default'
                          className={classes.outlined}
                          leftSection={<IconDownload size={16} />}
                          onClick={() =>
                            download(
                              `/reports/${data.reportId}/export?format=pdf`,
                              `${data.type === "INTERNAL" ? "memo" : "nazk"}-${data.period}.pdf`
                            ).catch((e: Error) => notifications.show({ color: "danger", message: e.message }))
                          }
                        >
                          Завантажити оригінал
                        </Button>
                      )}
                    </Group>
                  )}
                </>
              )}

              {revoked && (
                <Text size='sm'>
                  Документ справжній, але відповідальна особа його відкликала. Не використовуйте його: зверніться до
                  уповноваженої особи з питань запобігання корупції по актуальний звіт.
                </Text>
              )}
              {!known && (
                <Text size='sm'>
                  Не довіряйте цьому документу: він не сформований системою або був змінений. Зверніться до
                  уповноваженої особи з питань запобігання корупції.
                </Text>
              )}
            </Stack>
          )}
        </Card>
        <CopyCheckCard reportId={known && data?.reportId ? data.reportId : ""} />
        <Text
          size='xs'
          c='dimmed'
          ta='center'
        >
          Публічна перевірка справжності звітів ·{" "}
          <Anchor
            component={Link}
            to={paths.login}
            size='xs'
          >
            вхід до системи
          </Anchor>
        </Text>
      </Stack>
    </div>
  )
}
