import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type {
  Evidence,
  EvidenceCheck,
  EvidenceFile,
  IndicatorValue,
  MeasureDetail,
  MeasureDraft,
  MeasureIn,
  MeasureListItem,
  MeasureStatus,
  ReportDraft,
  SubmitResult,
} from "@/shared/api"

import { http, invalidateDomain, patch, post, query } from "@/shared/api"
import { appendEvidence } from "../lib/evidenceFiles"

export type MeasureFilters = {
  mine?: boolean
  programId?: string
  sectionId?: string
  orgUnitId?: string
  riskId?: string
  status?: MeasureStatus
  overdue?: boolean
  q?: string
}

export const measureQueries = {
  all: ["measures"] as const,
  list: (filters: MeasureFilters = {}) =>
    queryOptions({
      queryKey: [
        ...measureQueries.all,
        "list",
        filters,
      ],
      queryFn: () => http<MeasureListItem[]>(`/measures${query(filters)}`),
    }),
  detail: (id: string, period?: string) =>
    queryOptions({
      queryKey: [
        ...measureQueries.all,
        "detail",
        id,
        period ?? null,
      ],
      queryFn: () => http<MeasureDetail>(`/measures/${id}${query({ period })}`),
    }),
}

export const useMeasures = (filters?: MeasureFilters) => useQuery(measureQueries.list(filters))
export const useMeasure = (id: string, period?: string) => useQuery(measureQueries.detail(id, period))

function useInvalidate() {
  const client = useQueryClient()
  return () => invalidateDomain(client)
}

export function useSubmitMeasure(id: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (data: {
      resultDescription?: string
      nonExecutionReason?: string
      period?: string
      files: EvidenceFile[]
      aiDraftKey?: string | null
      indicatorValue?: number | null
    }) => {
      const form = new FormData()
      if (data.aiDraftKey) form.set("aiDraftKey", data.aiDraftKey)
      if (data.resultDescription) form.set("resultDescription", data.resultDescription)
      if (data.nonExecutionReason) form.set("nonExecutionReason", data.nonExecutionReason)
      if (data.period) form.set("period", data.period)
      if (data.indicatorValue !== null && data.indicatorValue !== undefined)
        form.set("indicatorValue", String(data.indicatorValue))
      appendEvidence(form, data.files)
      return post<SubmitResult>(`/measures/${id}/submit`, form)
    },
    onSuccess: invalidate,
  })
}

export function useAddProgress(id: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (data: { text: string; period?: string }) => post<MeasureDetail>(`/measures/${id}/progress`, data),
    onSuccess: invalidate,
  })
}

export function useUploadEvidence(id: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (data: { files: EvidenceFile[]; period?: string }) => {
      const form = new FormData()
      if (data.period) form.set("period", data.period)
      appendEvidence(form, data.files)
      return post<Evidence[]>(`/measures/${id}/evidence`, form)
    },
    onSuccess: invalidate,
  })
}

/** Перенесення внутрішнього строку — лише координатор, з причиною; строк у програмі не змінюється. */
export function usePostponeMeasure(id: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (data: { newDeadline: string; reason: string }) =>
      post<MeasureDetail>(`/measures/${id}/deadline-changes`, data),
    onSuccess: invalidate,
  })
}

export function useApproveMeasure(id: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (data: {
      comment: string
      period?: string
      indicatorValue?: Pick<IndicatorValue, "value" | "measuredAt"> | null
    }) => post<MeasureDetail>(`/measures/${id}/approve`, data),
    onSuccess: invalidate,
  })
}

export function useReturnMeasure(id: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (data: { comment: string; period?: string }) => post<MeasureDetail>(`/measures/${id}/return`, data),
    onSuccess: invalidate,
  })
}

export function useSaveMeasure(id?: string) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (data: MeasureIn) =>
      id ? patch<MeasureDetail>(`/measures/${id}`, data) : post<MeasureDetail>("/measures", data),
    onSuccess: invalidate,
  })
}

export const useIntakeReport = () =>
  useMutation({
    mutationFn: ({ file, period }: { file: File; period?: string | null }) => {
      const form = new FormData()
      form.set("file", file)
      if (period) form.set("period", period)
      return post<ReportDraft>("/ai/intake/report", form)
    },
  })

export const useIntakeMeasure = () =>
  useMutation({
    mutationFn: ({ file, programId }: { file: File; programId: string }) => {
      const form = new FormData()
      form.set("file", file)
      form.set("programId", programId)
      return post<MeasureDraft>("/ai/intake/measure", form)
    },
  })

export const useEvidenceCheck = () =>
  useMutation({
    mutationFn: (periodId: string) => post<EvidenceCheck>(`/ai/periods/${periodId}/evidence-check`),
  })
