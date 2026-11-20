import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { CoverageGap, MeasureDraft, Program, ProgramPassport } from "@/shared/api"

import { http, invalidateDomain, post } from "@/shared/api"

export const usePassport = (programId?: string) =>
  useQuery({
    queryKey: [
      "programs",
      programId,
      "passport",
    ],
    queryFn: () => http<ProgramPassport>(`/programs/${programId}/passport`),
    enabled: Boolean(programId),
  })

export function useApproveProgram() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => post<Program>(`/programs/${id}/approve`),
    onSuccess: () => invalidateDomain(client),
  })
}

export const useCoverage = (programId?: string) =>
  useQuery({
    queryKey: [
      "programs",
      programId,
      "coverage",
    ],
    queryFn: () => http<CoverageGap[]>(`/programs/${programId}/coverage`),
    enabled: Boolean(programId),
  })

export const useRiskMeasureDraft = () =>
  useMutation({
    mutationFn: ({ riskId, programId }: { riskId: string; programId: string }) =>
      post<MeasureDraft>(`/ai/risks/${riskId}/measure-draft`, { programId }),
  })
