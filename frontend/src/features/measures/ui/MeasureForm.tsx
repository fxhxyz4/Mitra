import { useState } from "react"
import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  List,
  Modal,
  NumberInput,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconFileCheck } from "@tabler/icons-react"
import { Link } from "react-router"
import type { MeasureDetail, MeasureDraft, MeasureIn } from "@/shared/api"
import type { ReactNode } from "react"

import { useOrgUnits, useRisks } from "@/shared/api"
import { sectionShort } from "@/shared/lib"
import { AiNote, DateField, DocumentDrop, measurePath, SearchMultiSelect, SearchSelect, SourceBadge } from "@/shared/ui"
import { useIntakeMeasure, useSaveMeasure } from "../api/queries"
import { IntakeError } from "./IntakeError"

type MeasureFormProps = {
  opened: boolean
  onClose: () => void
  sections: { id: string; number: number }[]
  measure?: MeasureDetail
  defaultSectionId?: string
  programId?: string
  draft?: MeasureDraft | null
  locked?: boolean
}

type FieldKey = keyof MeasureIn

const draftKeys: Partial<Record<FieldKey, string>> = {
  sectionId: "section",
  code: "code",
  title: "title",
  isPermanent: "isPermanent",
  plannedDeadline: "plannedDeadline",
  riskId: "risk",
  indicatorText: "indicator",
  requiredEvidence: "requiredEvidence",
  assignments: "assignments",
}

const emptyForm = (sectionId: string): MeasureIn => ({
  sectionId,
  code: "",
  title: "",
  isPermanent: false,
  plannedDeadline: "",
  riskId: null,
  indicatorText: "",
  indicatorUnit: "",
  indicatorTarget: null,
  requiredEvidence: "",
  assignments: [],
})

const fromMeasure = (m: MeasureDetail, sectionId: string): MeasureIn => ({
  sectionId,
  code: m.code,
  title: m.title,
  isPermanent: m.isPermanent,
  plannedDeadline: m.plannedDeadline,
  riskId: m.risk?.id ?? null,
  indicatorText: m.indicatorText,
  indicatorUnit: m.indicator?.unit ?? "",
  indicatorTarget: m.indicator ? Number(m.indicator.target) : null,
  requiredEvidence: m.requiredEvidence,
  assignments: m.assignments.map(a => ({ orgUnitId: a.orgUnitId, userId: a.userId, isResponsible: a.isResponsible })),
})

const fromDraft = ({ measure: d }: MeasureDraft, sectionId: string): MeasureIn => ({
  ...emptyForm(d.sectionId ?? sectionId),
  code: d.code,
  title: d.title,
  isPermanent: d.isPermanent,
  plannedDeadline: d.plannedDeadline ?? "",
  riskId: d.riskId,
  indicatorText: d.indicatorText,
  indicatorUnit: d.indicatorUnit,
  indicatorTarget: d.indicatorTarget === null ? null : Number(d.indicatorTarget),
  requiredEvidence: d.requiredEvidence,
  assignments: d.assignments,
})

function DraftSummary({ draft, onReset }: { draft: MeasureDraft; onReset: () => void }) {
  return (
    <Alert
      variant='light'
      color='blue'
      icon={<IconFileCheck size={18} />}
      title={`Заповнено з документа «${draft.fileName}»`}
    >
      <Stack gap={6}>
        <Text size='sm'>
          Біля кожного поля позначено джерело значення. Перевірте форму — захід створиться лише після натискання
          «Створити захід».
        </Text>
        {draft.warnings.length > 0 && (
          <List
            size='sm'
            c='warning'
          >
            {draft.warnings.map(w => (
              <List.Item key={w}>{w}</List.Item>
            ))}
          </List>
        )}
        {draft.similar.length > 0 && (
          <Stack gap={2}>
            <Text
              size='sm'
              fw={500}
            >
              Схожі заходи вже є в програмі:
            </Text>
            {draft.similar.map(m => (
              <Anchor
                key={m.measureId}
                component={Link}
                to={measurePath(m.measureId)}
                size='sm'
                target='_blank'
              >
                {m.code} — {m.title} ({Math.round(m.score * 100)}%)
              </Anchor>
            ))}
          </Stack>
        )}
        {draft.modelUsed && <AiNote>{draft.disclaimer}</AiNote>}
        <Group>
          <Button
            size='compact-sm'
            variant='subtle'
            onClick={onReset}
          >
            Очистити форму
          </Button>
        </Group>
      </Stack>
    </Alert>
  )
}

function MeasureFormBody({
  onClose,
  sections,
  measure,
  defaultSectionId,
  programId,
  draft: initialDraft,
  locked = false,
}: Omit<MeasureFormProps, "opened">) {
  const sectionOf = (n: number) => sections.find(s => s.number === n)?.id ?? ""
  const fallbackSection = defaultSectionId ?? sections[0]?.id ?? ""
  const [draft, setDraft] = useState<MeasureDraft | null>(measure ? null : (initialDraft ?? null))
  const [form, setForm] = useState<MeasureIn>(() => {
    if (measure) return fromMeasure(measure, sectionOf(measure.sectionNumber))
    if (initialDraft) return fromDraft(initialDraft, fallbackSection)
    return emptyForm(fallbackSection)
  })
  const orgUnits = useOrgUnits()
  const risks = useRisks()
  const save = useSaveMeasure(measure?.id)
  const intake = useIntakeMeasure()
  const set = <K extends keyof MeasureIn>(key: K, value: MeasureIn[K]) => setForm(f => ({ ...f, [key]: value }))

  const applyDraft = (d: MeasureDraft) => {
    setDraft(d)
    setForm(fromDraft(d, fallbackSection))
  }
  const resetDraft = () => {
    setDraft(null)
    intake.reset()
    setForm(emptyForm(fallbackSection))
  }
  const fieldOf = (key: FieldKey) => {
    const name = draftKeys[key]
    return name ? draft?.fields[name] : undefined
  }
  const label = (text: string, key: FieldKey): ReactNode => {
    const field = fieldOf(key)
    if (!field) return text
    return (
      <Group
        gap={6}
        component='span'
        display='inline-flex'
      >
        {text}
        <SourceBadge source={field.source} />
      </Group>
    )
  }
  const docNote = (key: FieldKey, fallback?: string) => {
    const field = fieldOf(key)
    if (field?.documentValue && field.documentValue !== String(field.value ?? ""))
      return `У документі: «${field.documentValue}»`
    return fallback
  }

  const responsible = form.assignments.find(a => a.isResponsible)?.orgUnitId ?? null
  const coExecutors = form.assignments.filter(a => !a.isResponsible).map(a => a.orgUnitId)
  const setUnits = (resp: string | null, co: string[]) => {
    const keep = (id: string) => form.assignments.find(a => a.orgUnitId === id)?.userId ?? null
    set("assignments", [
      ...(resp ? [{ orgUnitId: resp, userId: keep(resp), isResponsible: true }] : []),
      ...co.filter(id => id !== resp).map(id => ({ orgUnitId: id, userId: keep(id), isResponsible: false })),
    ])
  }

  const unitOptions = (orgUnits.data ?? []).map(u => ({ value: u.id, label: u.name }))
  const valid = form.title.trim() && form.plannedDeadline && form.sectionId && responsible

  return (
    <form
      onSubmit={e => {
        e.preventDefault()
        if (!valid) return
        save.mutate(
          { ...form, title: form.title.trim(), code: form.code.trim() },
          {
            onSuccess: () => {
              notifications.show({ color: "success", message: measure ? "Захід оновлено" : "Захід створено" })
              onClose()
            },
          }
        )
      }}
    >
      <Stack gap='sm'>
        {draft && (
          <DraftSummary
            draft={draft}
            onReset={resetDraft}
          />
        )}
        {!measure && !draft && programId && (
          <Stack gap='xs'>
            <DocumentDrop
              compact
              loading={intake.isPending}
              onFile={file => intake.mutate({ file, programId }, { onSuccess: applyDraft })}
              title='Заповнити з картки заходу (зразок B)'
              description='Перетягніть .docx, .xlsx, .pdf або .txt — поля заповняться, ви перевірите'
            />
            <IntakeError
              error={intake.error}
              sample='B'
            />
          </Stack>
        )}
        {locked && (
          <Alert
            color='gray'
            variant='light'
          >
            Програму затверджено: змінювати можна лише виконавців. Паспорт заходу зафіксовано.
          </Alert>
        )}
        <Group
          grow
          align='flex-start'
        >
          <Select
            label={label("Розділ", "sectionId")}
            description={docNote("sectionId")}
            data={sections.map(s => ({ value: s.id, label: `${s.number}. ${sectionShort[s.number] ?? ""}` }))}
            value={form.sectionId}
            onChange={v => v && set("sectionId", v)}
            allowDeselect={false}
            required
            disabled={locked}
          />
          <TextInput
            label={label("Номер", "code")}
            description={docNote("code")}
            placeholder='2.7'
            value={form.code}
            onChange={e => set("code", e.currentTarget.value)}
            maw={120}
            disabled={locked}
          />
        </Group>
        <Textarea
          label={label("Назва заходу", "title")}
          description={docNote("title")}
          autosize
          minRows={2}
          value={form.title}
          onChange={e => set("title", e.currentTarget.value)}
          required
          disabled={locked}
        />
        <Group
          grow
          align='flex-end'
        >
          <DateField
            label={label("Плановий строк", "plannedDeadline")}
            description={docNote("plannedDeadline")}
            value={form.plannedDeadline}
            onChange={v => set("plannedDeadline", v ?? "")}
            required
            disabled={locked}
          />
          <Checkbox
            label={label("Постійний захід (щопівроку)", "isPermanent")}
            checked={form.isPermanent}
            onChange={e => set("isPermanent", e.currentTarget.checked)}
            mb={8}
            disabled={locked}
          />
        </Group>
        <SearchSelect
          label={label("Відповідальний підрозділ", "assignments")}
          description={docNote("assignments")}
          data={unitOptions}
          value={responsible}
          onChange={v => setUnits(v, coExecutors)}
          required
        />
        <SearchMultiSelect
          label='Співвиконавці'
          data={unitOptions.filter(o => o.value !== responsible)}
          value={coExecutors}
          onChange={v => setUnits(responsible, v)}
          clearable
        />
        <SearchSelect
          label={label("Корупційний ризик", "riskId")}
          description={docNote("riskId")}
          data={(risks.data ?? []).map(r => ({ value: r.id, label: `${r.code} — ${r.description}` }))}
          value={form.riskId ?? null}
          onChange={v => set("riskId", v)}
          clearable
          disabled={locked}
        />
        <TextInput
          label={label("Індикатор виконання заходу", "indicatorText")}
          description={docNote(
            "indicatorText",
            "Як у програмі НАЗК: за чим видно, що захід виконано. Індикатор ризику задається в реєстрі ризиків."
          )}
          placeholder='Частка призначень на вразливі посади з проведеною перевіркою'
          value={form.indicatorText}
          onChange={e => set("indicatorText", e.currentTarget.value)}
          disabled={locked}
        />
        <Group
          grow
          align='flex-start'
        >
          <NumberInput
            label='Ціль індикатора'
            description='Лише для кількісного індикатора'
            placeholder='100'
            min={0}
            value={form.indicatorTarget ?? ""}
            onChange={v => set("indicatorTarget", v === "" ? null : Number(v))}
            disabled={locked || !form.indicatorText.trim()}
          />
          <TextInput
            label='Одиниця'
            description='%, осіб, шт.'
            placeholder='%'
            value={form.indicatorUnit}
            onChange={e => set("indicatorUnit", e.currentTarget.value)}
            disabled={locked || form.indicatorTarget === null}
          />
        </Group>
        <TextInput
          label={label("Які документи потрібні", "requiredEvidence")}
          description={docNote("requiredEvidence", "Виконавець побачить підказку при внесенні результату")}
          placeholder='Наказ про затвердження, протокол навчання'
          value={form.requiredEvidence}
          onChange={e => set("requiredEvidence", e.currentTarget.value)}
          disabled={locked}
        />
        {save.error && (
          <Alert
            color='danger'
            variant='light'
          >
            {save.error.message}
          </Alert>
        )}
        <Group
          justify='flex-end'
          mt='sm'
        >
          <Button
            variant='default'
            onClick={onClose}
          >
            Скасувати
          </Button>
          <Button
            type='submit'
            disabled={!valid}
            loading={save.isPending}
          >
            {measure ? "Зберегти" : "Створити захід"}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}

export function MeasureForm({ opened, onClose, ...props }: MeasureFormProps) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={props.measure ? `Редагування заходу ${props.measure.code}` : "Новий захід"}
      size='lg'
    >
      {opened && (
        <MeasureFormBody
          onClose={onClose}
          {...props}
        />
      )}
    </Modal>
  )
}
