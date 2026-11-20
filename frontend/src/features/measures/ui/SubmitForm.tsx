import { useMemo, useState } from "react"
import {
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  List,
  NumberInput,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
} from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconArrowBackUp, IconBulb, IconCheck, IconDeviceFloppy, IconFileText, IconSend } from "@tabler/icons-react"
import { Link } from "react-router"
import type { EvidenceFile, MeasureDetail } from "@/shared/api"
import type { ReactNode } from "react"

import { HttpError } from "@/shared/api"
import { resultHints } from "@/shared/lib"
import { AiNote, measurePath, SourceBadge } from "@/shared/ui"
import { useAddProgress, useSubmitMeasure } from "../api/queries"
import { isComplete, toEvidenceFile } from "../lib/evidenceFiles"
import { FilePicker } from "./FilePicker"
import { ReportIntake } from "./ReportIntake"
import type { ChosenDraft } from "./ReportIntake"

type SubmitFormProps = {
  measure: MeasureDetail
  aiSlot?: (ctx: { text: string; setText: (text: string) => void }) => ReactNode
  initialDraft?: ChosenDraft | null
}

type Mode = "done" | "notDone"

const modeOf = (outcome: ChosenDraft["outcome"], fallback: Mode): Mode =>
  outcome === "not_done" ? "notDone" : outcome === "done" ? "done" : fallback

const sameFile = (a: File, b: File) => a.name === b.name && a.size === b.size
const has = (files: EvidenceFile[], file: File) => files.some(x => sameFile(x.file, file))

export function SubmitForm({ measure, aiSlot, initialDraft }: SubmitFormProps) {
  const ownDraft = initialDraft && initialDraft.measureId === measure.id ? initialDraft : null
  const [draft, setDraft] = useState<ChosenDraft | null>(ownDraft)
  const [foreign, setForeign] = useState<ChosenDraft | null>(null)
  const [mode, setMode] = useState<Mode>(modeOf(ownDraft?.outcome ?? null, "done"))
  const [text, setText] = useState(ownDraft?.text || measure.currentPeriod?.resultDescription || "")
  const [files, setFiles] = useState<EvidenceFile[]>(ownDraft ? [toEvidenceFile(ownDraft.file)] : [])
  // Кількісний індикатор виконання заходу (власний, не індикатор ризику): факт обовʼязковий при «Виконано»
  const own = measure.indicator && measure.indicator.riskId === null ? measure.indicator : null
  const [fact, setFact] = useState<number | null>(null)
  const [serverHints, setServerHints] = useState<string[]>([])
  const submit = useSubmitMeasure(measure.id)
  const progress = useAddProgress(measure.id)
  const lastReturn = [...measure.approvals].reverse().find(a => a.decision === "RETURNED")
  const evidenceCount = measure.evidenceCount + files.length

  const hints = useMemo(
    () => (mode === "done" ? resultHints(measure.title, text, measure.requiredEvidence, evidenceCount) : []),
    [
      mode,
      measure.title,
      measure.requiredEvidence,
      text,
      evidenceCount,
    ]
  )
  const blocking = mode === "done" && Boolean(measure.requiredEvidence) && evidenceCount === 0
  const needsFact = mode === "done" && own !== null && fact === null
  const filesIncomplete = mode === "done" && !isComplete(files)

  const applyDraft = (d: ChosenDraft) => {
    if (d.measureId !== measure.id) {
      setForeign(d)
      return
    }
    setForeign(null)
    setDraft(d)
    setMode(m => modeOf(d.outcome, m))
    if (d.text) setText(d.text)
    setFiles(f => (has(f, d.file) ? f : [...f, toEvidenceFile(d.file)]))
  }

  const dropDraft = () => {
    if (draft) setFiles(f => f.filter(x => !sameFile(x.file, draft.file)))
    setDraft(null)
  }

  const onSubmit = () =>
    submit.mutate(
      {
        resultDescription: mode === "done" ? text.trim() : undefined,
        nonExecutionReason: mode === "notDone" ? text.trim() : undefined,
        period: measure.period ?? undefined,
        files: mode === "done" ? files : [],
        aiDraftKey: draft?.draftKey,
        indicatorValue: mode === "done" ? fact : null,
      },
      {
        onSuccess: res => {
          setFiles([])
          setFact(null)
          setDraft(null)
          setServerHints(res.hints)
          notifications.show({
            color: "success",
            icon: <IconCheck size={18} />,
            title: "Надіслано на перевірку",
            message: res.hints.length ? "Координатор побачить ваші підказки" : "Статус: «На перевірці»",
          })
        },
        onError: e => {
          if (e instanceof HttpError && e.hints.length) setServerHints(e.hints)
        },
      }
    )

  return (
    <Card>
      <Stack gap='md'>
        <div>
          <Text
            fw={600}
            size='lg'
          >
            Внесення результату за один крок
          </Text>
          <Text
            size='sm'
            c='dimmed'
          >
            Опис і документи надсилаються разом — після цього захід переходить «На перевірку».
          </Text>
        </div>

        {lastReturn && measure.status === "RETURNED" && (
          <Alert
            color='orange'
            variant='light'
            title='Зауваження координатора'
          >
            {lastReturn.comment}
          </Alert>
        )}

        {!draft && (
          <ReportIntake
            compact
            period={measure.period}
            onDraft={applyDraft}
          />
        )}

        {foreign && (
          <Alert
            color='warning'
            variant='light'
            title='Документ про інший захід'
            withCloseButton
            onClose={() => setForeign(null)}
          >
            <Text size='sm'>
              Звіт «{foreign.fileName}» стосується заходу{" "}
              <Anchor
                component={Link}
                to={measurePath(foreign.measureId)}
                state={{ draft: foreign }}
              >
                {foreign.candidates.find(c => c.measureId === foreign.measureId)?.code ?? "іншого"}
              </Anchor>
              . Відкрийте його, щоб внести результат там.
            </Text>
          </Alert>
        )}

        {draft && (
          <Alert
            color='violet'
            variant='light'
            icon={<IconFileText size={18} />}
            title={`Заповнено з документа «${draft.fileName}»`}
            withCloseButton
            closeButtonLabel='Прибрати чернетку'
            onClose={dropDraft}
          >
            <Stack gap={6}>
              <Group gap={6}>
                <Text size='sm'>Захід:</Text>
                <SourceBadge source={draft.measureSource} />
                <Text size='sm'>Стан:</Text>
                <SourceBadge source={draft.outcomeSource} />
                <Text size='sm'>Текст:</Text>
                <SourceBadge source={draft.textSource} />
              </Group>
              {draft.warnings.length > 0 && (
                <List
                  size='sm'
                  spacing={2}
                >
                  {draft.warnings.map(w => (
                    <List.Item key={w}>{w}</List.Item>
                  ))}
                </List>
              )}
              <AiNote>{draft.disclaimer}</AiNote>
            </Stack>
          </Alert>
        )}

        <SegmentedControl
          value={mode}
          onChange={v => setMode(v as Mode)}
          data={[
            { value: "done", label: "Виконано" },
            { value: "notDone", label: "Не виконано" },
          ]}
          fullWidth
        />

        <Textarea
          label={
            <Group
              gap={6}
              component='span'
            >
              {mode === "done" ? "Опис результату" : "Причини невиконання"}
              {draft && text === draft.text && <SourceBadge source={draft.textSource} />}
            </Group>
          }
          description={
            mode === "done"
              ? "Що саме змінилось: числа, реквізити наказу чи протоколу, посилання"
              : "Поясніть причини — вони потраплять у звіт НАЗК"
          }
          placeholder={
            mode === "done"
              ? "Напр.: Затверджено наказом № 245 від 12.11.2026; навчено 48 працівників (протокол № 7)"
              : "Напр.: Не виділено фінансування, лист № 112 від 03.11.2026"
          }
          autosize
          minRows={4}
          value={text}
          onChange={e => setText(e.currentTarget.value)}
          required
        />

        {draft && draft.textSource === "model" && draft.documentText && text !== draft.documentText && (
          <Button
            variant='subtle'
            size='xs'
            w='fit-content'
            leftSection={<IconArrowBackUp size={14} />}
            onClick={() => setText(draft.documentText)}
          >
            Повернути текст документа
          </Button>
        )}

        {aiSlot?.({ text, setText })}

        {mode === "done" && own && (
          <NumberInput
            label={`Фактичне значення індикатора: ${own.name}`}
            description={`Ціль ${Number(own.target).toLocaleString("uk-UA")} ${own.unit}`.trim()}
            placeholder={String(Number(own.target))}
            min={0}
            value={fact ?? ""}
            onChange={v => setFact(v === "" ? null : Number(v))}
            required
          />
        )}

        {mode === "done" && (
          <FilePicker
            files={files}
            onChange={setFiles}
            label={measure.evidenceCount ? `Додати ще файли (вже ${measure.evidenceCount})` : "Додати підтвердні файли"}
          />
        )}

        {(hints.length > 0 || serverHints.length > 0 || Boolean(draft?.hints.length)) && (
          <Alert
            color={blocking ? "danger" : "warning"}
            variant='light'
            icon={<IconBulb size={18} />}
            title='Підказки'
          >
            <List
              size='sm'
              spacing={4}
            >
              {[
                ...new Set([
                  ...hints,
                  ...(draft?.hints ?? []),
                  ...serverHints,
                ]),
              ].map(h => (
                <List.Item key={h}>{h}</List.Item>
              ))}
            </List>
          </Alert>
        )}

        {submit.error && !(submit.error instanceof HttpError && submit.error.hints.length) && (
          <Alert
            color='danger'
            variant='light'
          >
            {submit.error.message}
          </Alert>
        )}

        <Group
          justify='space-between'
          gap='sm'
        >
          <Button
            variant='default'
            leftSection={<IconDeviceFloppy size={16} />}
            disabled={!text.trim() || mode !== "done"}
            loading={progress.isPending}
            onClick={() =>
              progress.mutate(
                { text: text.trim(), period: measure.period ?? undefined },
                {
                  onSuccess: () => notifications.show({ color: "success", message: "Проміжний результат збережено" }),
                  onError: e => notifications.show({ color: "danger", message: e.message }),
                }
              )
            }
          >
            Проміжний результат
          </Button>
          <Button
            leftSection={<IconSend size={16} />}
            disabled={!text.trim() || blocking || needsFact || filesIncomplete}
            loading={submit.isPending}
            onClick={onSubmit}
          >
            Надіслати на перевірку
          </Button>
        </Group>
      </Stack>
    </Card>
  )
}
