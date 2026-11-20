import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type {
  Incident,
  Risk,
  RiskAssessment,
  RiskCreate,
  RiskExplanation,
  RiskModelOverview,
  RiskSignal,
} from "@/shared/api"

import { http, patch, post, query } from "@/shared/api"

export const useRiskModel = (programId?: string, asOf?: string | null, enabled = true) =>
  useQuery({
    queryKey: [
      "risk-model",
      "overview",
      programId ?? null,
      asOf ?? null,
    ],
    queryFn: () => http<RiskModelOverview>(`/risk-model/overview${query({ programId, asOf })}`),
    enabled,
    placeholderData: previous => previous,
  })

export const useRiskAssessment = (riskId: string | null, asOf?: string | null) =>
  useQuery({
    queryKey: [
      "risk-model",
      "risk",
      riskId,
      asOf ?? null,
    ],
    queryFn: () => http<RiskAssessment>(`/risk-model/risks/${riskId}${query({ asOf })}`),
    enabled: Boolean(riskId),
  })

export const useRiskSignals = () =>
  useQuery({ queryKey: ["risk-model", "signals"], queryFn: () => http<RiskSignal[]>("/risk-model/signals") })

export function useAddIncident(riskId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (data: { occurredOn: string; source: string; description: string; confirmed?: boolean }) =>
      post<Incident>(`/risk-model/risks/${riskId}/incidents`, data),
    onSuccess: () => client.invalidateQueries({ queryKey: ["risk-model"] }),
  })
}

/** Переоцінка ризику робочою групою: нові бали з обовʼязковим обґрунтуванням (рівень рахує сервер). */
export function useReassessRisk(riskId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (data: { probability: number; impact: number; justification: string }) =>
      patch<Risk>(`/risks/${riskId}`, data),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["risk-model"] })
      client.invalidateQueries({ queryKey: ["reference"] })
    },
  })
}

/** Новий запис реєстру ризиків разом з індикатором ризику (KRI). */
export function useCreateRisk() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (data: RiskCreate) => post<Risk>("/risks", data),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["reference"] })
      client.invalidateQueries({ queryKey: ["risk-model"] })
    },
  })
}

export const useExplainRisk = () =>
  useMutation({
    mutationFn: (riskId: string) => post<RiskExplanation>(`/ai/risks/${riskId}/explain`),
  })
