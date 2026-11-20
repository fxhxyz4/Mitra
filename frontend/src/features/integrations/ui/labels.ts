import type { InboxState, OutboxState } from "@/shared/api"

export const externalStatusLabel: Record<string, string> = {
  planned: "Заплановано",
  in_progress: "В роботі",
  done: "Виконано",
  cancelled: "Скасовано",
}

export const inboxStateMeta: Record<InboxState, { label: string; color: string }> = {
  NEW: { label: "Нове", color: "blue" },
  LINKED: { label: "Повʼязано", color: "teal" },
  REJECTED: { label: "Відхилено", color: "gray" },
}

export const outboxStateMeta: Record<OutboxState, { label: string; color: string }> = {
  PENDING: { label: "У черзі", color: "yellow" },
  SENT: { label: "Надіслано", color: "teal" },
  FAILED: { label: "Помилка", color: "red" },
  SUPERSEDED: { label: "Замінено новішим", color: "gray" },
}

export const statusLabel = (status: string | null | undefined) =>
  status ? (externalStatusLabel[status] ?? status) : "—"
