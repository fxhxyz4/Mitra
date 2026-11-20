import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { DeliveryResult, InboxState, IntegraInboxItem, IntegraOutboxMessage, IntegraStatus } from "@/shared/api"

import { http, invalidateDomain, post, query } from "@/shared/api"

const base = "/integrations/integra"

export const useIntegraStatus = () =>
  useQuery({ queryKey: ["integra", "status"], queryFn: () => http<IntegraStatus>(`${base}/status`) })

export const useIntegraInbox = (state?: InboxState) =>
  useQuery({
    queryKey: [
      "integra",
      "inbox",
      state ?? null,
    ],
    queryFn: () => http<IntegraInboxItem[]>(`${base}/inbox${query({ state })}`),
  })

export const useIntegraOutbox = () =>
  useQuery({ queryKey: ["integra", "outbox"], queryFn: () => http<IntegraOutboxMessage[]>(`${base}/outbox`) })

export function useDecideInbox() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (
      data: { id: string; decision: "link"; measureId: string } | { id: string; decision: "reject"; comment: string }
    ) =>
      data.decision === "link"
        ? post<IntegraInboxItem>(`${base}/inbox/${data.id}/link`, { measureId: data.measureId })
        : post<IntegraInboxItem>(`${base}/inbox/${data.id}/reject`, { comment: data.comment }),
    onSuccess: () => invalidateDomain(client),
  })
}

export function useFlushOutbox() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => post<DeliveryResult>(`${base}/outbox/flush`),
    onSuccess: () => invalidateDomain(client),
  })
}

export function useRetryOutbox() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => post<DeliveryResult>(`${base}/outbox/${id}/retry`),
    onSuccess: () => invalidateDomain(client),
  })
}
