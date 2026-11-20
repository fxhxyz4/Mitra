import { useSyncExternalStore } from "react"

export interface AiQueueEntry {
  jobId: string
  status: "queued" | "running"
  ahead: number
}

let entries: AiQueueEntry[] = []
const listeners = new Set<() => void>()
const emit = () => listeners.forEach(l => l())

export const aiQueue = {
  set(entry: AiQueueEntry) {
    entries = [...entries.filter(e => e.jobId !== entry.jobId), entry]
    emit()
  },
  remove(jobId: string) {
    entries = entries.filter(e => e.jobId !== jobId)
    emit()
  },
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  snapshot: () => entries,
}

export const useAiQueue = () => useSyncExternalStore(aiQueue.subscribe, aiQueue.snapshot)
