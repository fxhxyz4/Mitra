import type { FlagType, MeasureStatus, RecStatus, ReportType, RiskLevel, Role } from "@/shared/api"

export const statusMeta: Record<MeasureStatus, { label: string; color: string }> = {
  DRAFT: { label: "Чернетка", color: "gray" },
  PLANNED: { label: "Заплановано", color: "blue" },
  IN_PROGRESS: { label: "В роботі", color: "cyan" },
  ON_REVIEW: { label: "На перевірці", color: "violet" },
  RETURNED: { label: "Повернено", color: "orange" },
  DONE: { label: "Виконано", color: "success" },
  PARTIAL: { label: "Частково виконано", color: "teal" },
  NOT_DONE: { label: "Не виконано", color: "danger" },
}

export const statusOrder: MeasureStatus[] = [
  "DRAFT",
  "PLANNED",
  "IN_PROGRESS",
  "ON_REVIEW",
  "RETURNED",
  "DONE",
  "PARTIAL",
  "NOT_DONE",
]

export const flagMeta: Record<FlagType, { label: string; rule: string; color: string }> = {
  OVERDUE: { label: "Прострочено", rule: "R1", color: "danger" },
  NO_EVIDENCE: { label: "Виконання не підтверджено", rule: "E1", color: "danger" },
  FORMAL_CLOSURE: { label: "Формальне закриття", rule: "F1", color: "danger" },
  WORSENING: { label: "Погіршення попри виконання", rule: "F2", color: "danger" },
  AWAITING_EFFECT: { label: "Очікування ефекту (застаріле)", rule: "F3", color: "gray" },
  VAGUE_RESULT: { label: "Неінформативний опис", rule: "R4", color: "warning" },
  TARGET_MISSED: { label: "Показник не досягнуто", rule: "R5", color: "pink" },
  REPEATED_DELAY: { label: "Повторне порушення строків", rule: "R6", color: "red" },
  REPEATED_POSTPONEMENT: { label: "Строк переносили двічі і більше", rule: "R6a", color: "orange" },
  DATE_OUT_OF_PERIOD: { label: "Дата виконання поза періодом", rule: "R7a", color: "orange" },
  BACKDATED_EVIDENCE: { label: "Підтвердження «заднім числом»", rule: "R7b", color: "danger" },
  NO_EXPLANATION: { label: "Не виконано без пояснення", rule: "R7c", color: "warning" },
  PREMATURE_DESCRIPTION: { label: "Опис до настання строку", rule: "R7e", color: "gray" },
}

export const signalColor: Record<string, string> = {
  red: "danger",
  orange: "orange",
  yellow: "warning",
  gray: "gray",
  green: "success",
}

export const flagOrder: FlagType[] = [
  "OVERDUE",
  "NO_EVIDENCE",
  "FORMAL_CLOSURE",
  "WORSENING",
  "VAGUE_RESULT",
  "TARGET_MISSED",
  "REPEATED_DELAY",
  "REPEATED_POSTPONEMENT",
  "DATE_OUT_OF_PERIOD",
  "BACKDATED_EVIDENCE",
  "NO_EXPLANATION",
  "PREMATURE_DESCRIPTION",
]

export const levelMeta: Record<RiskLevel, { label: string; color: string }> = {
  LOW: { label: "Низький", color: "success" },
  MEDIUM: { label: "Середній", color: "warning" },
  HIGH: { label: "Високий", color: "danger" },
  CRITICAL: { label: "Критичний", color: "grape" },
}

export const roleMeta: Record<Role, { label: string; color: string }> = {
  EXECUTOR: { label: "Виконавець", color: "warning" },
  COORDINATOR: { label: "Координатор", color: "success" },
  HEAD: { label: "Керівник", color: "cyan" },
  ANALYST: { label: "Аналітик", color: "violet" },
  ADMIN: { label: "Адміністратор", color: "gray" },
}

export const recMeta: Record<RecStatus, { label: string; color: string }> = {
  PROPOSED: { label: "На рішення", color: "blue" },
  ACCEPTED: { label: "Прийнято", color: "success" },
  REJECTED: { label: "Відхилено", color: "gray" },
  DONE: { label: "Виконано", color: "teal" },
}

export const reportMeta: Record<ReportType, string> = {
  NAZK: "Портал НАЗК",
  PRINT: "Друкована форма",
  INTERNAL: "Аналітична довідка",
}

export const sectionShort: Record<number, string> = {
  1: "Відомча політика і стратегія",
  2: "Усунення корупційних ризиків",
  3: "Навчання і поширення інформації",
}

export const actionLabels: Record<string, string> = {
  create: "Створено",
  update: "Змінено",
  submit: "Надіслано на перевірку",
  approve: "Погоджено",
  return: "Повернено",
  progress: "Проміжний результат",
  transition: "Зміна статусу",
  upload: "Завантажено файл",
  resolve: "Знято",
  open: "Відкрито",
  propose: "Запропоновано",
  accept: "Прийнято",
  reject: "Відхилено",
  login: "Вхід",
  auto_resolve: "Знято автоматично",
  generate: "Сформовано",
  reissue_token: "Перевипущено токен",
  status: "Зміна статусу",
  import: "Імпортовано",
  create_incident: "Зареєстровано інцидент",
  postpone: "Перенесено внутрішній строк",
  receive: "Отримано",
  link: "Повʼязано",
  retry: "Повторне відправлення",
}

export const entityLabels: Record<string, string> = {
  measure: "Захід",
  measure_period: "Період заходу",
  evidence: "Документ",
  risk_flag: "Risk Flag",
  recommendation: "Рекомендація",
  program: "Програма",
  user: "Користувач",
  indicator: "Індикатор",
  indicator_value: "Значення індикатора",
  report: "Звіт",
  org_unit: "Підрозділ",
  risk: "Ризик",
  corruption_risk: "Корупційний ризик",
  incident: "Інцидент",
  risk_signal: "Сигнал ризику",
  integra_inbox: "Вхідний захід Integra",
  outbox: "Відправлення в Integra",
}

export const describeAction = (action: string) => {
  const m = /^status:(\w+)->(\w+)$/.exec(action)
  if (m) {
    const from = statusMeta[m[1] as MeasureStatus]?.label ?? m[1]
    const to = statusMeta[m[2] as MeasureStatus]?.label ?? m[2]
    return `${from} → ${to}`
  }
  return actionLabels[action] ?? action
}
