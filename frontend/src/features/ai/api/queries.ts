import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { AiChat, AiChatSummary } from "@/shared/api"

import { aiStatusQuery, del, http, patch, post } from "@/shared/api"
import type { RewriteResult } from "./types"

export const aiQueries = {
  all: ["ai"] as const,
  status: () => aiStatusQuery,
}

export const chatQueries = {
  all: [...aiQueries.all, "chats"] as const,
  list: () =>
    queryOptions({
      queryKey: [...chatQueries.all, "list"],
      queryFn: () => http<AiChatSummary[]>("/ai/chats"),
    }),
  detail: (id: string) =>
    queryOptions({
      queryKey: [
        ...chatQueries.all,
        "detail",
        id,
      ],
      queryFn: () => http<AiChat>(`/ai/chats/${id}`),
    }),
}

export const useRewrite = (measureId: string) =>
  useMutation({
    mutationFn: (text: string) => post<RewriteResult>(`/ai/measures/${measureId}/rewrite`, { text }),
  })

export const useChats = () => useQuery(chatQueries.list())

export const useChat = (id: string | null) => useQuery({ ...chatQueries.detail(id ?? ""), enabled: Boolean(id) })

function useChatSaved() {
  const client = useQueryClient()
  return {
    saved: (chat: AiChat) => client.setQueryData(chatQueries.detail(chat.id).queryKey, chat),
    refreshList: () => client.invalidateQueries({ queryKey: chatQueries.list().queryKey }),
  }
}

export function useSendMessage() {
  const { saved, refreshList } = useChatSaved()
  return useMutation({
    mutationFn: async ({ chatId, question }: { chatId: string | null; question: string }) => {
      const id = chatId ?? (await post<AiChat>("/ai/chats", {})).id
      return post<AiChat>(`/ai/chats/${id}/messages`, { question })
    },
    onSuccess: saved,
    onSettled: refreshList,
  })
}

export function useRenameChat() {
  const { saved, refreshList } = useChatSaved()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => patch<AiChat>(`/ai/chats/${id}`, { title }),
    onSuccess: saved,
    onSettled: refreshList,
  })
}

export function useDeleteChat() {
  const { refreshList } = useChatSaved()
  return useMutation({
    mutationFn: (id: string) => del(`/ai/chats/${id}`),
    onSettled: refreshList,
  })
}
