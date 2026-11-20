import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { NazkReport, Report, ReportCopyCheck, ReportIntegrity, ReportType, ReportVerification } from "@/shared/api"

import { http, post, query } from "@/shared/api"
import { sha256Hex } from "@/shared/lib"

export const useReports = () => useQuery({ queryKey: ["reports"], queryFn: () => http<Report[]>("/reports") })

export const useNazkReport = (id: string | null) =>
  useQuery({
    queryKey: [
      "reports",
      id,
      "nazk",
    ],
    queryFn: () => http<NazkReport>(`/reports/${id}/nazk`),
    enabled: Boolean(id),
  })

export const useReportIntegrity = (id: string | null) =>
  useQuery({
    queryKey: [
      "reports",
      id,
      "integrity",
    ],
    queryFn: () => http<ReportIntegrity>(`/reports/${id}/integrity`),
    enabled: Boolean(id),
    staleTime: Infinity,
  })

export const useReportVerification = (id: string, h: string, sig: string) =>
  useQuery({
    queryKey: [
      "verify",
      id,
      h,
      sig,
    ],
    queryFn: () => http<ReportVerification>(`/reports/${encodeURIComponent(id)}/verify${query({ h, sig })}`),
    enabled: Boolean(id && h && sig),
    retry: 1,
  })

export function useGenerateReport() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (data: { programId: string; period: string; type: ReportType }) =>
      post<Report>("/reports/generate", data),
    onSuccess: () => client.invalidateQueries({ queryKey: ["reports"] }),
  })
}

export function useRevokeReport() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => post<Report>(`/reports/${id}/revoke`, { reason }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["reports"] })
      void client.invalidateQueries({ queryKey: ["verify"] })
    },
  })
}

export const useCopyCheck = () =>
  useMutation({
    mutationFn: async ({ file, reportId }: { file: File; reportId: string }) => {
      const sha256 = await sha256Hex(file)
      const result = await http<ReportCopyCheck>(`/reports/copies/check${query({ sha256, id: reportId })}`)
      return { ...result, sha256 }
    },
  })
