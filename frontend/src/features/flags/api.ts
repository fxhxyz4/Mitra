import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { FlagStatus, FlagType, RiskFlag } from "@/shared/api"

import { http, invalidateDomain, post, query } from "@/shared/api"

export type FlagFilters = { status?: FlagStatus | "ALL"; type?: FlagType; programId?: string; measureId?: string }

export const useFlags = ({ status = "OPEN", ...rest }: FlagFilters = {}) =>
  useQuery({
    queryKey: [
      "flags",
      status,
      rest,
    ],
    queryFn: async () => {
      if (status !== "ALL") return http<RiskFlag[]>(`/flags${query({ ...rest, status })}`)
      const [open, resolved] = await Promise.all([
        http<RiskFlag[]>(`/flags${query({ ...rest, status: "OPEN" })}`),
        http<RiskFlag[]>(`/flags${query({ ...rest, status: "RESOLVED" })}`),
      ])
      return [...open, ...resolved]
    },
  })

export function useResolveFlag() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      post<RiskFlag>(`/flags/${id}/resolve`, { comment }),
    onSuccess: () => invalidateDomain(client),
  })
}
