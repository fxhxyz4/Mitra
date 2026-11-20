import { useLocalStorage } from "@mantine/hooks"
import { useQuery } from "@tanstack/react-query"

import { http } from "./http"
import { useSession } from "./session"
import type { AiStatus } from "./types"

export const AI_PREFERENCE_KEY = "mitra.ai-enabled"

export const aiStatusQuery = {
  queryKey: ["ai", "status"] as const,
  queryFn: () => http<AiStatus>("/ai/status"),
  refetchInterval: 30_000,
}

export const useAiStatus = () => {
  const { user } = useSession()
  return useQuery({ ...aiStatusQuery, enabled: Boolean(user) })
}

export const useAiPreference = () =>
  useLocalStorage<boolean>({ key: AI_PREFERENCE_KEY, defaultValue: true, getInitialValueInEffect: false })

export function useAiAccess() {
  const status = useAiStatus()
  const [userOn] = useAiPreference()
  const adminOn = status.data?.enabled !== false
  const reachable = Boolean(status.data?.reachable)
  return {
    status: status.data,
    adminOn,
    userOn,
    show: adminOn && userOn,
    model: adminOn && userOn && reachable,
  }
}
