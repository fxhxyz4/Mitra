import { env } from "@/shared/config"
import { aiQueue } from "./aiQueue"
import { session } from "./session"

export class HttpError extends Error {
  readonly status: number
  readonly hints: string[]

  constructor(status: number, message: string, hints: string[] = []) {
    super(message)
    this.name = "HttpError"
    this.status = status
    this.hints = hints
  }
}

type ValidationItem = { type?: string; loc?: (string | number)[]; msg?: string; ctx?: Record<string, unknown> }

type Detail =
  string | { message?: string; hints?: string[]; missingFields?: string[]; errors?: string[] } | ValidationItem[]

const fieldNames: Record<string, string> = {
  comment: "Коментар",
  text: "Текст",
  title: "Назва",
  displayName: "Імʼя",
  resultDescription: "Опис результату",
  nonExecutionReason: "Причина невиконання",
  plannedDeadline: "Строк",
  dueDate: "Строк",
  responsibleId: "Відповідальний",
  question: "Питання",
  justification: "Обґрунтування",
  baseline: "Базове значення",
  target: "Цільове значення",
  value: "Значення",
  measuredAt: "Дата вимірювання",
  token: "Токен",
  address: "Адреса",
  orgUnitId: "Підрозділ",
  sectionId: "Розділ",
  periodStart: "Початок періоду",
  periodEnd: "Кінець періоду",
}

export function validationMessage(item: ValidationItem): string {
  const field = [...(item.loc ?? [])].reverse().find((x): x is string => typeof x === "string" && x !== "body")
  const label = field ? (fieldNames[field] ?? field) : ""
  const ctx = item.ctx ?? {}
  const what = (() => {
    switch (item.type) {
      case "missing":
        return "обовʼязкове поле"
      case "string_too_short":
        return `щонайменше ${String(ctx.min_length)} симв.`
      case "string_too_long":
        return `не більше ${String(ctx.max_length)} симв.`
      case "too_short":
        return `щонайменше ${String(ctx.min_length)} елем.`
      case "greater_than":
        return `має бути більше ${String(ctx.gt)}`
      case "greater_than_equal":
        return `має бути не менше ${String(ctx.ge)}`
      case "less_than":
        return `має бути менше ${String(ctx.lt)}`
      case "less_than_equal":
        return `має бути не більше ${String(ctx.le)}`
      case "date_parsing":
      case "date_from_datetime_parsing":
      case "date_type":
        return "некоректна дата"
      case "int_parsing":
      case "float_parsing":
      case "decimal_parsing":
        return "потрібне число"
      case "enum":
      case "literal_error":
        return "недопустиме значення"
      case "uuid_parsing":
        return "оберіть значення зі списку"
      case "value_error":
        return (item.msg ?? "").replace(/^Value error,\s*/, "")
      default:
        return "некоректне значення"
    }
  })()
  return label ? `${label}: ${what}` : what
}

const statusText: Record<number, string> = {
  413: "Файл завеликий",
  502: "Сервер тимчасово недоступний",
  503: "Сервер тимчасово недоступний",
  504: "Сервер не відповів вчасно",
}

export function parseError(status: number, raw: string): HttpError {
  try {
    const { detail } = JSON.parse(raw) as { detail?: Detail }
    if (typeof detail === "string") return new HttpError(status, detail)
    if (Array.isArray(detail)) {
      const text = [...new Set(detail.map(validationMessage))].join("; ")
      return new HttpError(status, text || "Перевірте заповнення полів")
    }
    if (detail && "message" in detail)
      return new HttpError(status, detail.message ?? "", detail.hints ?? detail.missingFields ?? detail.errors ?? [])
  } catch {
    const html = raw.trimStart().startsWith("<")
    return new HttpError(status, statusText[status] ?? (!html && raw ? raw : `Помилка ${status}`))
  }
  return new HttpError(status, `Помилка ${status}`)
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const isForm = init?.body instanceof FormData
  const signedIn = session.signedIn()
  const res = await fetch(`${env.apiUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "X-Requested-With": "mitra",
      ...(isForm || !init?.body ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  })
  if (res.status === 401 && signedIn && !path.startsWith("/auth/")) session.clear()
  if (!res.ok) throw parseError(res.status, await res.text())
  return res
}

interface AiJob {
  jobId: string
  status: "queued" | "running" | "done" | "failed"
  ahead?: number
  result?: unknown
  error?: { status: number; detail: Detail }
}

const JOB_POLL_MS = 1500
const JOB_MAX_MS = 15 * 60_000

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

async function awaitJob<T>(job: AiJob): Promise<T> {
  const started = Date.now()
  let state = job
  try {
    while (state.status === "queued" || state.status === "running") {
      aiQueue.set({ jobId: job.jobId, status: state.status, ahead: state.ahead ?? 0 })
      if (Date.now() - started > JOB_MAX_MS) throw new HttpError(504, "ШІ не відповів вчасно")
      await sleep(JOB_POLL_MS)
      state = (await (await request(`/ai/jobs/${job.jobId}`)).json()) as AiJob
    }
  } finally {
    aiQueue.remove(job.jobId)
  }
  if (state.status === "failed") throw parseError(state.error?.status ?? 500, JSON.stringify(state.error ?? {}))
  return state.result as T
}

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await request(path, init)
  if (res.status === 204) return undefined as T
  const body: unknown = await res.json()
  if (res.status === 202 && body && typeof body === "object" && "jobId" in body) return awaitJob<T>(body as AiJob)
  return body as T
}

export const post = <T>(path: string, body?: unknown) =>
  http<T>(path, {
    method: "POST",
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  })

export const patch = <T>(path: string, body: unknown) => http<T>(path, { method: "PATCH", body: JSON.stringify(body) })

export const put = <T>(path: string, body: unknown) => http<T>(path, { method: "PUT", body: JSON.stringify(body) })

export const del = <T = void>(path: string) => http<T>(path, { method: "DELETE" })

export async function fetchBlob(path: string): Promise<Blob> {
  return (await request(path)).blob()
}

export async function download(path: string, fileName: string) {
  const blob = await fetchBlob(path)
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = fileName
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function openInTab(path: string, { print = false } = {}) {
  const tab = window.open("", "_blank")
  let blob: Blob
  try {
    blob = await fetchBlob(path)
  } catch (error) {
    tab?.close()
    throw error
  }
  const url = URL.createObjectURL(blob)
  if (tab && print) tab.addEventListener("load", () => tab.print(), { once: true })
  if (tab) tab.location.href = url
  else window.location.href = url
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export const query = (params: Record<string, string | number | boolean | null | undefined>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ""
}
