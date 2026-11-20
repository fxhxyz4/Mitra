import { useMutation, useQuery } from "@tanstack/react-query"
import type { AuditEntry, AuditVerify } from "@/shared/api"

import { http, query } from "@/shared/api"

export const useAuditLog = (filters: { entity?: string; limit?: number } = {}) =>
  useQuery({
    queryKey: ["audit", filters],
    queryFn: () => http<AuditEntry[]>(`/audit${query({ limit: 200, ...filters })}`),
  })

export const useVerifyAudit = () => useMutation({ mutationFn: () => http<AuditVerify>("/audit/verify") })
