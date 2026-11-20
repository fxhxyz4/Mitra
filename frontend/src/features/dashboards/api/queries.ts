import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type {
  CoordinatorDashboard,
  ExecutiveDashboard,
  ExecutorDashboard,
  JobResult,
  UnitDashboard,
  WeeklyDigest,
} from "@/shared/api"

import { http, invalidateDomain, post, query } from "@/shared/api"

export const dashboardQueries = {
  all: ["dashboard"] as const,
  executor: () =>
    queryOptions({
      queryKey: [...dashboardQueries.all, "executor"],
      queryFn: () => http<ExecutorDashboard>("/dashboard/executor"),
    }),
  coordinator: (programId?: string) =>
    queryOptions({
      queryKey: [
        ...dashboardQueries.all,
        "coordinator",
        programId ?? null,
      ],
      queryFn: () => http<CoordinatorDashboard>(`/dashboard/coordinator${query({ programId })}`),
    }),
  executive: (programId?: string) =>
    queryOptions({
      queryKey: [
        ...dashboardQueries.all,
        "executive",
        programId ?? null,
      ],
      queryFn: () => http<ExecutiveDashboard>(`/dashboard/executive${query({ programId })}`),
    }),
  unit: (id: string, programId?: string) =>
    queryOptions({
      queryKey: [
        ...dashboardQueries.all,
        "unit",
        id,
        programId ?? null,
      ],
      queryFn: () => http<UnitDashboard>(`/dashboard/units/${id}${query({ programId })}`),
    }),
}

export const useExecutorDashboard = () => useQuery(dashboardQueries.executor())
export const useCoordinatorDashboard = (programId?: string) => useQuery(dashboardQueries.coordinator(programId))
export const useExecutiveDashboard = (programId?: string) => useQuery(dashboardQueries.executive(programId))
export const useUnitDashboard = (id: string) => useQuery(dashboardQueries.unit(id))

export function useRunDailyJob() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => post<JobResult>("/flags/evaluate"),
    onSuccess: () => invalidateDomain(client),
  })
}

export const useWeeklyDigest = () =>
  useQuery({
    queryKey: [
      "dashboards",
      "weekly-digest",
    ],
    queryFn: () => post<WeeklyDigest>("/ai/digest/weekly"),
    staleTime: 5 * 60_000,
  })
