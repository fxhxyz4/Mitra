export type { AiStatus } from "@/shared/api"

export interface RewriteResult {
  text: string | null
  note: string
  model: string
  modelUsed: boolean
}
