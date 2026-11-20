import { useState } from "react"
import {
  Alert,
  Button,
  Checkbox,
  Divider,
  Group,
  Modal,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core"
import { notifications } from "@mantine/notifications"
import type { RiskCreate, RiskLevel } from "@/shared/api"

import { useOrgUnits } from "@/shared/api"
import { DateField, LevelBadge, SearchSelect } from "@/shared/ui"
import { useCreateRisk } from "../api"

/** Межі рівнів за Методологією НАЗК № 830/21. */
const levelOf = (score: number): RiskLevel =>
  score >= 12 ? "CRITICAL" : score >= 6 ? "HIGH" : score >= 3 ? "MEDIUM" : "LOW"

const SCALE = [
  { value: "1", label: "1 низька" },
  { value: "2", label: "2 середня" },
  { value: "3", label: "3 висока" },
  { value: "4", label: "4 дуже висока" },
]

type Kri = { name: string; unit: string; direction: "LOWER" | "HIGHER"; baseline: number | null; target: number | null }

const empty: Omit<RiskCreate, "indicator"> = {
  code: "",
  description: "",
  probability: 2,
  impact: 2,
  process: "",
  content: "",
  sources: "",
  existingControls: "",
  ownerUnitId: null,
}

/** Запис реєстру корупційних ризиків (словник: ryzyky): бали ставить робоча група, рівень — з балу; KRI — разом. */
export function RiskRegisterForm({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const units = useOrgUnits()
  const create = useCreateRisk()
  const [form, setForm] = useState(empty)
  const [kri, setKri] = useState<Kri>({ name: "", unit: "%", direction: "LOWER", baseline: null, target: null })
  const [kriMeta, setKriMeta] = useState({ targetDate: null as string | null, source: "", independent: true })
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm(f => ({ ...f, [k]: v }))
  const score = form.probability * form.impact
  const kriFilled = kri.name.trim() !== ""
  const kriProblem = !kriFilled
    ? null
    : kri.baseline === null || kri.target === null
      ? "Вкажіть базу і ціль індикатора"
      : kri.baseline === kri.target
        ? "Ціль дорівнює базі"
        : kri.direction === "LOWER" && kri.target > kri.baseline
          ? "«Менше — краще», а ціль більша за базу"
          : kri.direction === "HIGHER" && kri.target < kri.baseline
            ? "«Більше — краще», а ціль менша за базу"
            : null
  const valid = form.code.trim() && form.description.trim() && !kriProblem

  const submit = () =>
    create.mutate(
      {
        ...form,
        code: form.code.trim(),
        indicator:
          kriFilled && kri.baseline !== null && kri.target !== null
            ? { ...kri, baseline: kri.baseline, target: kri.target, ...kriMeta }
            : null,
      },
      {
        onSuccess: r => {
          notifications.show({ color: "success", message: `Ризик ${r.code} додано до реєстру` })
          setForm(empty)
          setKri({ name: "", unit: "%", direction: "LOWER", baseline: null, target: null })
          onClose()
        },
        onError: e => notifications.show({ color: "danger", message: e.message }),
      }
    )

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title='Новий корупційний ризик'
      size='lg'
    >
      <Stack gap='sm'>
        <Group
          grow
          align='flex-start'
        >
          <TextInput
            label='Код'
            placeholder='KR15'
            required
            value={form.code}
            onChange={e => set("code", e.currentTarget.value)}
          />
          <SearchSelect
            label='Власник ризику (підрозділ)'
            data={(units.data ?? []).map(u => ({ value: u.id, label: u.name }))}
            value={form.ownerUnitId ?? null}
            onChange={v => set("ownerUnitId", v)}
            clearable
          />
        </Group>
        <TextInput
          label='Функція, процес організації'
          placeholder='Публічні закупівлі'
          value={form.process}
          onChange={e => set("process", e.currentTarget.value)}
        />
        <TextInput
          label='Корупційний ризик'
          required
          placeholder='Дискримінаційні вимоги в тендерній документації'
          value={form.description}
          onChange={e => set("description", e.currentTarget.value)}
        />
        <Textarea
          label='Зміст корупційного ризику'
          autosize
          minRows={2}
          value={form.content}
          onChange={e => set("content", e.currentTarget.value)}
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Textarea
            label='Джерела ризику'
            autosize
            minRows={2}
            value={form.sources}
            onChange={e => set("sources", e.currentTarget.value)}
          />
          <Textarea
            label='Існуючі заходи контролю'
            autosize
            minRows={2}
            value={form.existingControls}
            onChange={e => set("existingControls", e.currentTarget.value)}
          />
        </SimpleGrid>

        <Divider label='Оцінка робочої групи (Методологія НАЗК)' />
        <Stack gap={4}>
          <Text size='sm'>Ймовірність</Text>
          <SegmentedControl
            data={SCALE}
            value={String(form.probability)}
            onChange={v => set("probability", Number(v))}
          />
          <Text size='sm'>Наслідки (найвищий з 4 категорій втрат)</Text>
          <SegmentedControl
            data={SCALE}
            value={String(form.impact)}
            onChange={v => set("impact", Number(v))}
          />
          <Group gap={6}>
            <Text size='sm'>
              Бал {form.probability}·{form.impact} = {score}
            </Text>
            <LevelBadge
              level={levelOf(score)}
              size='sm'
            />
          </Group>
        </Stack>

        <Divider label='Індикатор ризику (KRI): чи зменшується ризик' />
        <TextInput
          label='Назва індикатора'
          placeholder='Частка процедур закупівель з одним учасником'
          value={kri.name}
          onChange={e => {
            const name = e.currentTarget.value
            setKri(k => ({ ...k, name }))
          }}
        />
        <SimpleGrid cols={{ base: 2, sm: 4 }}>
          <Select
            label='Напрям'
            data={[
              { value: "LOWER", label: "менше — краще" },
              { value: "HIGHER", label: "більше — краще" },
            ]}
            value={kri.direction}
            onChange={v => setKri(k => ({ ...k, direction: (v as Kri["direction"]) ?? "LOWER" }))}
            allowDeselect={false}
            disabled={!kriFilled}
          />
          <NumberInput
            label='База'
            value={kri.baseline ?? ""}
            onChange={v => setKri(k => ({ ...k, baseline: v === "" ? null : Number(v) }))}
            disabled={!kriFilled}
          />
          <NumberInput
            label='Ціль'
            value={kri.target ?? ""}
            onChange={v => setKri(k => ({ ...k, target: v === "" ? null : Number(v) }))}
            disabled={!kriFilled}
          />
          <TextInput
            label='Одиниця'
            value={kri.unit}
            onChange={e => {
              const unit = e.currentTarget.value
              setKri(k => ({ ...k, unit }))
            }}
            disabled={!kriFilled}
          />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <DateField
            label='Дедлайн цілі'
            value={kriMeta.targetDate}
            onChange={targetDate => setKriMeta(m => ({ ...m, targetDate }))}
            disabled={!kriFilled}
          />
          <TextInput
            label='Джерело даних'
            placeholder='Prozorro, реєстр, інвентаризація'
            value={kriMeta.source}
            onChange={e => {
              const source = e.currentTarget.value
              setKriMeta(m => ({ ...m, source }))
            }}
            disabled={!kriFilled}
          />
        </SimpleGrid>
        <Checkbox
          label='Незалежне джерело (самозвітні дані: позитивний прогрес × 0,5)'
          checked={kriMeta.independent}
          onChange={e => {
            const independent = e.currentTarget.checked
            setKriMeta(m => ({ ...m, independent }))
          }}
          disabled={!kriFilled}
        />
        {kriProblem && (
          <Alert
            color='danger'
            variant='light'
          >
            {kriProblem}
          </Alert>
        )}
        <Group justify='flex-end'>
          <Button
            disabled={!valid}
            loading={create.isPending}
            onClick={submit}
          >
            Додати до реєстру
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
