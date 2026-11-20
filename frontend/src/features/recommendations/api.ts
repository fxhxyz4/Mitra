import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AiSuggestion, MeasureDetail, Recommendation, RecStatus } from "@/shared/api"

import { http, invalidateDomain, post, query } from "@/shared/api"

export const useRecommendations = (status?: RecStatus) =>
  useQuery({
    queryKey: ["recommendations", status ?? null],
    queryFn: () => http<Recommendation[]>(`/recommendations${query({ status })}`),
  })

export const useMeasureAssignees = (measureId: string | null, enabled: boolean) =>
  useQuery({
    queryKey: [
      "measures",
      "detail",
      measureId,
      null,
    ],
    queryFn: () => http<MeasureDetail>(`/measures/${measureId}`),
    enabled: enabled && Boolean(measureId),
    select: m =>
      m.assignments.filter(a => a.userId).map(a => ({ value: a.userId!, label: `${a.userName} · ${a.orgUnitName}` })),
  })

export function useDecideRecommendation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (
      data:
        | { id: string; decision: "accept"; responsibleId: string; dueDate: string; text?: string }
        | { id: string; decision: "reject"; comment: string }
    ) =>
      data.decision === "accept"
        ? post<Recommendation>(`/recommendations/${data.id}/accept`, {
            responsibleId: data.responsibleId,
            dueDate: data.dueDate,
            text: data.text,
          })
        : post<Recommendation>(`/recommendations/${data.id}/reject`, { comment: data.comment }),
    onSuccess: () => invalidateDomain(client),
  })
}

export function useCompleteRecommendation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (data: { id: string; comment: string }) =>
      post<Recommendation>(`/recommendations/${data.id}/complete`, { comment: data.comment }),
    onSuccess: () => invalidateDomain(client),
  })
}

export const useSuggestRecommendation = () =>
  useMutation({
    mutationFn: (id: string) => post<AiSuggestion>(`/ai/recommendations/${id}/suggest`),
  })
