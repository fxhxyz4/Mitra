import { useQuery } from "@tanstack/react-query"
import type { AnalyticsOverview, AnalyticsSummary, PeerReport, PerformanceReport } from "@/shared/api"

import { download, http, query } from "@/shared/api"

export type PerformanceFilters = {
  programId?: string | null
  period?: string | null
  orgUnitId?: string | null
  userId?: string | null
}

export const useAnalyticsOverview = (weeks: number, programId?: string | null, enabled = true) =>
  useQuery({
    queryKey: [
      "analytics",
      "overview",
      weeks,
      programId ?? null,
    ],
    queryFn: () => http<AnalyticsOverview>(`/analytics/overview${query({ weeks, programId })}`),
    enabled,
    placeholderData: previous => previous,
  })

export const useAnalyticsSummary = (programId?: string | null) =>
  useQuery({
    queryKey: [
      "analytics",
      "summary",
      programId ?? null,
    ],
    queryFn: () => http<AnalyticsSummary>(`/analytics/summary${query({ programId })}`),
  })

export const usePerformance = (filters: PerformanceFilters, enabled = true) =>
  useQuery({
    queryKey: [
      "analytics",
      "performance",
      filters,
    ],
    queryFn: () => http<PerformanceReport>(`/analytics/performance${query(filters)}`),
    enabled,
    placeholderData: previous => previous,
  })

export const usePeers = (programId?: string | null) =>
  useQuery({
    queryKey: [
      "analytics",
      "peers",
      programId ?? null,
    ],
    queryFn: () => http<PeerReport>(`/analytics/peers${query({ programId })}`),
  })

export const exportPerformance = (filters: PerformanceFilters) =>
  download(`/analytics/performance/export${query(filters)}`, `analytics-${filters.period ?? "all"}.xlsx`)
